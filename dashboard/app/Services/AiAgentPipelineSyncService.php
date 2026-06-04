<?php

namespace App\Services;

use App\Enums\AiAgentPipelinePhase;
use App\Enums\AiAgentTaskStatus;
use App\Models\AiAgentTask;
use App\Support\AiAgentPaths;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\File;

class AiAgentPipelineSyncService
{
    public function __construct(
        private readonly AiAgentJobTracker $jobTracker,
    ) {}

    public function progressDirectory(): string
    {
        return storage_path('app/agent-progress');
    }

    /**
     * Detect progress files / DB rows left active after Ctrl+C or killed processes.
     */
    public function reconcileAbandonedRuns(): int
    {
        $marked = 0;
        $staleSeconds = max(30, (int) config('ai_agent.pipeline_stale_seconds', 120));
        $cutoff = now()->subSeconds($staleSeconds);

        $dir = $this->progressDirectory();
        if (is_dir($dir)) {
            foreach (File::files($dir) as $file) {
                if ($file->getExtension() !== 'json') {
                    continue;
                }
                if ($this->reconcileProgressFile($file->getPathname(), $cutoff)) {
                    $marked++;
                }
            }
        }

        $tasks = AiAgentTask::query()
            ->where(function ($q) {
                $q->where('status', AiAgentTaskStatus::Running)
                    ->orWhere(function ($inner) {
                        $inner->where('pipeline_terminal', false)
                            ->whereNotIn('pipeline_phase', [
                                AiAgentPipelinePhase::NotStarted->value,
                                AiAgentPipelinePhase::Completed->value,
                                AiAgentPipelinePhase::Failed->value,
                                AiAgentPipelinePhase::Skipped->value,
                            ]);
                    });
            })
            ->where(function ($q) use ($cutoff) {
                $q->where('pipeline_updated_at', '<', $cutoff)
                    ->orWhereNull('pipeline_updated_at');
            })
            ->get();

        foreach ($tasks as $task) {
            if ($this->isTaskProcessLive($task)) {
                continue;
            }
            $path = $task->jira_issue_key
                ? $this->progressDirectory().'/'.str_replace('/', '_', $task->jira_issue_key).'.json'
                : null;
            if ($path && File::exists($path)) {
                $data = json_decode(File::get($path), true);
                if (is_array($data) && ! ($data['terminal'] ?? false)) {
                    $this->writeAbandonedProgress($path, $data);

                    continue;
                }
            }
            $this->applyStoppedToTask($task, 'Agent process ended before completion');
            $marked++;
        }

        return $marked;
    }

    public function markTaskStopped(AiAgentTask $task, string $reason = 'Stopped from control plane'): AiAgentTask
    {
        if ($task->jira_issue_key) {
            $path = $this->progressDirectory().'/'.str_replace('/', '_', $task->jira_issue_key).'.json';
            if (File::exists($path)) {
                $data = json_decode(File::get($path), true) ?? [];
                $this->writeAbandonedProgress($path, is_array($data) ? $data : [], $reason);
            }
        }

        $this->applyStoppedToTask($task, $reason);

        return $task->fresh();
    }

    /**
     * Sync all progress JSON files into the database (realtime polling).
     */
    public function syncAllProgressFiles(): int
    {
        $dir = $this->progressDirectory();
        if (! is_dir($dir)) {
            return 0;
        }

        $count = 0;
        foreach (File::files($dir) as $file) {
            if ($file->getExtension() !== 'json') {
                continue;
            }
            $this->syncProgressFile($file->getPathname());
            $count++;
        }

        return $count;
    }

    public function syncProgressFile(string $path): ?AiAgentTask
    {
        if (! File::exists($path)) {
            return null;
        }

        $data = json_decode(File::get($path), true);
        if (! is_array($data)) {
            return null;
        }

        $issueKey = (string) ($data['issue_key'] ?? '');
        $basename = pathinfo($path, PATHINFO_FILENAME);
        if ($issueKey === '' && ! preg_match('/^task-\d+$/', $basename)) {
            return null;
        }

        $key = (string) ($data['issue_key'] ?? '');
        $repoPath = AiAgentPaths::workspaceRepo();

        try {
            $task = $this->resolveTask($key, $path);
        } catch (\RuntimeException) {
            return null;
        }
        if (! $task->exists) {
            $task->repo_path = $repoPath;
            $task->task_description = '['.$key.'] '.($data['jira_summary'] ?? 'Jira ai-fix task');
            $task->status = AiAgentTaskStatus::Running;
            $task->started_at = now();
        }

        $phase = AiAgentPipelinePhase::tryFrom((string) ($data['phase'] ?? ''))
            ?? AiAgentPipelinePhase::Queued;

        $task->fill([
            'jira_summary' => $data['jira_summary'] ?? $task->jira_summary,
            'pipeline_phase' => $phase->value,
            'pipeline_label' => (string) ($data['label'] ?? $phase->label()),
            'pipeline_percent' => min(100, max(0, (int) ($data['percent'] ?? 0))),
            'pipeline_step' => (int) ($data['step'] ?? 0),
            'pipeline_step_total' => (int) ($data['step_total'] ?? 9),
            'pipeline_terminal' => (bool) ($data['terminal'] ?? false),
            'pipeline_history' => $data['history'] ?? $task->pipeline_history,
            'pipeline_updated_at' => isset($data['updated_at'])
                ? Carbon::parse($data['updated_at'])
                : now(),
        ]);

        if ($phase->isActive()) {
            $task->status = AiAgentTaskStatus::Running;
            $task->completed_at = null;
        }

        if ($phase === AiAgentPipelinePhase::Completed) {
            $task->status = AiAgentTaskStatus::PrCreated;
            $task->completed_at = now();
            if (! empty($data['pr_url'])) {
                $task->pr_url = $data['pr_url'];
            }
        } elseif ($phase === AiAgentPipelinePhase::Failed) {
            $task->status = AiAgentTaskStatus::Failed;
            $task->error_message = (string) ($data['error'] ?? 'Pipeline failed');
            $task->completed_at = now();
        } elseif ($phase === AiAgentPipelinePhase::Skipped) {
            $task->status = AiAgentTaskStatus::Skipped;
            $task->error_message = (string) ($data['error'] ?? $data['label'] ?? '');
            $task->completed_at = now();
        }

        if (! empty($data['validation_status'])) {
            $task->validation_status = $data['validation_status'];
        }

        $task->save();

        return $task;
    }

    /**
     * @return array<string, mixed>|null
     */
    public function readProgressForTask(AiAgentTask $task): ?array
    {
        if (! $task->jira_issue_key) {
            return null;
        }

        $path = $this->progressDirectory().'/'.str_replace('/', '_', $task->jira_issue_key).'.json';
        if (! File::exists($path)) {
            return null;
        }

        return json_decode(File::get($path), true);
    }

    private function reconcileProgressFile(string $path, Carbon $cutoff): bool
    {
        $data = json_decode(File::get($path), true);
        if (! is_array($data) || ($data['terminal'] ?? false)) {
            return false;
        }

        if ($this->isProgressProcessLive($data)) {
            return false;
        }

        $updated = isset($data['updated_at'])
            ? Carbon::parse($data['updated_at'])
            : null;

        if ($updated && $updated->greaterThan($cutoff)) {
            return false;
        }

        $this->writeAbandonedProgress($path, $data);
        $this->syncProgressFile($path);

        return true;
    }

    /**
     * @param  array<string, mixed>  $data
     */
    private function isProgressProcessLive(array $data): bool
    {
        $pid = (int) ($data['pid'] ?? 0);

        return $pid > 0 && $this->jobTracker->isPidRunning($pid);
    }

    private function isTaskProcessLive(AiAgentTask $task): bool
    {
        $data = $this->readProgressForTask($task);
        if (is_array($data) && $this->isProgressProcessLive($data)) {
            return true;
        }

        foreach ($this->jobTracker->activeJobs() as $job) {
            if ($this->jobTracker->isPidRunning((int) ($job['pid'] ?? 0))) {
                return true;
            }
        }

        return false;
    }

    /**
     * @param  array<string, mixed>  $data
     */
    private function writeAbandonedProgress(
        string $path,
        array $data,
        string $reason = 'Agent process ended before completion',
    ): void {
        $data['phase'] = AiAgentPipelinePhase::Failed->value;
        $data['label'] = 'Stopped — '.$reason;
        $data['terminal'] = true;
        $data['success'] = false;
        $data['error'] = $reason;
        $data['updated_at'] = now()->utc()->format('Y-m-d\TH:i:s\Z');
        $history = $data['history'] ?? [];
        $history[] = [
            'phase' => AiAgentPipelinePhase::Failed->value,
            'label' => $data['label'],
            'at' => $data['updated_at'],
        ];
        $data['history'] = array_slice($history, -30);

        File::put($path, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
    }

    private function applyStoppedToTask(AiAgentTask $task, string $reason): void
    {
        $task->update([
            'status' => AiAgentTaskStatus::Failed,
            'pipeline_phase' => AiAgentPipelinePhase::Failed->value,
            'pipeline_label' => 'Stopped — '.$reason,
            'pipeline_terminal' => true,
            'pipeline_updated_at' => now(),
            'error_message' => $reason,
            'completed_at' => $task->completed_at ?? now(),
        ]);
    }

    private function resolveTask(string $issueKey, string $progressPath): AiAgentTask
    {
        if ($issueKey !== '') {
            return AiAgentTask::query()->firstOrNew(['jira_issue_key' => $issueKey]);
        }

        $basename = pathinfo($progressPath, PATHINFO_FILENAME);
        if (preg_match('/^task-(\d+)$/', $basename, $matches)) {
            $task = AiAgentTask::query()->find((int) $matches[1]);
            if ($task) {
                return $task;
            }
        }

        throw new \RuntimeException('Cannot resolve task for progress file: '.$progressPath);
    }
}

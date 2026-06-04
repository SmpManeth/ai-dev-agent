<?php

namespace App\Services;

use App\Enums\AiAgentPipelinePhase;
use App\Enums\AiAgentTaskStatus;
use App\Models\AiAgentLog;
use App\Models\AiAgentTask;
use App\Support\AiAgentPaths;
use Illuminate\Support\Facades\File;
use Symfony\Component\Process\Process;

class AiAgentBatchService
{
    private const SCHEDULER_STATE_FILE = 'app/ai-agent-scheduler.json';

    public function __construct(
        private readonly AiAgentLogService $logService,
        private readonly AiAgentPipelineSyncService $pipelineSync,
        private readonly AiAgentJobTracker $jobTracker,
        private readonly AiAgentRepositoryService $repositoryService,
        private readonly AiAgentProcessService $processService,
        private readonly AiAgentHardeningService $hardeningService,
    ) {}

    /**
     * @return array<string, mixed>
     */
    public function getSchedulerState(): array
    {
        $path = storage_path(self::SCHEDULER_STATE_FILE);
        if (! File::exists($path)) {
            return [
                'enabled' => config('ai_agent.schedule_enabled'),
                'interval_minutes' => config('ai_agent.schedule_interval_minutes'),
                'last_run_at' => null,
                'last_success' => null,
                'last_stats' => null,
                'last_error' => null,
                'last_triggered_by' => null,
            ];
        }

        return array_merge(
            [
                'enabled' => config('ai_agent.schedule_enabled'),
                'interval_minutes' => config('ai_agent.schedule_interval_minutes'),
            ],
            json_decode(File::get($path), true) ?? [],
        );
    }

    /**
     * @param  array<string, mixed>  $data
     */
    public function recordSchedulerRun(array $data): void
    {
        $path = storage_path(self::SCHEDULER_STATE_FILE);
        File::ensureDirectoryExists(dirname($path));
        File::put($path, json_encode(array_merge([
            'updated_at' => now()->toIso8601String(),
        ], $data), JSON_PRETTY_PRINT));
    }

    /**
     * Run Python batch processor for all Jira ai-fix issues.
     *
     * @return array<string, mixed>
     */
    public function runJiraBatch(?string $repoPath = null, string $triggeredBy = 'manual', bool $waitForCompletion = false): array
    {
        if (! $this->hardeningService->isAgentEnabled()) {
            throw new \RuntimeException('AI agent is disabled (kill switch). Enable it in Settings → Production hardening.');
        }

        $repoPath = $this->repositoryService->ensureSynced($repoPath);

        $this->recordSchedulerRun([
            'last_run_at' => now()->toIso8601String(),
            'last_triggered_by' => $triggeredBy,
            'last_success' => null,
            'last_stats' => null,
            'last_error' => null,
            'running' => true,
        ]);

        $batchJson = storage_path('app/agent-runs/jira-batch-'.now()->format('Ymd-His').'.json');
        File::ensureDirectoryExists(dirname($batchJson));
        File::ensureDirectoryExists($this->pipelineSync->progressDirectory());

        $command = $this->buildBatchCommand($repoPath, $batchJson);

        $batchLog = storage_path('logs/jira-batch-'.now()->format('Ymd-His').'.log');
        $hardening = $this->hardeningService->current();
        $env = array_filter(array_merge($_ENV, $_SERVER), fn ($v) => is_string($v));
        $env['AI_AGENT_HARDENING_CONFIG'] = $this->hardeningService->hardeningConfigPath();
        if (! empty($hardening['sandbox_enabled'])) {
            $env['AI_AGENT_USE_SANDBOX'] = '1';
        }
        $env['AI_AGENT_PR_APPROVED'] = ($hardening['require_approval_before_pr'] ?? false) ? '0' : '1';

        $process = new Process(
            $command,
            config('ai_agent.project_path'),
            $env,
            null,
            min(
                config('ai_agent.default_timeout'),
                ($hardening['max_runtime_minutes'] ?? 120) * 60,
            ),
        );

        $process->start();
        $pid = (int) $process->getPid();
        $jobId = 'jira-batch-'.now()->format('Ymd-His');

        $this->jobTracker->register($jobId, $pid, [
            'type' => 'jira_batch',
            'triggered_by' => $triggeredBy,
            'batch_json' => $batchJson,
            'batch_log' => $batchLog,
            'repo_path' => $repoPath,
        ]);

        $this->recordSchedulerRun([
            'last_run_at' => now()->toIso8601String(),
            'last_triggered_by' => $triggeredBy,
            'last_success' => null,
            'last_stats' => null,
            'last_error' => null,
            'running' => true,
            'batch_log' => $batchLog,
            'batch_json' => $batchJson,
            'background_job_id' => $jobId,
            'background_pid' => $pid,
        ]);

        $started = [
            'running' => true,
            'background_job_id' => $jobId,
            'background_pid' => $pid,
            'batch_log' => $batchLog,
            'batch_json' => $batchJson,
            'repo_path' => $repoPath,
            'pr_created' => 0,
            'failed' => 0,
            'skipped' => 0,
            'total' => 0,
        ];

        if ($waitForCompletion) {
            return $this->waitForJob($jobId, (int) config('ai_agent.default_timeout', 3600));
        }

        return $started;
    }

    /**
     * @return array<string, mixed>
     */
    public function waitForJob(string $jobId, int $timeoutSeconds = 3600): array
    {
        $deadline = time() + $timeoutSeconds;

        while (time() < $deadline) {
            $this->tickBackgroundJobs();

            $scheduler = $this->getSchedulerState();
            if (! ($scheduler['running'] ?? false)) {
                return array_merge([
                    'running' => false,
                    'exit_code' => ($scheduler['last_success'] ?? false) ? 0 : 1,
                ], $scheduler['last_stats'] ?? [
                    'pr_created' => 0,
                    'failed' => 0,
                    'skipped' => 0,
                    'total' => 0,
                ]);
            }

            usleep(500_000);
        }

        throw new \RuntimeException('Timed out waiting for agent job '.$jobId);
    }

    public function clearStaleSchedulerState(): void
    {
        $state = $this->getSchedulerState();
        if (! ($state['running'] ?? false)) {
            return;
        }

        foreach ($this->jobTracker->activeJobs() as $job) {
            if ($this->jobTracker->isPidRunning((int) ($job['pid'] ?? 0))) {
                return;
            }
        }

        $this->recordSchedulerRun(array_merge($state, [
            'running' => false,
            'last_error' => $state['last_error'] ?? 'Run ended (process no longer active)',
        ]));
    }

    public function tickBackgroundJobs(): void
    {
        $this->clearStaleSchedulerState();

        foreach ($this->jobTracker->activeJobs() as $job) {
            $pid = (int) ($job['pid'] ?? 0);
            if ($this->jobTracker->isPidRunning($pid)) {
                continue;
            }

            $jobId = (string) ($job['job_id'] ?? '');
            $type = (string) ($job['type'] ?? '');

            if ($type === 'jira_batch') {
                $this->finalizeJiraBatchJob($job);
            } elseif ($type === 'single_task') {
                $this->finalizeSingleTaskJob($job);
            }

            if ($jobId !== '') {
                $this->jobTracker->remove($jobId);
            }
        }
    }

    /**
     * @param  array<string, mixed>  $job
     */
    private function finalizeJiraBatchJob(array $job): void
    {
        $batchJson = (string) ($job['batch_json'] ?? '');
        $batchLog = (string) ($job['batch_log'] ?? '');
        $repoPath = (string) ($job['repo_path'] ?? '');
        $triggeredBy = (string) ($job['triggered_by'] ?? 'manual');

        $stats = ['pr_created' => 0, 'failed' => 0, 'skipped' => 0, 'total' => 0];
        $error = null;

        if ($batchJson !== '' && File::exists($batchJson)) {
            $stats = $this->syncTasksFromBatchJson($batchJson, $repoPath, $batchLog);
        } elseif ($batchLog !== '' && File::exists($batchLog)) {
            $error = 'Batch finished without result JSON. See batch log.';
        } else {
            $error = 'Batch process ended without output.';
        }

        $this->pipelineSync->syncAllProgressFiles();

        $this->recordSchedulerRun([
            'last_run_at' => now()->toIso8601String(),
            'last_triggered_by' => $triggeredBy,
            'last_success' => $error === null && ($stats['failed'] ?? 0) === 0,
            'last_stats' => $stats,
            'last_error' => $error,
            'running' => false,
            'batch_log' => $batchLog ?: null,
        ]);
    }

    /**
     * @param  array<string, mixed>  $job
     */
    private function finalizeSingleTaskJob(array $job): void
    {
        $taskId = (int) ($job['task_id'] ?? 0);
        $summaryPath = (string) ($job['summary_path'] ?? '');
        $logFile = (string) ($job['log_file'] ?? '');

        $task = AiAgentTask::query()->find($taskId);
        if (! $task) {
            return;
        }

        $progressPath = (string) ($job['progress_path'] ?? '');
        if ($progressPath !== '' && File::exists($progressPath)) {
            $this->pipelineSync->syncProgressFile($progressPath);
            $task->refresh();
        }

        $this->processService->finalizeFromSummary($task, $summaryPath, $logFile);
    }

    /**
     * @return array<string, mixed>
     */
    public function pipelinePayload(AiAgentTask $task): array
    {
        $phase = $task->pipelinePhaseEnum();

        return [
            'id' => $task->id,
            'jira_issue_key' => $task->jira_issue_key,
            'status' => $task->status->value,
            'status_label' => $task->status->label(),
            'pipeline_phase' => $phase->value,
            'pipeline_label' => $task->displayPipelineLabel(),
            'pipeline_percent' => (int) ($task->pipeline_percent ?? 0),
            'pipeline_step' => (int) ($task->pipeline_step ?? 0),
            'pipeline_step_total' => (int) ($task->pipeline_step_total ?? 9),
            'pipeline_terminal' => (bool) $task->pipeline_terminal,
            'pipeline_active' => $task->isPipelineActive(),
            'pipeline_badge_color' => $task->isPipelineActive()
                ? $phase->badgeColorActive()
                : $phase->badgeColor(),
            'pipeline_history' => $task->pipeline_history ?? [],
            'pipeline_updated_at' => $task->pipeline_updated_at?->toIso8601String(),
            'error_message' => $task->error_message,
            'pr_url' => $task->pr_url,
        ];
    }

    public function ensureRepositorySynced(?string $repoPath = null): string
    {
        return $this->repositoryService->ensureSynced($repoPath);
    }

    /**
     * @return list<string>
     */
    public function buildBatchCommand(string $repoPath, string $batchJson): array
    {
        $python = config('ai_agent.python_path');
        $main = rtrim(config('ai_agent.project_path'), '/').'/main.py';

        return [
            $python,
            $main,
            '--from-jira',
            '--repo',
            $repoPath,
            '--apply-patch',
            '--commit',
            '--create-pr',
            '--max-tasks='.(string) config('ai_agent.jira_batch_max_tasks', 1),
            '--batch-json',
            $batchJson,
            '--progress-dir',
            $this->pipelineSync->progressDirectory(),
        ];
    }

    /**
     * @return array{pr_created: int, failed: int, skipped: int, total: int}
     */
    private function syncTasksFromBatchJson(string $batchJson, string $repoPath, string $batchLog): array
    {
        $data = json_decode(File::get($batchJson), true) ?? [];
        $items = $data['items'] ?? [];
        $stats = ['pr_created' => 0, 'failed' => 0, 'skipped' => 0, 'total' => count($items)];

        $jiraBase = rtrim(config('ai_agent.jira_base_url', ''), '/');
        $repoUrl = AiAgentPaths::githubRepoUrl();

        foreach ($items as $item) {
            $key = $item['issue_key'] ?? '';
            if ($key === '') {
                continue;
            }

            $batchStatus = $item['status'] ?? 'failed';
            $status = $this->mapBatchStatus($batchStatus);

            if ($batchStatus === 'pr_created') {
                $stats['pr_created']++;
            } elseif ($batchStatus === 'skipped') {
                $stats['skipped']++;
            } elseif ($batchStatus === 'failed') {
                $stats['failed']++;
            }

            $pipelinePhase = AiAgentPipelinePhase::tryFrom($item['pipeline_phase'] ?? '')
                ?? $this->mapBatchToPipeline($batchStatus);

            $task = AiAgentTask::updateOrCreate(
                ['jira_issue_key' => $key],
                [
                    'jira_summary' => $item['summary'] ?? null,
                    'jira_url' => $jiraBase ? "{$jiraBase}/browse/{$key}" : null,
                    'repo_path' => $repoPath,
                    'repo_url' => $repoUrl,
                    'branch_name' => $item['branch_name'] ?? "ai-fix/{$key}",
                    'task_description' => '['.$key.'] '.($item['summary'] ?? 'Jira ai-fix task'),
                    'status' => $status,
                    'pipeline_phase' => $pipelinePhase->value,
                    'pipeline_label' => $item['pipeline_label'] ?? $pipelinePhase->label(),
                    'pipeline_percent' => (int) ($item['pipeline_percent'] ?? ($pipelinePhase === AiAgentPipelinePhase::Completed ? 100 : 0)),
                    'pipeline_terminal' => $pipelinePhase->isTerminal(),
                    'pipeline_updated_at' => now(),
                    'validation_status' => $item['validation_status'] ?? null,
                    'pr_url' => $item['pr_url'] ?? null,
                    'pr_number' => $item['pr_number'] ?? null,
                    'error_message' => $item['error_message'] ?? $item['reason'] ?? null,
                    'changed_files' => $item['changed_files'] ?? null,
                    'logs_path' => $batchLog,
                    'completed_at' => now(),
                    'started_at' => now(),
                ],
            );

            AiAgentLog::create([
                'ai_agent_task_id' => $task->id,
                'level' => $batchStatus === 'failed' ? 'error' : 'info',
                'step' => 'jira_batch',
                'message' => sprintf(
                    '%s: %s%s',
                    $key,
                    $batchStatus,
                    isset($item['reason']) && $item['reason'] !== ''
                        ? ' — '.$item['reason']
                        : ''
                ),
                'context' => ['pr_url' => $item['pr_url'] ?? null],
                'created_at' => now(),
            ]);
        }

        return $stats;
    }

    private function mapBatchStatus(string $batchStatus): AiAgentTaskStatus
    {
        return match ($batchStatus) {
            'pr_created' => AiAgentTaskStatus::PrCreated,
            'skipped' => AiAgentTaskStatus::Skipped,
            'failed' => AiAgentTaskStatus::Failed,
            'dry_run' => AiAgentTaskStatus::Queued,
            default => AiAgentTaskStatus::Failed,
        };
    }

    private function mapBatchToPipeline(string $batchStatus): AiAgentPipelinePhase
    {
        return match ($batchStatus) {
            'pr_created' => AiAgentPipelinePhase::Completed,
            'skipped' => AiAgentPipelinePhase::Skipped,
            'failed' => AiAgentPipelinePhase::Failed,
            default => AiAgentPipelinePhase::Failed,
        };
    }
}

<?php

namespace App\Services;

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
    public function runJiraBatch(?string $repoPath = null, string $triggeredBy = 'manual'): array
    {
        $repoPath = $this->ensureRepositorySynced($repoPath);

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

        $command = $this->buildBatchCommand($repoPath, $batchJson);

        $batchLog = storage_path('logs/jira-batch-'.now()->format('Ymd-His').'.log');
        $process = new Process(
            $command,
            config('ai_agent.project_path'),
            null,
            null,
            config('ai_agent.default_timeout'),
        );

        $process->run();

        File::put($batchLog, $process->getOutput()."\n".$process->getErrorOutput());

        if (! $process->isSuccessful() && ! File::exists($batchJson)) {
            $message = trim($process->getErrorOutput() ?: $process->getOutput());
            $this->recordSchedulerRun([
                'last_run_at' => now()->toIso8601String(),
                'last_triggered_by' => $triggeredBy,
                'last_success' => false,
                'last_error' => $message,
                'running' => false,
            ]);
            throw new \RuntimeException('Jira batch failed: '.$message);
        }

        $stats = ['pr_created' => 0, 'failed' => 0, 'skipped' => 0, 'total' => 0];

        if (File::exists($batchJson)) {
            $stats = $this->syncTasksFromBatchJson($batchJson, $repoPath, $batchLog);
        }

        $result = array_merge($stats, [
            'exit_code' => $process->getExitCode() ?? 1,
            'batch_log' => $batchLog,
            'batch_json' => $batchJson,
            'repo_path' => $repoPath,
        ]);

        $this->recordSchedulerRun([
            'last_run_at' => now()->toIso8601String(),
            'last_triggered_by' => $triggeredBy,
            'last_success' => ($result['exit_code'] ?? 1) === 0 || ($result['failed'] ?? 0) === 0,
            'last_stats' => $stats,
            'last_error' => null,
            'running' => false,
            'batch_log' => $batchLog,
        ]);

        return $result;
    }

    /**
     * Clone or pull the GitHub repo before a batch (uses Python + root .env).
     */
    public function ensureRepositorySynced(?string $repoPath = null): string
    {
        if (! config('ai_agent.auto_sync_repo', true)) {
            $repoPath = $repoPath ?: AiAgentPaths::workspaceRepo();
            if (! is_dir($repoPath)) {
                throw new \RuntimeException(
                    'Workspace repo not found at '. $repoPath
                    .'. Set GITHUB_OWNER and GITHUB_REPO in Python .env, or enable AI_AGENT_AUTO_SYNC_REPO.'
                );
            }

            return $repoPath;
        }

        $python = config('ai_agent.python_path');
        $script = rtrim(config('ai_agent.project_path'), '/').'/scripts/sync_repo.py';
        $command = [$python, $script];
        if ($repoPath) {
            $command[] = '--repo='.$repoPath;
        }

        $process = new Process(
            $command,
            config('ai_agent.project_path'),
            null,
            null,
            600,
        );
        $process->run();

        if (! $process->isSuccessful()) {
            throw new \RuntimeException(
                'Repository sync failed: '.trim($process->getErrorOutput() ?: $process->getOutput())
            );
        }

        $path = trim($process->getOutput());
        if ($path === '' || ! is_dir($path)) {
            throw new \RuntimeException('Repository sync did not return a valid path.');
        }

        return $path;
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
            '--run-tests',
            '--commit',
            '--create-pr',
            '--max-tasks='.(string) config('ai_agent.jira_batch_max_tasks', 1),
            '--batch-json',
            $batchJson,
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
}

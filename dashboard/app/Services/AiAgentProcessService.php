<?php

namespace App\Services;

use App\Enums\AiAgentTaskStatus;
use App\Models\AiAgentTask;
use App\Support\AiAgentPaths;
use Illuminate\Support\Facades\File;
use Symfony\Component\Process\Process;

class AiAgentProcessService
{
    public function __construct(
        private readonly AiAgentLogService $logService,
        private readonly AiAgentBatchService $batchService,
    ) {}

    public function run(AiAgentTask $task, ?bool $createPr = null): int
    {
        if (! $task->canRun()) {
            throw new \RuntimeException('Task cannot be run in its current state.');
        }

        $wasApproved = $task->status === AiAgentTaskStatus::Approved;

        if ($task->isHighRisk() && ! $wasApproved) {
            throw new \RuntimeException('High-risk tasks require explicit approval before running.');
        }

        if ($task->requiresApprovalBeforeRun()) {
            throw new \RuntimeException('Task requires human approval before the agent can run.');
        }

        if ($createPr === null) {
            $createPr = ! in_array($task->risk_level, ['medium', 'high'], true) || $wasApproved;
        }

        $task->update([
            'status' => AiAgentTaskStatus::Running,
            'started_at' => $task->started_at ?? now(),
            'completed_at' => null,
            'error_message' => null,
        ]);

        $this->logService->log($task, 'Starting Python agent', 'info', 'run');

        if (config('ai_agent.auto_sync_repo', true)) {
            $synced = $this->batchService->ensureRepositorySynced($task->repo_path);
            if ($task->repo_path !== $synced) {
                $task->update([
                    'repo_path' => $synced,
                    'repo_url' => $task->repo_url ?: AiAgentPaths::githubRepoUrl(),
                ]);
            }
        }

        $summaryPath = storage_path("app/agent-runs/task-{$task->id}-summary.json");
        File::ensureDirectoryExists(dirname($summaryPath));

        $command = $this->buildCommand($task, $summaryPath, $createPr);
        $this->logService->log(
            $task,
            'Command: '.$this->logService->sanitize(implode(' ', $this->redactCommand($command))),
            'info',
            'run',
        );

        $process = new Process(
            $command,
            config('ai_agent.project_path'),
            null,
            null,
            config('ai_agent.default_timeout'),
        );

        $process->run(function (string $type, string $buffer) use ($task) {
            $this->logService->logProcessOutput($task, $type, $buffer);
        });

        $logFile = storage_path("logs/agent-task-{$task->id}.log");
        File::put($logFile, $process->getOutput()."\n".$process->getErrorOutput());

        $exitCode = $process->getExitCode() ?? 1;
        $this->syncFromSummary($task, $summaryPath, $exitCode, $logFile);

        return $exitCode;
    }

    /**
     * @return list<string>
     */
    public function buildCommand(AiAgentTask $task, string $summaryPath, bool $createPr): array
    {
        $python = config('ai_agent.python_path');
        $main = rtrim(config('ai_agent.project_path'), '/').'/main.py';

        $cmd = [
            $python,
            $main,
            '--repo',
            $task->repo_path,
            '--task',
            $task->task_description,
            '--apply-patch',
            '--run-tests',
            '--commit',
            '--summary-json',
            $summaryPath,
        ];

        if ($task->branch_name) {
            $cmd[] = '--branch-name';
            $cmd[] = $task->branch_name;
        }

        if ($createPr) {
            $cmd[] = '--create-pr';
        }

        if ($task->jira_issue_key) {
            $cmd[] = '--jira-issue';
            $cmd[] = $task->jira_issue_key;
        }

        return $cmd;
    }

    private function syncFromSummary(
        AiAgentTask $task,
        string $summaryPath,
        int $exitCode,
        string $logFile,
    ): void {
        $updates = [
            'logs_path' => $logFile,
            'completed_at' => now(),
        ];

        if (File::exists($summaryPath)) {
            $summary = json_decode(File::get($summaryPath), true) ?? [];
            $updates['risk_level'] = $summary['risk_level'] ?? $task->risk_level;
            $updates['validation_status'] = $summary['validation_status'] ?? $task->validation_status;
            $updates['branch_name'] = $summary['branch_name'] ?? $task->branch_name;
            $updates['pr_url'] = $summary['pr_url'] ?? $task->pr_url;
            $updates['pr_number'] = $summary['pr_number'] ?? $task->pr_number;
            $updates['changed_files'] = $summary['changed_files'] ?? $task->changed_files;
            $updates['error_message'] = $summary['error_message'] ?? null;

            $updates['status'] = $this->mapSummaryStatus($summary, $exitCode);
        } else {
            $updates['status'] = $exitCode === 0
                ? AiAgentTaskStatus::Completed
                : AiAgentTaskStatus::Failed;
            if ($exitCode !== 0) {
                $updates['error_message'] = 'Agent exited with code '.$exitCode;
            }
        }

        $task->update($updates);

        $this->logService->log(
            $task,
            'Agent finished with exit code '.$exitCode,
            $exitCode === 0 ? 'info' : 'error',
            'run',
            ['status' => $task->fresh()->status->value],
        );
    }

    private function mapSummaryStatus(array $summary, int $exitCode): AiAgentTaskStatus
    {
        if ($exitCode !== 0) {
            if (($summary['validation_status'] ?? '') === 'failed') {
                return AiAgentTaskStatus::TestsFailed;
            }

            return AiAgentTaskStatus::Failed;
        }

        if (! empty($summary['jira_update_status']) && $summary['jira_update_status'] === 'updated') {
            return AiAgentTaskStatus::JiraUpdated;
        }
        if (! empty($summary['pr_url'])) {
            return AiAgentTaskStatus::PrCreated;
        }
        if (($summary['commit_status'] ?? '') === 'committed') {
            return AiAgentTaskStatus::Committed;
        }
        if (($summary['validation_status'] ?? '') === 'passed') {
            return AiAgentTaskStatus::TestsPassed;
        }

        return AiAgentTaskStatus::Completed;
    }

    /**
     * @param  list<string>  $command
     * @return list<string>
     */
    private function redactCommand(array $command): array
    {
        return array_map(fn ($part) => $this->logService->sanitize($part), $command);
    }
}

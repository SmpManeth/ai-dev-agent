<?php

namespace App\Services;

use App\Enums\AiAgentPipelinePhase;
use App\Enums\AiAgentTaskStatus;
use App\Models\AiAgentTask;
use App\Support\AiAgentPaths;
use Illuminate\Support\Facades\File;
use Symfony\Component\Process\Process;

class AiAgentProcessService
{
    public function __construct(
        private readonly AiAgentLogService $logService,
        private readonly AiAgentRepositoryService $repositoryService,
        private readonly AiAgentPipelineSyncService $pipelineSync,
        private readonly AiAgentJobTracker $jobTracker,
        private readonly AiAgentHardeningService $hardeningService,
    ) {}

    public function run(AiAgentTask $task, ?bool $createPr = null, bool $background = true): int
    {
        if (! $this->hardeningService->isAgentEnabled()) {
            throw new \RuntimeException('AI agent is disabled (kill switch).');
        }

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

        $progressPath = $this->progressPathFor($task);
        File::ensureDirectoryExists(dirname($progressPath));

        $task->update([
            'status' => AiAgentTaskStatus::Running,
            'started_at' => $task->started_at ?? now(),
            'completed_at' => null,
            'error_message' => null,
            'pipeline_phase' => AiAgentPipelinePhase::Queued->value,
            'pipeline_label' => AiAgentPipelinePhase::Queued->label(),
            'pipeline_percent' => 0,
            'pipeline_terminal' => false,
            'pipeline_updated_at' => now(),
        ]);

        $this->logService->log($task, 'Starting Python agent', 'info', 'run');

        if (config('ai_agent.auto_sync_repo', true)) {
            $synced = $this->repositoryService->ensureSynced($task->repo_path);
            if ($task->repo_path !== $synced) {
                $task->update([
                    'repo_path' => $synced,
                    'repo_url' => $task->repo_url ?: AiAgentPaths::githubRepoUrl(),
                ]);
            }
        }

        $summaryPath = storage_path("app/agent-runs/task-{$task->id}-summary.json");
        File::ensureDirectoryExists(dirname($summaryPath));

        $command = $this->buildCommand($task, $summaryPath, $createPr, $progressPath);
        $this->logService->log(
            $task,
            'Command: '.$this->logService->sanitize(implode(' ', $this->redactCommand($command))),
            'info',
            'run',
        );

        $logFile = storage_path("logs/agent-task-{$task->id}.log");

        if (! $background) {
            return $this->runForeground($task, $command, $summaryPath, $logFile, $createPr);
        }

        $process = new Process(
            $command,
            config('ai_agent.project_path'),
            $this->buildAgentEnvironment($task, $createPr),
            null,
            min(
                config('ai_agent.default_timeout'),
                ($this->hardeningService->current()['max_runtime_minutes'] ?? 120) * 60,
            ),
        );
        $process->start();

        $jobId = 'task-'.$task->id.'-'.now()->format('Ymd-His');
        $this->jobTracker->register($jobId, (int) $process->getPid(), [
            'type' => 'single_task',
            'task_id' => $task->id,
            'summary_path' => $summaryPath,
            'log_file' => $logFile,
            'progress_path' => $progressPath,
        ]);

        return 0;
    }

    /**
     * @param  list<string>  $command
     */
    private function runForeground(
        AiAgentTask $task,
        array $command,
        string $summaryPath,
        string $logFile,
        bool $createPr,
    ): int {
        $process = new Process(
            $command,
            config('ai_agent.project_path'),
            $this->buildAgentEnvironment($task, $createPr),
            null,
            min(
                config('ai_agent.default_timeout'),
                ($this->hardeningService->current()['max_runtime_minutes'] ?? 120) * 60,
            ),
        );

        $process->run(function (string $type, string $buffer) use ($task) {
            $this->logService->logProcessOutput($task, $type, $buffer);
            $this->pipelineSync->syncProgressFile($this->progressPathFor($task));
        });

        File::put($logFile, $process->getOutput()."\n".$process->getErrorOutput());
        $exitCode = $process->getExitCode() ?? 1;
        $this->finalizeFromSummary($task, $summaryPath, $logFile, $exitCode);

        return $exitCode;
    }

    public function finalizeFromSummary(
        AiAgentTask $task,
        string $summaryPath,
        string $logFile,
        ?int $exitCode = null,
    ): void {
        if ($task->jira_issue_key) {
            $this->pipelineSync->syncProgressFile($this->progressPathFor($task));
            $task->refresh();
        }

        if ($exitCode === null) {
            $exitCode = File::exists($summaryPath) ? 0 : 1;
        }

        $this->syncFromSummary($task, $summaryPath, $exitCode, $logFile);
    }

    /**
     * @return list<string>
     */
    public function buildCommand(
        AiAgentTask $task,
        string $summaryPath,
        bool $createPr,
        ?string $progressPath = null,
    ): array {
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

        $progress = $progressPath ?? $this->progressPathFor($task);
        $cmd[] = '--progress-json';
        $cmd[] = $progress;

        return $cmd;
    }

    public function progressPathFor(AiAgentTask $task): string
    {
        $key = $task->jira_issue_key ?: ('task-'.$task->id);

        return $this->pipelineSync->progressDirectory().'/'.str_replace('/', '_', $key).'.json';
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
            'pipeline_terminal' => true,
            'pipeline_updated_at' => now(),
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
            $updates['pipeline_phase'] = $exitCode === 0
                ? AiAgentPipelinePhase::Completed->value
                : AiAgentPipelinePhase::Failed->value;
            $updates['pipeline_label'] = $exitCode === 0
                ? AiAgentPipelinePhase::Completed->label()
                : AiAgentPipelinePhase::Failed->label();
            $updates['pipeline_percent'] = $exitCode === 0 ? 100 : (int) ($task->pipeline_percent ?? 0);
        } else {
            $updates['status'] = $exitCode === 0
                ? AiAgentTaskStatus::Completed
                : AiAgentTaskStatus::Failed;
            $updates['pipeline_phase'] = $exitCode === 0
                ? AiAgentPipelinePhase::Completed->value
                : AiAgentPipelinePhase::Failed->value;
            $updates['pipeline_label'] = $updates['pipeline_phase'] === AiAgentPipelinePhase::Completed->value
                ? AiAgentPipelinePhase::Completed->label()
                : AiAgentPipelinePhase::Failed->label();
            $updates['pipeline_percent'] = $exitCode === 0 ? 100 : 0;
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

    /**
     * @return array<string, string>
     */
    private function buildAgentEnvironment(AiAgentTask $task, bool $createPr): array
    {
        $hardening = $this->hardeningService->current();
        $env = array_merge($_ENV, $_SERVER);
        $env = array_filter($env, fn ($v) => is_string($v));
        $env['AI_AGENT_HARDENING_CONFIG'] = $this->hardeningService->hardeningConfigPath();
        if (! empty($hardening['sandbox_enabled'])) {
            $env['AI_AGENT_USE_SANDBOX'] = '1';
        }
        if ($createPr && $task->status === \App\Enums\AiAgentTaskStatus::Approved) {
            $env['AI_AGENT_PR_APPROVED'] = '1';
        }
        if (! ($hardening['require_approval_before_pr'] ?? false)) {
            $env['AI_AGENT_PR_APPROVED'] = '1';
        }

        return $env;
    }
}

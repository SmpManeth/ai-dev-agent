<?php

namespace App\Console\Commands;

use App\Services\AiAgentBatchService;
use Illuminate\Console\Command;

class RunJiraBatchCommand extends Command
{
    protected $signature = 'ai-agent:run-jira-batch
                            {--repo= : Optional override of workspace repo path}
                            {--force : Run even when AI_AGENT_SCHEDULE_ENABLED=false}';

    protected $description = 'Poll Jira for ai-fix issues and run the Python agent batch (one PR per issue)';

    public function handle(AiAgentBatchService $batchService): int
    {
        if (! config('ai_agent.schedule_enabled') && ! $this->option('force')) {
            $this->warn('Scheduler is disabled. Set AI_AGENT_SCHEDULE_ENABLED=true or use --force.');

            return self::SUCCESS;
        }

        $this->info('Starting Jira ai-fix batch at '.now()->toDateTimeString());

        try {
            $result = $batchService->runJiraBatch($this->option('repo'), 'schedule', waitForCompletion: true);
            $repo = $result['repo_path'] ?? 'synced';
            $this->line("Repo: {$repo}");
        } catch (\Throwable $e) {
            $this->error($e->getMessage());
            $batchService->recordSchedulerRun([
                'triggered_by' => 'schedule',
                'success' => false,
                'error' => $e->getMessage(),
            ]);

            return self::FAILURE;
        }

        $this->info(sprintf(
            'Batch done: %d PR created, %d failed, %d skipped (of %d).',
            $result['pr_created'],
            $result['failed'],
            $result['skipped'],
            $result['total'],
        ));

        if (($result['exit_code'] ?? 0) !== 0 && ($result['failed'] ?? 0) > 0) {
            return self::FAILURE;
        }

        return self::SUCCESS;
    }
}

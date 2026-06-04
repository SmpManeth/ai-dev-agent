<?php

namespace App\Console\Commands;

use App\Models\AiAgentLog;
use App\Models\AiAgentTask;
use Illuminate\Console\Command;

class PurgeDemoTasksCommand extends Command
{
    protected $signature = 'ai-agent:purge-demo';

    protected $description = 'Remove demo tasks (e.g. DEMO-1) and test-project rows from the dashboard database';

    public function handle(): int
    {
        $query = AiAgentTask::query()->where(function ($q) {
            $q->where('jira_issue_key', 'like', 'DEMO-%')
                ->orWhere('repo_path', 'like', '%test-project%');
        });

        $count = $query->count();
        if ($count === 0) {
            $this->info('No demo tasks found.');

            return self::SUCCESS;
        }

        $ids = $query->pluck('id');
        AiAgentLog::query()->whereIn('ai_agent_task_id', $ids)->delete();
        $query->delete();

        $this->info("Removed {$count} demo task(s).");

        return self::SUCCESS;
    }
}

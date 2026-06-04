<?php

namespace App\Services;

use App\Support\AiAgentPaths;
use Illuminate\Support\Facades\File;

class AiAgentHealthService
{
    /**
     * @return array{
     *     ready: bool,
     *     checks: list<array{label: string, ok: bool, detail: string}>
     * }
     */
    public function check(): array
    {
        $checks = [];
        $projectPath = rtrim((string) config('ai_agent.project_path'), '/');
        $python = (string) config('ai_agent.python_path');
        $mainPy = $projectPath.'/main.py';
        $pythonEnv = $projectPath.'/.env';
        $workspace = AiAgentPaths::workspaceRepo();
        $owner = trim((string) config('ai_agent.github_owner', ''));
        $repo = trim((string) config('ai_agent.github_repo', ''));
        $jiraUrl = trim((string) config('ai_agent.jira_base_url', ''));

        $checks[] = $this->row(
            'Python agent project',
            is_dir($projectPath) && is_file($mainPy),
            is_file($mainPy)
                ? $projectPath
                : 'Set AI_AGENT_PROJECT_PATH to the ai-dev-agent repo root (main.py missing).',
        );

        $checks[] = $this->row(
            'Python credentials (.env)',
            is_file($pythonEnv),
            is_file($pythonEnv)
                ? 'Found at project root (Jira/GitHub/OpenAI).'
                : 'Copy .env.example to '.$projectPath.'/.env and configure.',
        );

        $checks[] = $this->row(
            'GitHub target',
            $owner !== '' && $repo !== '',
            $owner !== '' && $repo !== ''
                ? "{$owner}/".AiAgentPaths::normalizeRepoName($repo)
                : 'Set GITHUB_OWNER and GITHUB_REPO in dashboard .env.',
        );

        $checks[] = $this->row(
            'Workspace clone',
            is_dir($workspace),
            is_dir($workspace)
                ? $workspace
                : 'Run Jira batch or enable AI_AGENT_AUTO_SYNC_REPO to clone.',
        );

        $checks[] = $this->row(
            'Jira dashboard URL',
            $jiraUrl !== '',
            $jiraUrl !== '' ? $jiraUrl : 'Set JIRA_BASE_URL in dashboard .env.',
        );

        $checks[] = $this->row(
            'Scheduler',
            (bool) config('ai_agent.schedule_enabled'),
            config('ai_agent.schedule_enabled')
                ? 'Every '.config('ai_agent.schedule_interval_minutes', 15).' min (needs system cron).'
                : 'Disabled — use manual batch button or enable AI_AGENT_SCHEDULE_ENABLED.',
        );

        $required = ['Python agent project', 'Python credentials (.env)', 'GitHub target', 'Jira dashboard URL'];
        $ready = collect($checks)
            ->filter(fn (array $c) => in_array($c['label'], $required, true))
            ->every(fn (array $c) => $c['ok']);

        return ['ready' => $ready, 'checks' => $checks];
    }

    /**
     * @return array{label: string, ok: bool, detail: string}
     */
    private function row(string $label, bool $ok, string $detail): array
    {
        return ['label' => $label, 'ok' => $ok, 'detail' => $detail];
    }
}

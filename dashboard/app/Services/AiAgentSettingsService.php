<?php

namespace App\Services;

use App\Support\AiAgentPaths;
use Illuminate\Support\Facades\File;

class AiAgentSettingsService
{
    private const SENSITIVE_FRAGMENTS = [
        'KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL', 'API_KEY',
    ];

    /**
     * @return list<array{key: string, value: string, masked: bool, group: string}>
     */
    public function laravelAgentSettings(): array
    {
        $rows = [
            ['AI_AGENT_PYTHON_PATH', config('ai_agent.python_path'), 'Runtime'],
            ['AI_AGENT_PROJECT_PATH', config('ai_agent.project_path'), 'Runtime'],
            ['AI_AGENT_WORKSPACE_ROOT', config('ai_agent.workspace_root'), 'Runtime'],
            ['AI_AGENT_AUTO_SYNC_REPO', $this->formatBool(config('ai_agent.auto_sync_repo')), 'Runtime'],
            ['AI_AGENT_TIMEOUT', (string) config('ai_agent.default_timeout'), 'Runtime'],
            ['AI_AGENT_JIRA_BATCH_MAX_TASKS', (string) config('ai_agent.jira_batch_max_tasks'), 'Jira batch'],
            ['AI_AGENT_SCHEDULE_ENABLED', $this->formatBool(config('ai_agent.schedule_enabled')), 'Scheduler'],
            ['AI_AGENT_SCHEDULE_INTERVAL_MINUTES', (string) config('ai_agent.schedule_interval_minutes'), 'Scheduler'],
            ['AI_AGENT_SCHEDULE_OVERLAP_MINUTES', (string) config('ai_agent.schedule_overlap_minutes'), 'Scheduler'],
            ['AI_AGENT_REQUIRES_APPROVAL', $this->formatBool(config('ai_agent.requires_approval')), 'Safety'],
            ['GITHUB_OWNER', config('ai_agent.github_owner') ?: '—', 'GitHub'],
            ['GITHUB_REPO', config('ai_agent.github_repo') ?: '—', 'GitHub'],
            ['JIRA_BASE_URL', config('ai_agent.jira_base_url') ?: '—', 'Jira'],
            ['APP_ENV', config('app.env'), 'Laravel'],
            ['APP_DEBUG', $this->formatBool(config('app.debug')), 'Laravel'],
        ];

        return $this->formatRows($rows);
    }

    /**
     * @return array{path: string, exists: bool, rows: list<array{key: string, value: string, masked: bool, group: string}>}
     */
    public function pythonEnvSettings(): array
    {
        $path = rtrim((string) config('ai_agent.project_path'), '/').'/.env';

        if (! is_file($path)) {
            return ['path' => $path, 'exists' => false, 'rows' => []];
        }

        $parsed = $this->parseEnvFile($path);
        $groups = [
            'OPENAI_' => 'OpenAI',
            'GITHUB_' => 'GitHub',
            'JIRA_' => 'Jira',
            'AI_AGENT_' => 'Agent',
        ];

        $rows = [];
        foreach ($parsed as $key => $value) {
            $group = 'General';
            foreach ($groups as $prefix => $label) {
                if (str_starts_with($key, $prefix)) {
                    $group = $label;
                    break;
                }
            }
            $rows[] = [$key, $value, $group];
        }

        return [
            'path' => $path,
            'exists' => true,
            'rows' => $this->formatRows($rows),
        ];
    }

    /**
     * @return array<string, mixed>
     */
    public function integrationSummary(): array
    {
        $workspace = AiAgentPaths::workspaceRepo();

        return [
            'workspace_path' => $workspace,
            'workspace_exists' => is_dir($workspace),
            'github_url' => AiAgentPaths::githubRepoUrl(),
            'github_target' => trim(config('ai_agent.github_owner', '').'/'.AiAgentPaths::normalizeRepoName((string) config('ai_agent.github_repo', ''))),
            'jira_base_url' => config('ai_agent.jira_base_url'),
            'python_main' => rtrim((string) config('ai_agent.project_path'), '/').'/main.py',
            'python_main_exists' => is_file(rtrim((string) config('ai_agent.project_path'), '/').'/main.py'),
        ];
    }

    /**
     * @param  list<array{0: string, 1: string, 2?: string}>  $rows
     * @return list<array{key: string, value: string, masked: bool, group: string}>
     */
    private function formatRows(array $rows): array
    {
        $out = [];
        foreach ($rows as $row) {
            $key = $row[0];
            $raw = (string) $row[1];
            $group = $row[2] ?? 'General';
            $masked = $this->isSensitiveKey($key);
            $out[] = [
                'key' => $key,
                'value' => $masked ? $this->maskValue($raw) : ($raw !== '' ? $raw : '(empty)'),
                'masked' => $masked,
                'group' => $group,
            ];
        }

        return $out;
    }

    /**
     * @return array<string, string>
     */
    private function parseEnvFile(string $path): array
    {
        $vars = [];
        $lines = File::lines($path);
        foreach ($lines as $line) {
            $line = trim((string) $line);
            if ($line === '' || str_starts_with($line, '#')) {
                continue;
            }
            if (! str_contains($line, '=')) {
                continue;
            }
            [$key, $value] = explode('=', $line, 2);
            $key = trim($key);
            $value = trim($value);
            if (
                (str_starts_with($value, '"') && str_ends_with($value, '"'))
                || (str_starts_with($value, "'") && str_ends_with($value, "'"))
            ) {
                $value = substr($value, 1, -1);
            }
            $vars[$key] = $value;
        }

        ksort($vars);

        return $vars;
    }

    private function isSensitiveKey(string $key): bool
    {
        $upper = strtoupper($key);
        foreach (self::SENSITIVE_FRAGMENTS as $fragment) {
            if (str_contains($upper, $fragment)) {
                return true;
            }
        }

        return false;
    }

    private function maskValue(string $value): string
    {
        if ($value === '') {
            return '(empty)';
        }
        if (strlen($value) <= 10) {
            return str_repeat('•', 12);
        }

        return substr($value, 0, 4).'…'.substr($value, -4).' ('.strlen($value).' chars)';
    }

    private function formatBool(mixed $value): string
    {
        return filter_var($value, FILTER_VALIDATE_BOOLEAN) ? 'true' : 'false';
    }
}

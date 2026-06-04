<?php

return [
    'python_path' => env('AI_AGENT_PYTHON_PATH', 'python3'),
    'project_path' => env('AI_AGENT_PROJECT_PATH', dirname(base_path())),
    'workspace_root' => env(
        'AI_AGENT_WORKSPACE_ROOT',
        dirname(base_path()).'/../workspaces',
    ),
    'github_owner' => env('GITHUB_OWNER', ''),
    'github_repo' => env('GITHUB_REPO', ''),
    'auto_sync_repo' => env('AI_AGENT_AUTO_SYNC_REPO', true),
    'default_timeout' => (int) env('AI_AGENT_TIMEOUT', 7200),
    'jira_batch_max_tasks' => (int) env('AI_AGENT_JIRA_BATCH_MAX_TASKS', 1),
    'schedule_enabled' => env('AI_AGENT_SCHEDULE_ENABLED', true),
    'schedule_interval_minutes' => (int) env('AI_AGENT_SCHEDULE_INTERVAL_MINUTES', 15),
    'schedule_overlap_minutes' => (int) env('AI_AGENT_SCHEDULE_OVERLAP_MINUTES', 180),
    'requires_approval' => env('AI_AGENT_REQUIRES_APPROVAL', false),
    'jira_base_url' => env('JIRA_BASE_URL', ''),
    'high_risk_keywords' => [
        'payment', 'auth', 'login', 'password', 'permission',
        'security', 'migration', 'production', 'secret', 'token',
    ],
];

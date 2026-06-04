<?php

namespace App\Support;

class AiAgentPaths
{
    /**
     * Standard workspace repo path: {project}/workspaces/{owner}/{repo}
     * Matches Python tools/repo_sync.py resolve_workspace_path().
     */
    public static function workspaceRepo(): string
    {
        $root = rtrim((string) config('ai_agent.workspace_root'), '/');
        $owner = trim((string) config('ai_agent.github_owner', ''));
        $repo = trim((string) config('ai_agent.github_repo', ''));
        $repo = self::normalizeRepoName($repo);

        if ($owner === '' || $repo === '') {
            return $root;
        }

        return "{$root}/{$owner}/{$repo}";
    }

    public static function githubRepoUrl(): ?string
    {
        $owner = trim((string) config('ai_agent.github_owner', ''));
        $repo = trim((string) config('ai_agent.github_repo', ''));
        if ($owner === '' || $repo === '') {
            return null;
        }

        return 'https://github.com/'.$owner.'/'.self::normalizeRepoName($repo);
    }

    public static function normalizeRepoName(string $repo): string
    {
        $repo = trim($repo, '/');
        if (preg_match('#github\.com/[^/]+/([^/]+)#', $repo, $m)) {
            return $m[1];
        }
        if (str_contains($repo, '/')) {
            return basename($repo);
        }

        return $repo;
    }
}

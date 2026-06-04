<?php

namespace App\Services;

use App\Support\AiAgentPaths;
use Symfony\Component\Process\Process;

class AiAgentRepositoryService
{
    public function ensureSynced(?string $repoPath = null): string
    {
        if (! config('ai_agent.auto_sync_repo', true)) {
            $repoPath = $repoPath ?: AiAgentPaths::workspaceRepo();
            if (! is_dir($repoPath)) {
                throw new \RuntimeException(
                    'Workspace repo not found at '.$repoPath
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
}

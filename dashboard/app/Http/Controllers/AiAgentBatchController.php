<?php

namespace App\Http\Controllers;

use App\Services\AiAgentBatchService;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

class AiAgentBatchController extends Controller
{
    public function __construct(
        private readonly AiAgentBatchService $batchService,
    ) {}

    public function runJiraBatch(Request $request): RedirectResponse
    {
        $repoPath = $request->input('repo_path');

        try {
            $result = $this->batchService->runJiraBatch($repoPath, 'manual');

            if (! empty($result['running'])) {
                return redirect()
                    ->route('ai-agent.tasks.index')
                    ->with('success', 'Jira batch started. Pipeline status updates live below.');
            }

            return redirect()
                ->route('ai-agent.dashboard')
                ->with('success', sprintf(
                    'Jira batch finished: %d PR created, %d failed, %d skipped (of %d).',
                    $result['pr_created'],
                    $result['failed'],
                    $result['skipped'],
                    $result['total'],
                ));
        } catch (\Throwable $e) {
            return redirect()
                ->route('ai-agent.dashboard')
                ->with('error', $e->getMessage());
        }
    }
}

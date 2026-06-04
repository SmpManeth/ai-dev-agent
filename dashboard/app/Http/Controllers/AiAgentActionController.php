<?php

namespace App\Http\Controllers;

use App\Enums\AiAgentTaskStatus;
use App\Models\AiAgentTask;
use App\Services\AiAgentLogService;
use App\Services\AiAgentPipelineSyncService;
use App\Services\AiAgentProcessService;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

class AiAgentActionController extends Controller
{
    public function __construct(
        private readonly AiAgentProcessService $processService,
        private readonly AiAgentLogService $logService,
        private readonly AiAgentPipelineSyncService $pipelineSync,
    ) {}

    public function stop(AiAgentTask $task): RedirectResponse
    {
        $this->pipelineSync->markTaskStopped($task);
        $this->logService->log($task, 'Task marked as stopped from dashboard', 'warning', 'control');

        return back()->with('success', 'Task marked as stopped.');
    }

    public function approve(AiAgentTask $task): RedirectResponse
    {
        if ($task->status === AiAgentTaskStatus::Rejected) {
            return back()->with('error', 'Rejected tasks cannot be approved.');
        }

        $task->update(['status' => AiAgentTaskStatus::Approved]);
        $this->logService->log($task, 'Task approved by operator', 'info', 'approval');

        return back()->with('success', 'Task approved. You may run the agent when ready.');
    }

    public function reject(Request $request, AiAgentTask $task): RedirectResponse
    {
        $request->validate(['reason' => 'nullable|string|max:2000']);

        $task->update([
            'status' => AiAgentTaskStatus::Rejected,
            'error_message' => $request->input('reason', 'Rejected by operator'),
            'completed_at' => now(),
        ]);
        $this->logService->log($task, 'Task rejected', 'warning', 'approval', [
            'reason' => $request->input('reason'),
        ]);

        return redirect()
            ->route('ai-agent.tasks.index')
            ->with('success', 'Task rejected.');
    }

    public function retry(AiAgentTask $task): RedirectResponse
    {
        if (! in_array($task->status, [AiAgentTaskStatus::Failed, AiAgentTaskStatus::TestsFailed], true)) {
            return back()->with('error', 'Only failed tasks can be retried.');
        }

        $task->update([
            'status' => ($task->isHighRisk() || config('ai_agent.requires_approval'))
                ? AiAgentTaskStatus::Approved
                : AiAgentTaskStatus::Pending,
            'error_message' => null,
            'completed_at' => null,
        ]);
        $this->logService->log($task, 'Task queued for retry', 'info', 'retry');

        return back()->with('success', 'Task reset for retry. Approve and run when ready.');
    }

    public function run(AiAgentTask $task): RedirectResponse
    {
        try {
            if ($task->requiresApprovalBeforeRun()) {
                return back()->with('error', 'Approve the task before running the agent.');
            }

            if ($task->isHighRisk() && $task->status !== AiAgentTaskStatus::Approved) {
                return back()->with('error', 'High-risk tasks must be approved before running.');
            }

            $this->processService->run($task);

            return back()->with('success', 'Agent started. Watch the pipeline progress below.');
        } catch (\Throwable $e) {
            $this->logService->log($task, $e->getMessage(), 'error', 'run');
            $task->update([
                'status' => AiAgentTaskStatus::Failed,
                'error_message' => $e->getMessage(),
                'completed_at' => now(),
            ]);

            return back()->with('error', $e->getMessage());
        }
    }
}

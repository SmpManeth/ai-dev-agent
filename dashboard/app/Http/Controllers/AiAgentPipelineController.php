<?php

namespace App\Http\Controllers;

use App\Models\AiAgentTask;
use App\Services\AiAgentBatchService;
use App\Services\AiAgentPipelineSyncService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class AiAgentPipelineController extends Controller
{
    public function __construct(
        private readonly AiAgentPipelineSyncService $pipelineSync,
        private readonly AiAgentBatchService $batchService,
    ) {}

    public function sync(Request $request): JsonResponse
    {
        $this->batchService->tickBackgroundJobs();
        $reconciled = $this->pipelineSync->reconcileAbandonedRuns();
        $synced = $this->pipelineSync->syncAllProgressFiles();

        $ids = array_filter(array_map('intval', explode(',', $request->string('ids'))));

        $query = AiAgentTask::query()
            ->when($ids !== [], fn ($q) => $q->whereIn('id', $ids))
            ->when($ids === [], function ($q) {
                $q->where(function ($inner) {
                    $inner->where('pipeline_terminal', false)
                        ->where('pipeline_phase', '!=', 'not_started')
                        ->orWhere('status', 'running');
                });
            })
            ->orderByDesc('pipeline_updated_at')
            ->orderByDesc('updated_at')
            ->limit($request->integer('limit', 50));

        $tasks = $query->get()->map(fn (AiAgentTask $task) => $this->batchService->pipelinePayload($task));

        $scheduler = $this->batchService->getSchedulerState();

        return response()->json([
            'synced_files' => $synced,
            'reconciled_stale' => $reconciled,
            'scheduler_running' => (bool) ($scheduler['running'] ?? false),
            'tasks' => $tasks,
        ]);
    }

    public function show(AiAgentTask $task): JsonResponse
    {
        if ($task->jira_issue_key) {
            $path = $this->pipelineSync->progressDirectory().'/'.str_replace('/', '_', $task->jira_issue_key).'.json';
            $this->pipelineSync->syncProgressFile($path);
            $task->refresh();
        }

        return response()->json($this->batchService->pipelinePayload($task));
    }
}

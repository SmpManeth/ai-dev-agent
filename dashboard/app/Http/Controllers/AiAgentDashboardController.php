<?php

namespace App\Http\Controllers;

use App\Services\AiAgentBatchService;
use App\Services\AiAgentDashboardService;
use App\Services\AiAgentPipelineSyncService;
use Illuminate\View\View;

class AiAgentDashboardController extends Controller
{
    public function __construct(
        private readonly AiAgentDashboardService $dashboardService,
        private readonly AiAgentBatchService $batchService,
        private readonly AiAgentPipelineSyncService $pipelineSync,
    ) {}

    public function index(): View
    {
        $this->batchService->tickBackgroundJobs();
        $this->pipelineSync->reconcileAbandonedRuns();

        return view('ai-agent.dashboard.index', [
            'overview' => $this->dashboardService->overview(),
        ]);
    }
}

<?php

namespace App\Http\Controllers;

use App\Services\AiAgentBatchService;
use App\Services\AiAgentHealthService;
use App\Services\AiAgentSettingsService;
use Illuminate\Http\Request;
use Illuminate\View\View;

class AiAgentSettingsController extends Controller
{
    public function __construct(
        private readonly AiAgentSettingsService $settingsService,
        private readonly AiAgentHealthService $healthService,
        private readonly AiAgentBatchService $batchService,
    ) {}

    public function index(Request $request): View
    {
        $section = $request->query('section', 'runtime');
        $allowed = ['runtime', 'integrations', 'scheduler', 'python-env', 'security'];
        if (! in_array($section, $allowed, true)) {
            $section = 'runtime';
        }

        return view('ai-agent.settings.index', [
            'section' => $section,
            'laravelSettings' => $this->settingsService->laravelAgentSettings(),
            'pythonEnv' => $this->settingsService->pythonEnvSettings(),
            'integrations' => $this->settingsService->integrationSummary(),
            'health' => $this->healthService->check(),
            'scheduler' => $this->batchService->getSchedulerState(),
        ]);
    }
}

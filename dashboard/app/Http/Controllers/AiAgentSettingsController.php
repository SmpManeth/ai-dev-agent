<?php

namespace App\Http\Controllers;

use App\Services\AiAgentBatchService;
use App\Services\AiAgentHardeningService;
use App\Services\AiAgentHealthService;
use App\Services\AiAgentSettingsService;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

class AiAgentSettingsController extends Controller
{
    public function __construct(
        private readonly AiAgentSettingsService $settingsService,
        private readonly AiAgentHealthService $healthService,
        private readonly AiAgentBatchService $batchService,
        private readonly AiAgentHardeningService $hardeningService,
    ) {}

    public function index(Request $request): View
    {
        $section = $request->query('section', 'runtime');
        $allowed = ['runtime', 'integrations', 'scheduler', 'python-env', 'security', 'production'];
        if (! in_array($section, $allowed, true)) {
            $section = 'runtime';
        }

        $hardening = $this->hardeningService->current();

        return view('ai-agent.settings.index', [
            'section' => $section,
            'laravelSettings' => $this->settingsService->laravelAgentSettings(),
            'pythonEnv' => $this->settingsService->pythonEnvSettings(),
            'integrations' => $this->settingsService->integrationSummary(),
            'health' => $this->healthService->check(),
            'scheduler' => $this->batchService->getSchedulerState(),
            'hardening' => $hardening,
            'hardeningPath' => $this->hardeningService->hardeningConfigPath(),
        ]);
    }

    public function updateHardening(Request $request): RedirectResponse
    {
        $this->hardeningService->save($request->all());

        return redirect()
            ->route('ai-agent.settings', ['section' => 'production'])
            ->with('status', 'Production hardening settings saved.');
    }
}

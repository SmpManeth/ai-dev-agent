<?php

namespace App\Http\Controllers;

use App\Models\AiAgentTask;
use App\Services\AiAgentBatchService;
use App\Services\AiAgentHealthService;
use Illuminate\Http\Request;
use Illuminate\View\View;

class AiAgentTaskController extends Controller
{
    public function __construct(
        private readonly AiAgentBatchService $batchService,
        private readonly AiAgentHealthService $healthService,
    ) {}

    public function index(Request $request): View
    {
        $scheduler = $this->batchService->getSchedulerState();
        $health = $this->healthService->check();
        $githubUrl = \App\Support\AiAgentPaths::githubRepoUrl();

        $tasks = AiAgentTask::query()
            ->when($request->filled('status'), fn ($q) => $q->where('status', $request->string('status')))
            ->when($request->filled('q'), function ($q) use ($request) {
                $term = '%'.$request->string('q').'%';
                $q->where(function ($inner) use ($term) {
                    $inner->where('jira_issue_key', 'like', $term)
                        ->orWhere('task_description', 'like', $term)
                        ->orWhere('repo_path', 'like', $term);
                });
            })
            ->latest()
            ->paginate(20)
            ->withQueryString();

        return view('ai-agent.tasks.index', compact('tasks', 'scheduler', 'health', 'githubUrl'));
    }

    public function show(AiAgentTask $task): View
    {
        $task->load('logs');

        return view('ai-agent.tasks.show', compact('task'));
    }
}

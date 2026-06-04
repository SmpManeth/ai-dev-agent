@extends('layouts.ai-agent')

@section('title', 'Task #'.$task->id)

@section('content')
    <div class="mb-4">
        <a href="{{ route('ai-agent.tasks.index') }}" class="text-sm text-indigo-600 hover:text-indigo-800">← All tasks</a>
    </div>

    <div class="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
            <h1 class="text-2xl font-bold">Task #{{ $task->id }}</h1>
            <p class="text-slate-600 mt-1 max-w-2xl">{{ $task->task_description }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
            @if ($task->needsManualApproval())
                <form method="post" action="{{ route('ai-agent.tasks.approve', $task) }}">
                    @csrf
                    <button type="submit" class="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700">
                        Approve
                    </button>
                </form>
            @endif

            @if ($task->canRun())
                <form method="post" action="{{ route('ai-agent.tasks.run', $task) }}"
                      onsubmit="return confirm('Run the Python agent for this task?');">
                    @csrf
                    <button type="submit" class="rounded-lg bg-indigo-600 text-white px-4 py-2 text-sm font-medium hover:bg-indigo-700">
                        Run Agent
                    </button>
                </form>
            @endif

            @if (in_array($task->status, [\App\Enums\AiAgentTaskStatus::Failed, \App\Enums\AiAgentTaskStatus::TestsFailed]))
                <form method="post" action="{{ route('ai-agent.tasks.retry', $task) }}">
                    @csrf
                    <button type="submit" class="rounded-lg bg-amber-600 text-white px-4 py-2 text-sm font-medium hover:bg-amber-700">
                        Retry
                    </button>
                </form>
            @endif

            @if ($task->status !== \App\Enums\AiAgentTaskStatus::Rejected)
                <form method="post" action="{{ route('ai-agent.tasks.reject', $task) }}"
                      onsubmit="return confirm('Reject this task?');">
                    @csrf
                    <button type="submit" class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50">
                        Reject
                    </button>
                </form>
            @endif

            @if ($task->pr_url)
                <a href="{{ $task->pr_url }}" target="_blank" rel="noopener"
                   class="rounded-lg bg-slate-800 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700">
                    Open PR
                </a>
            @endif

            @if ($task->jira_url)
                <a href="{{ $task->jira_url }}" target="_blank" rel="noopener"
                   class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50">
                    Open Jira
                </a>
            @endif
        </div>
    </div>

    @if ($task->isHighRisk() && $task->status === \App\Enums\AiAgentTaskStatus::Pending)
        <div class="mb-6 rounded-lg bg-red-50 border border-red-200 text-red-800 px-4 py-3 text-sm">
            High-risk task: approval required before the agent can run. PR creation is never auto-merged.
        </div>
    @endif

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div class="bg-white rounded-xl shadow border border-slate-200 p-5 space-y-3 text-sm">
            <h2 class="font-semibold text-slate-800">Overview</h2>
            <dl class="grid grid-cols-3 gap-2">
                <dt class="text-slate-500">Status</dt>
                <dd class="col-span-2">
                    <span class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium {{ $task->status->badgeColor() }}">
                        {{ ucwords($task->status->label()) }}
                    </span>
                </dd>
                <dt class="text-slate-500">Risk</dt>
                <dd class="col-span-2">@include('ai-agent.partials.risk-badge', ['risk' => $task->risk_level])</dd>
                <dt class="text-slate-500">Validation</dt>
                <dd class="col-span-2">{{ $task->validation_status ?? '—' }}</dd>
                <dt class="text-slate-500">Branch</dt>
                <dd class="col-span-2 font-mono text-xs">{{ $task->branch_name ?? '—' }}</dd>
                <dt class="text-slate-500">Repo</dt>
                <dd class="col-span-2 font-mono text-xs break-all">{{ $task->repo_path }}</dd>
                @if ($task->repo_url)
                    <dt class="text-slate-500">Repo URL</dt>
                    <dd class="col-span-2"><a href="{{ $task->repo_url }}" class="text-indigo-600 break-all" target="_blank">{{ $task->repo_url }}</a></dd>
                @endif
                <dt class="text-slate-500">Started</dt>
                <dd class="col-span-2">{{ $task->started_at?->toDateTimeString() ?? '—' }}</dd>
                <dt class="text-slate-500">Completed</dt>
                <dd class="col-span-2">{{ $task->completed_at?->toDateTimeString() ?? '—' }}</dd>
            </dl>
        </div>

        <div class="bg-white rounded-xl shadow border border-slate-200 p-5 space-y-3 text-sm">
            <h2 class="font-semibold text-slate-800">Integrations</h2>
            <dl class="grid grid-cols-3 gap-2">
                <dt class="text-slate-500">Jira</dt>
                <dd class="col-span-2">
                    @if ($task->jira_issue_key)
                        <span class="font-medium">{{ $task->jira_issue_key }}</span>
                        @if ($task->jira_summary)
                            <span class="text-slate-600">— {{ $task->jira_summary }}</span>
                        @endif
                    @else
                        —
                    @endif
                </dd>
                <dt class="text-slate-500">PR</dt>
                <dd class="col-span-2">
                    @if ($task->pr_url)
                        <a href="{{ $task->pr_url }}" target="_blank" class="text-indigo-600">
                            #{{ $task->pr_number ?? '?' }}
                        </a>
                    @else
                        —
                    @endif
                </dd>
            </dl>
        </div>
    </div>

    @if ($task->error_message)
        <div class="mb-6 rounded-lg bg-red-50 border border-red-200 p-4">
            <h2 class="font-semibold text-red-800 text-sm mb-2">Error</h2>
            <pre class="text-xs text-red-900 whitespace-pre-wrap">{{ $task->error_message }}</pre>
        </div>
    @endif

    <div class="bg-white rounded-xl shadow border border-slate-200 p-5 mb-8">
        <h2 class="font-semibold text-slate-800 mb-3">Changed files</h2>
        @if (!empty($task->changed_files))
            <ul class="list-disc list-inside text-sm text-slate-700 space-y-1">
                @foreach ($task->changed_files as $file)
                    <li class="font-mono text-xs">{{ is_string($file) ? $file : json_encode($file) }}</li>
                @endforeach
            </ul>
        @else
            <p class="text-sm text-slate-500">No changed files recorded yet.</p>
        @endif
    </div>

    @if ($task->logs_path)
        <div class="mb-6 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
            <span class="text-slate-600">Full agent log:</span>
            <code class="block text-xs mt-1 break-all text-slate-800">{{ $task->logs_path }}</code>
        </div>
    @endif

    <div class="bg-white rounded-xl shadow border border-slate-200 p-5">
        <h2 class="font-semibold text-slate-800 mb-4">Execution timeline</h2>
        <div class="space-y-3 max-h-[32rem] overflow-y-auto">
            @forelse ($task->logs as $log)
                <div class="flex gap-3 text-sm border-l-2 pl-3
                    {{ $log->level === 'error' ? 'border-red-400' : ($log->level === 'warning' ? 'border-amber-400' : 'border-slate-200') }}">
                    <time class="text-xs text-slate-400 shrink-0 w-36">
                        {{ $log->created_at?->format('Y-m-d H:i:s') }}
                    </time>
                    <div class="min-w-0 flex-1">
                        @if ($log->step)
                            <span class="text-xs font-medium text-indigo-600">{{ $log->step }}</span>
                        @endif
                        <p class="text-slate-700 break-words font-mono text-xs">{{ $log->message }}</p>
                    </div>
                </div>
            @empty
                <p class="text-sm text-slate-500">No logs yet.</p>
            @endforelse
        </div>
    </div>
@endsection

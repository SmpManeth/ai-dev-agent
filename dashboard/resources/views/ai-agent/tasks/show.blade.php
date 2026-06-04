@extends('layouts.ai-agent')

@section('title', $task->jira_issue_key ?? 'Task #'.$task->id)
@section('page_title', $task->jira_issue_key ?? 'Task #'.$task->id)

@section('header_actions')
    <div class="flex flex-wrap gap-2">
        @if ($task->needsManualApproval())
            <form method="post" action="{{ route('ai-agent.tasks.approve', $task) }}">@csrf
                <button type="submit" class="rounded-lg bg-blue-600 text-white px-3 py-2 text-sm font-medium hover:bg-blue-700">Approve</button>
            </form>
        @endif
        @if ($task->isPipelineActive())
            <form method="post" action="{{ route('ai-agent.tasks.stop', $task) }}" onsubmit="return confirm('Mark this task as stopped?');">@csrf
                <button type="submit" class="rounded-lg bg-red-600 text-white px-3 py-2 text-sm font-medium hover:bg-red-700">Mark stopped</button>
            </form>
        @endif
        @if ($task->canRun())
            <form method="post" action="{{ route('ai-agent.tasks.run', $task) }}" onsubmit="return confirm('Run agent for this task?');">@csrf
                <button type="submit" class="rounded-lg bg-slate-900 text-white px-3 py-2 text-sm font-medium hover:bg-slate-800">Run agent</button>
            </form>
        @endif
        @if (in_array($task->status, [\App\Enums\AiAgentTaskStatus::Failed, \App\Enums\AiAgentTaskStatus::TestsFailed]))
            <form method="post" action="{{ route('ai-agent.tasks.retry', $task) }}">@csrf
                <button type="submit" class="rounded-lg bg-amber-600 text-white px-3 py-2 text-sm font-medium hover:bg-amber-700">Retry</button>
            </form>
        @endif
        @if ($task->pr_url)
            <a href="{{ $task->pr_url }}" target="_blank" class="rounded-lg ring-1 ring-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50">Pull request</a>
        @endif
        @if ($task->jira_url)
            <a href="{{ $task->jira_url }}" target="_blank" class="rounded-lg ring-1 ring-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50">Jira</a>
        @endif
    </div>
@endsection

@section('content')
    <nav class="text-sm text-slate-500 mb-6">
        <a href="{{ route('ai-agent.tasks.index') }}" class="hover:text-slate-800">Tasks</a>
        <span class="mx-2">/</span>
        <span class="text-slate-800 font-medium">{{ $task->jira_issue_key ?? '#'.$task->id }}</span>
    </nav>

    @if ($task->isHighRisk() && $task->status === \App\Enums\AiAgentTaskStatus::Pending)
        <div class="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
            High-risk classification — manual approval required. Draft PRs are never auto-merged.
        </div>
    @endif

    <p class="text-sm text-slate-600 mb-6 max-w-3xl leading-relaxed">{{ $task->task_description }}</p>

    @include('ai-agent.partials.pipeline-card', ['task' => $task])

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div class="lg:col-span-2 rounded-xl bg-white ring-1 ring-slate-200 p-5 shadow-sm">
            <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">Run metadata</h2>
            <dl class="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-4 text-sm">
                <div>
                    <dt class="text-slate-500 text-xs">Status</dt>
                    <dd class="mt-1">
                        <span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium {{ $task->status->badgeColor() }}">
                            {{ ucwords($task->status->label()) }}
                        </span>
                    </dd>
                </div>
                <div>
                    <dt class="text-slate-500 text-xs">Risk</dt>
                    <dd class="mt-1">@include('ai-agent.partials.risk-badge', ['risk' => $task->risk_level])</dd>
                </div>
                <div>
                    <dt class="text-slate-500 text-xs">Validation</dt>
                    <dd class="mt-1 font-medium text-slate-800">{{ $task->validation_status ?? '—' }}</dd>
                </div>
                <div>
                    <dt class="text-slate-500 text-xs">Branch</dt>
                    <dd class="mt-1 font-mono text-xs text-slate-800">{{ $task->branch_name ?? '—' }}</dd>
                </div>
                <div>
                    <dt class="text-slate-500 text-xs">Started</dt>
                    <dd class="mt-1 text-slate-800">{{ $task->started_at?->toDateTimeString() ?? '—' }}</dd>
                </div>
                <div>
                    <dt class="text-slate-500 text-xs">Completed</dt>
                    <dd class="mt-1 text-slate-800">{{ $task->completed_at?->toDateTimeString() ?? '—' }}</dd>
                </div>
                <div class="col-span-2 sm:col-span-3">
                    <dt class="text-slate-500 text-xs">Repository path</dt>
                    <dd class="mt-1 font-mono text-xs text-slate-700 break-all">{{ $task->repo_path }}</dd>
                </div>
            </dl>
        </div>

        <div class="rounded-xl bg-white ring-1 ring-slate-200 p-5 shadow-sm">
            <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">Actions</h2>
            @if ($task->status !== \App\Enums\AiAgentTaskStatus::Rejected)
                <form method="post" action="{{ route('ai-agent.tasks.reject', $task) }}" onsubmit="return confirm('Reject this task?');" class="mb-3">@csrf
                    <button type="submit" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">Reject task</button>
                </form>
            @endif
            @if ($task->logs_path)
                <p class="text-xs text-slate-500 mt-4">Full log file</p>
                <code class="block mt-1 text-[10px] font-mono text-slate-700 break-all leading-relaxed">{{ $task->logs_path }}</code>
            @endif
        </div>
    </div>

    @if ($task->error_message)
        <div class="mb-6 rounded-xl border border-red-200 bg-red-50/50 p-5">
            <h2 class="text-xs font-semibold text-red-800 uppercase tracking-wide mb-2">Failure detail</h2>
            <pre class="text-xs text-red-950 whitespace-pre-wrap font-mono leading-relaxed">{{ $task->error_message }}</pre>
        </div>
    @endif

    @if (!empty($task->changed_files))
        <div class="mb-6 rounded-xl bg-white ring-1 ring-slate-200 p-5 shadow-sm">
            <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Changed files</h2>
            <ul class="grid sm:grid-cols-2 gap-1 font-mono text-xs text-slate-700">
                @foreach ($task->changed_files as $file)
                    <li class="bg-slate-50 rounded px-2 py-1">{{ is_string($file) ? $file : json_encode($file) }}</li>
                @endforeach
            </ul>
        </div>
    @endif

    <div class="rounded-xl bg-white ring-1 ring-slate-200 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-100">
            <h2 class="text-sm font-semibold text-slate-900">Execution timeline</h2>
        </div>
        <div class="divide-y divide-slate-100 max-h-[28rem] overflow-y-auto">
            @forelse ($task->logs as $log)
                <div class="px-5 py-3 flex gap-4 text-sm hover:bg-slate-50/50">
                    <time class="text-xs text-slate-400 shrink-0 w-36 font-mono">{{ $log->created_at?->format('Y-m-d H:i:s') }}</time>
                    <div class="min-w-0 flex-1">
                        @if ($log->step)
                            <span class="text-[10px] font-semibold uppercase tracking-wide text-blue-600">{{ $log->step }}</span>
                        @endif
                        <p class="text-xs text-slate-700 break-words font-mono mt-0.5">{{ $log->message }}</p>
                    </div>
                    <span class="text-[10px] uppercase font-medium shrink-0 {{ $log->level === 'error' ? 'text-red-600' : ($log->level === 'warning' ? 'text-amber-600' : 'text-slate-400') }}">{{ $log->level }}</span>
                </div>
            @empty
                <p class="px-5 py-10 text-sm text-slate-500 text-center">No execution logs captured.</p>
            @endforelse
        </div>
    </div>

    @include('ai-agent.partials.pipeline-poll', ['task' => $task, 'scheduler' => ['running' => $task->isPipelineActive()]])
@endsection

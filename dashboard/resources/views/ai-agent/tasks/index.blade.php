@extends('layouts.ai-agent')

@section('title', 'Tasks')
@section('page_title', 'Task Registry')

@section('header_actions')
    <form method="post" action="{{ route('ai-agent.jira-batch.run') }}"
          onsubmit="return confirm('Run Jira ai-fix batch now?');">
        @csrf
        <button type="submit"
                class="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800 transition disabled:opacity-50"
                @disabled(!($health['ready'] ?? false))>
            Sync &amp; run batch
        </button>
    </form>
@endsection

@section('content')
    <form method="get" class="mb-6 flex flex-wrap gap-3 items-end bg-white rounded-xl ring-1 ring-slate-200 p-4 shadow-sm">
        <div class="flex-1 min-w-[200px]">
            <label class="block text-xs font-medium text-slate-500 mb-1">Search</label>
            <input type="text" name="q" value="{{ request('q') }}"
                   class="w-full rounded-lg border-slate-300 text-sm focus:border-blue-500 focus:ring-blue-500"
                   placeholder="Jira key, description, repo…">
        </div>
        <div class="w-44">
            <label class="block text-xs font-medium text-slate-500 mb-1">Status</label>
            <select name="status" class="w-full rounded-lg border-slate-300 text-sm">
                <option value="">All statuses</option>
                @foreach (\App\Enums\AiAgentTaskStatus::cases() as $s)
                    <option value="{{ $s->value }}" @selected(request('status') === $s->value)>
                        {{ ucwords($s->label()) }}
                    </option>
                @endforeach
            </select>
        </div>
        <button type="submit" class="rounded-lg bg-white ring-1 ring-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Apply filters
        </button>
    </form>

    <div class="rounded-xl bg-white ring-1 ring-slate-200 shadow-sm overflow-hidden">
        <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                <tr>
                    <th class="px-5 py-3">ID</th>
                    <th class="px-5 py-3">Jira issue</th>
                    <th class="px-5 py-3">Repository</th>
                    <th class="px-5 py-3">Pipeline</th>
                    <th class="px-5 py-3">Outcome</th>
                    <th class="px-5 py-3">Risk</th>
                    <th class="px-5 py-3">Validation</th>
                    <th class="px-5 py-3">Last update</th>
                    <th class="px-5 py-3"></th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
                @forelse ($tasks as $task)
                    <tr class="hover:bg-slate-50/80 transition">
                        <td class="px-5 py-3.5 font-mono text-xs text-slate-500">#{{ $task->id }}</td>
                        <td class="px-5 py-3.5">
                            @if ($task->jira_issue_key)
                                <span class="font-semibold text-slate-900">{{ $task->jira_issue_key }}</span>
                                @if ($task->jira_summary)
                                    <p class="text-xs text-slate-500 truncate max-w-xs" title="{{ $task->jira_summary }}">{{ $task->jira_summary }}</p>
                                @endif
                            @else
                                <span class="text-slate-400">—</span>
                            @endif
                        </td>
                        <td class="px-5 py-3.5 font-mono text-xs text-slate-600 max-w-[8rem] truncate" title="{{ $task->repo_path }}">
                            {{ basename($task->repo_path) }}
                        </td>
                        <td class="px-5 py-3.5 min-w-[10rem]">
                            @include('ai-agent.partials.pipeline-badge', ['task' => $task])
                        </td>
                        <td class="px-5 py-3.5">
                            <span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium {{ $task->status->badgeColor() }}"
                                  data-task-status data-task-id="{{ $task->id }}">
                                {{ ucwords($task->status->label()) }}
                            </span>
                        </td>
                        <td class="px-5 py-3.5">@include('ai-agent.partials.risk-badge', ['risk' => $task->risk_level])</td>
                        <td class="px-5 py-3.5 text-slate-600 text-xs">{{ $task->validation_status ?? '—' }}</td>
                        <td class="px-5 py-3.5 text-slate-500 text-xs">{{ $task->updated_at->diffForHumans() }}</td>
                        <td class="px-5 py-3.5 text-right">
                            <a href="{{ route('ai-agent.tasks.show', $task) }}"
                               class="text-sm font-medium text-blue-600 hover:text-blue-800">Open</a>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="9" class="px-5 py-16 text-center">
                            <p class="text-slate-600 font-medium">No tasks recorded</p>
                            <p class="text-sm text-slate-500 mt-1 max-w-md mx-auto">
                                Jira issues labeled <code class="text-xs bg-slate-100 px-1 rounded">ai-fix</code> appear here after a batch or scheduled run.
                            </p>
                        </td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    @if ($tasks->hasPages())
        <div class="mt-4">{{ $tasks->links() }}</div>
    @endif

    @include('ai-agent.partials.pipeline-poll', ['tasks' => $tasks, 'scheduler' => $scheduler])
@endsection

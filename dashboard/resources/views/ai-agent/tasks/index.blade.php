@extends('layouts.ai-agent')

@section('title', 'Tasks')

@section('content')
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h1 class="text-2xl font-bold">AI Tasks</h1>
        <form method="post" action="{{ route('ai-agent.jira-batch.run') }}"
              onsubmit="return confirm('Run the Python agent for Jira ai-fix tickets now? One issue per cycle; may take several minutes.');">
            @csrf
            <button type="submit"
                    class="rounded-lg bg-indigo-600 text-white px-5 py-2.5 text-sm font-semibold hover:bg-indigo-700 shadow"
                    @disabled(!($health['ready'] ?? false))>
                Run Jira ai-fix Batch Now
            </button>
        </form>
    </div>

    @include('ai-agent.partials.connection-status')

    <div class="mb-4 rounded-xl border border-slate-200 bg-white p-4 text-sm">
        <h2 class="font-semibold text-slate-800 mb-2">Automatic Jira polling</h2>
        @if (config('ai_agent.schedule_enabled'))
            <p class="text-slate-600">
                Scheduler is <span class="text-green-700 font-medium">ON</span>
                — checks Jira every {{ config('ai_agent.schedule_interval_minutes', 15) }} minutes
                (label <code class="text-xs bg-slate-100 px-1 rounded">ai-fix</code>),
                processes <strong>one</strong> Jira issue per cycle (patch → tests → commit → draft PR → Jira),
                then stops; the next ticket runs on the next cycle.
                Clones/pulls the GitHub repo automatically before each run.
            </p>
            <p class="text-xs text-slate-500 mt-2">
                Requires system cron: <code class="bg-slate-100 px-1 rounded">* * * * * php artisan schedule:run</code>
                in the <code>dashboard</code> folder.
            </p>
        @else
            <p class="text-amber-800">Scheduler is OFF. Set <code>AI_AGENT_SCHEDULE_ENABLED=true</code> in <code>.env</code>.</p>
        @endif
        @if (!empty($scheduler['last_run_at']))
            <p class="text-xs text-slate-500 mt-2">
                Last run: {{ $scheduler['last_run_at'] }}
                @if (!empty($scheduler['last_triggered_by']))
                    ({{ $scheduler['last_triggered_by'] }})
                @endif
                @if (isset($scheduler['last_stats']))
                    — {{ $scheduler['last_stats']['pr_created'] ?? 0 }} PR,
                    {{ $scheduler['last_stats']['failed'] ?? 0 }} failed,
                    {{ $scheduler['last_stats']['skipped'] ?? 0 }} skipped
                @endif
            </p>
        @endif
        @if (!empty($scheduler['running']))
            <p class="text-indigo-700 text-xs mt-1 font-medium">Batch is running now…</p>
        @endif
    </div>

    <p class="text-xs text-slate-500 mb-4">
        Workspace repo:
        <code class="bg-slate-100 px-1 rounded break-all">{{ \App\Support\AiAgentPaths::workspaceRepo() }}</code>
        (from Python <code>.env</code> <code>GITHUB_OWNER</code> / <code>GITHUB_REPO</code>)
        · {{ config('ai_agent.jira_batch_max_tasks', 1) }} issue(s) per scheduler cycle
    </p>

    <form method="get" class="mb-6 flex flex-wrap gap-3 items-end">
        <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">Search</label>
            <input type="text" name="q" value="{{ request('q') }}"
                   class="rounded-lg border border-slate-300 px-3 py-2 text-sm w-64"
                   placeholder="Jira key, repo, description…">
        </div>
        <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">Status</label>
            <select name="status" class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">All</option>
                @foreach (\App\Enums\AiAgentTaskStatus::cases() as $s)
                    <option value="{{ $s->value }}" @selected(request('status') === $s->value)>
                        {{ ucwords($s->label()) }}
                    </option>
                @endforeach
            </select>
        </div>
        <button type="submit" class="rounded-lg bg-slate-800 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700">
            Filter
        </button>
    </form>

    <div class="bg-white rounded-xl shadow border border-slate-200 overflow-hidden">
        <table class="min-w-full divide-y divide-slate-200 text-sm">
            <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                <tr>
                    <th class="px-4 py-3">ID</th>
                    <th class="px-4 py-3">Jira</th>
                    <th class="px-4 py-3">Repo</th>
                    <th class="px-4 py-3">Status</th>
                    <th class="px-4 py-3">Risk</th>
                    <th class="px-4 py-3">Validation</th>
                    <th class="px-4 py-3">Updated</th>
                    <th class="px-4 py-3"></th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
                @forelse ($tasks as $task)
                    <tr class="hover:bg-slate-50">
                        <td class="px-4 py-3 font-mono text-xs">#{{ $task->id }}</td>
                        <td class="px-4 py-3">
                            @if ($task->jira_issue_key)
                                <span class="font-medium">{{ $task->jira_issue_key }}</span>
                            @else
                                <span class="text-slate-400">—</span>
                            @endif
                        </td>
                        <td class="px-4 py-3 max-w-xs truncate" title="{{ $task->repo_path }}">
                            {{ basename($task->repo_path) }}
                        </td>
                        <td class="px-4 py-3">
                            <span class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium {{ $task->status->badgeColor() }}">
                                {{ ucwords($task->status->label()) }}
                            </span>
                        </td>
                        <td class="px-4 py-3">
                            @include('ai-agent.partials.risk-badge', ['risk' => $task->risk_level])
                        </td>
                        <td class="px-4 py-3 text-slate-600">{{ $task->validation_status ?? '—' }}</td>
                        <td class="px-4 py-3 text-slate-500">{{ $task->updated_at->diffForHumans() }}</td>
                        <td class="px-4 py-3 text-right">
                            <a href="{{ route('ai-agent.tasks.show', $task) }}"
                               class="text-indigo-600 hover:text-indigo-800 font-medium">View</a>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="8" class="px-4 py-8 text-center text-slate-500">
                            No tasks yet. Label Jira issues with
                            <code class="text-xs bg-slate-100 px-1 rounded">ai-fix</code>,
                            then use <strong>Run Jira ai-fix Batch Now</strong> or wait for the scheduler.
                        </td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    <div class="mt-4">{{ $tasks->links() }}</div>
@endsection

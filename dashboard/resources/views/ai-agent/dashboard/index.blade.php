@extends('layouts.ai-agent')

@section('title', 'Overview')
@section('page_title', 'Operations Overview')

@section('content')
    @php
        $o = $overview;
        $scheduler = $o['scheduler'] ?? [];
        $health = $o['health'] ?? ['ready' => false, 'checks' => []];
    @endphp

    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        @include('ai-agent.partials.stat-card', ['label' => 'Total runs', 'value' => $o['total_tasks'], 'hint' => 'Recorded in control plane'])
        @include('ai-agent.partials.stat-card', ['label' => 'PRs created', 'value' => $o['pr_created'], 'tone' => 'success'])
        @include('ai-agent.partials.stat-card', ['label' => 'Failed', 'value' => $o['failed'], 'tone' => 'danger'])
        @include('ai-agent.partials.stat-card', ['label' => 'Awaiting action', 'value' => $o['pending_review'], 'tone' => 'warning'])
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-8">
        <div class="xl:col-span-2 rounded-xl bg-white ring-1 ring-slate-200 shadow-sm p-5">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-sm font-semibold text-slate-900">System health</h2>
                <a href="{{ route('ai-agent.settings', ['section' => 'runtime']) }}" class="text-xs font-medium text-blue-600 hover:text-blue-800">View settings →</a>
            </div>
            <ul class="space-y-2">
                @foreach ($health['checks'] ?? [] as $check)
                    <li class="flex items-start gap-3 text-sm">
                        <span class="mt-1.5 h-2 w-2 rounded-full shrink-0 {{ $check['ok'] ? 'bg-emerald-500' : 'bg-amber-500' }}"></span>
                        <div class="min-w-0">
                            <span class="font-medium text-slate-800">{{ $check['label'] }}</span>
                            <p class="text-xs text-slate-500 break-all">{{ $check['detail'] }}</p>
                        </div>
                    </li>
                @endforeach
            </ul>
        </div>

        <div class="rounded-xl bg-white ring-1 ring-slate-200 shadow-sm p-5">
            <h2 class="text-sm font-semibold text-slate-900 mb-4">Scheduler</h2>
            <dl class="space-y-3 text-sm">
                <div class="flex justify-between gap-2">
                    <dt class="text-slate-500">Status</dt>
                    <dd class="font-medium {{ config('ai_agent.schedule_enabled') ? 'text-emerald-700' : 'text-slate-600' }}">
                        {{ config('ai_agent.schedule_enabled') ? 'Enabled' : 'Disabled' }}
                    </dd>
                </div>
                <div class="flex justify-between gap-2">
                    <dt class="text-slate-500">Interval</dt>
                    <dd class="font-medium text-slate-800">{{ config('ai_agent.schedule_interval_minutes') }} min</dd>
                </div>
                <div class="flex justify-between gap-2">
                    <dt class="text-slate-500">Batch size</dt>
                    <dd class="font-medium text-slate-800">{{ config('ai_agent.jira_batch_max_tasks') }} issue(s)</dd>
                </div>
                @if (!empty($scheduler['last_run_at']))
                    <div>
                        <dt class="text-slate-500 text-xs">Last run</dt>
                        <dd class="font-mono text-xs text-slate-700 mt-0.5">{{ $scheduler['last_run_at'] }}</dd>
                    </div>
                @endif
                @if (!empty($scheduler['running']))
                    <p class="text-xs font-medium text-blue-700">Batch running…</p>
                @endif
            </dl>
            <a href="{{ route('ai-agent.settings', ['section' => 'scheduler']) }}" class="mt-4 inline-block text-xs font-medium text-blue-600 hover:text-blue-800">Scheduler settings →</a>
        </div>
    </div>

    <div class="rounded-xl bg-white ring-1 ring-slate-200 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-slate-900">Recent task activity</h2>
            <a href="{{ route('ai-agent.tasks.index') }}" class="text-xs font-medium text-blue-600 hover:text-blue-800">All tasks →</a>
        </div>
        <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                <tr>
                    <th class="px-5 py-3">Jira</th>
                    <th class="px-5 py-3">Pipeline</th>
                    <th class="px-5 py-3">Updated</th>
                    <th class="px-5 py-3"></th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
                @forelse ($o['recent_tasks'] as $task)
                    <tr class="hover:bg-slate-50">
                        <td class="px-5 py-3 font-medium">{{ $task->jira_issue_key ?? '—' }}</td>
                        <td class="px-5 py-3 min-w-[8rem]">
                            @include('ai-agent.partials.pipeline-badge', ['task' => $task])
                        </td>
                        <td class="px-5 py-3 text-slate-500">{{ $task->updated_at->diffForHumans() }}</td>
                        <td class="px-5 py-3 text-right">
                            <a href="{{ route('ai-agent.tasks.show', $task) }}" class="text-blue-600 hover:text-blue-800 font-medium text-xs">Details</a>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="4" class="px-5 py-10 text-center text-slate-500">
                            No runs yet. Label Jira tickets with <code class="text-xs bg-slate-100 px-1 rounded">ai-fix</code> and run a batch.
                        </td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    @if (!empty($scheduler['running']) || $o['recent_tasks']->contains(fn ($t) => $t->isPipelineActive()))
        @include('ai-agent.partials.pipeline-poll', [
            'pollTaskIds' => $o['recent_tasks']->pluck('id'),
            'scheduler' => $scheduler,
        ])
    @endif
@endsection

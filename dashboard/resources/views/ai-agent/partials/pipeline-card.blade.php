@php
    $steps = \App\Enums\AiAgentPipelinePhase::stepDefinitions();
    $current = $task->pipelinePhaseEnum()->value;
    $stepNum = (int) ($task->pipeline_step ?? 0);
@endphp
<div class="rounded-xl bg-white ring-1 ring-slate-200 p-5 shadow-sm mb-6" id="pipeline-card" data-task-id="{{ $task->id }}">
    <div class="flex items-start justify-between gap-4 mb-4">
        <div>
            <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wide">Live pipeline</h2>
            <p class="text-sm font-medium text-slate-900 mt-1" data-pipeline-label>{{ $task->displayPipelineLabel() }}</p>
        </div>
        <div class="text-right shrink-0">
            @include('ai-agent.partials.pipeline-badge', ['task' => $task])
            <p class="text-[10px] text-slate-400 mt-2" data-pipeline-updated>
                @if ($task->pipeline_updated_at)
                    Updated {{ $task->pipeline_updated_at->diffForHumans() }}
                @endif
            </p>
        </div>
    </div>

    <div class="h-2 rounded-full bg-slate-100 overflow-hidden mb-5">
        <div class="h-full rounded-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-500"
             data-pipeline-bar
             style="width: {{ max(2, (int) $task->pipeline_percent) }}%"></div>
    </div>

    <ol class="grid grid-cols-2 sm:grid-cols-4 gap-2" data-pipeline-steps>
        @foreach ($steps as $def)
            @php
                $done = $stepNum > 0 && array_search($def['phase'], array_column($steps, 'phase')) !== false
                    && array_search($current, array_column($steps, 'phase')) !== false
                    && array_search($def['phase'], array_column($steps, 'phase')) < array_search($current, array_column($steps, 'phase'));
                $isCurrent = $def['phase'] === $current;
                $stepClass = $isCurrent
                    ? 'bg-blue-50 text-blue-800 ring-blue-200'
                    : ($done ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : 'bg-slate-50 text-slate-500 ring-slate-200');
            @endphp
            <li class="rounded-lg px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide ring-1 text-center {{ $stepClass }}"
                data-step-phase="{{ $def['phase'] }}">
                {{ $def['label'] }}
            </li>
        @endforeach
    </ol>

    @if (!empty($task->pipeline_history))
        <details class="mt-4">
            <summary class="text-xs font-medium text-slate-500 cursor-pointer">Phase history</summary>
            <ul class="mt-2 space-y-1 max-h-32 overflow-y-auto" data-pipeline-history>
                @foreach (array_reverse($task->pipeline_history) as $entry)
                    <li class="text-[10px] text-slate-600 font-mono">
                        {{ $entry['label'] ?? $entry['phase'] ?? '' }}
                        @if (!empty($entry['at']))
                            <span class="text-slate-400">· {{ $entry['at'] }}</span>
                        @endif
                    </li>
                @endforeach
            </ul>
        </details>
    @endif
</div>

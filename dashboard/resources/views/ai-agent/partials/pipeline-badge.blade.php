@php
    $phase = $task->pipelinePhaseEnum();
    $active = $task->isPipelineActive();
    $badgeClass = $active ? $phase->badgeColorActive() : $phase->badgeColor();
@endphp
<span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset {{ $badgeClass }}"
      data-pipeline-badge data-task-id="{{ $task->id }}">
    {{ $task->displayPipelineLabel() }}
</span>
@if ($task->pipeline_percent > 0 || $active)
    <div class="mt-1.5 w-full max-w-[12rem]" data-pipeline-bar-wrap data-task-id="{{ $task->id }}">
        <div class="h-1.5 rounded-full bg-slate-100 overflow-hidden">
            <div class="h-full rounded-full bg-blue-500 transition-all duration-500"
                 data-pipeline-bar
                 style="width: {{ (int) $task->pipeline_percent }}%"></div>
        </div>
        <p class="text-[10px] text-slate-500 mt-0.5" data-pipeline-percent>{{ (int) $task->pipeline_percent }}%</p>
    </div>
@endif

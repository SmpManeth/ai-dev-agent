<script>
(function () {
    const syncUrl = @json(route('ai-agent.pipeline.sync'));
    const pollMs = 2000;
    const schedulerRunning = @json((bool) (($scheduler['running'] ?? false)));
    const taskIds = @json(
        isset($pollTaskIds)
            ? $pollTaskIds
            : (isset($tasks) ? $tasks->pluck('id')->values() : (isset($task) ? [$task->id] : []))
    );

    const alwaysPoll = @json(isset($tasks) || isset($task));

    const stepOrder = @json(array_column(\App\Enums\AiAgentPipelinePhase::stepDefinitions(), 'phase'));

    function applyTask(data) {
        const id = data.id;
        document.querySelectorAll('[data-pipeline-badge][data-task-id="' + id + '"]').forEach(el => {
            el.textContent = data.pipeline_label;
            el.className = 'inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ' + data.pipeline_badge_color;
        });
        document.querySelectorAll('[data-pipeline-bar-wrap][data-task-id="' + id + '"] [data-pipeline-bar], #pipeline-card[data-task-id="' + id + '"] [data-pipeline-bar]').forEach(el => {
            el.style.width = Math.max(2, data.pipeline_percent) + '%';
        });
        document.querySelectorAll('[data-pipeline-percent][data-task-id="' + id + '"]').forEach(el => {
            el.textContent = data.pipeline_percent + '%';
        });
        const card = document.getElementById('pipeline-card');
        if (card && String(card.dataset.taskId) === String(id)) {
            const label = card.querySelector('[data-pipeline-label]');
            if (label) label.textContent = data.pipeline_label;
            const row = card.querySelector('[data-pipeline-steps]');
            if (row && data.pipeline_phase) {
                const cur = stepOrder.indexOf(data.pipeline_phase);
                row.querySelectorAll('[data-step-phase]').forEach(li => {
                    const phase = li.dataset.stepPhase;
                    const idx = stepOrder.indexOf(phase);
                    li.className = 'rounded-lg px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide ring-1 text-center ';
                    if (phase === data.pipeline_phase) {
                        li.className += 'bg-blue-50 text-blue-800 ring-blue-200';
                    } else if (idx >= 0 && cur >= 0 && idx < cur) {
                        li.className += 'bg-emerald-50 text-emerald-800 ring-emerald-200';
                    } else {
                        li.className += 'bg-slate-50 text-slate-500 ring-slate-200';
                    }
                });
            }
        }
    }

    async function poll() {
        try {
            const params = new URLSearchParams();
            if (taskIds.length) params.set('ids', taskIds.join(','));
            const res = await fetch(syncUrl + '?' + params, {
                headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) return;
            const body = await res.json();
            (body.tasks || []).forEach(applyTask);
            const keepGoing = alwaysPoll || body.scheduler_running || (body.tasks || []).some(t => t.pipeline_active);
            if (keepGoing) setTimeout(poll, pollMs);
        } catch (_) {
            setTimeout(poll, pollMs * 2);
        }
    }

    poll();
})();
</script>

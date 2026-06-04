@php
    $nav = [
        ['route' => 'ai-agent.dashboard', 'label' => 'Overview', 'icon' => 'grid'],
        ['route' => 'ai-agent.tasks.index', 'label' => 'Tasks', 'icon' => 'list'],
        ['route' => 'ai-agent.settings', 'label' => 'Settings', 'icon' => 'cog', 'params' => ['section' => 'runtime']],
    ];
@endphp
<aside class="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col bg-surface text-slate-300">
    <div class="flex h-16 shrink-0 items-center gap-3 px-5 border-b border-surface-border">
        <div class="h-9 w-9 rounded-lg bg-accent/20 flex items-center justify-center ring-1 ring-accent/40">
            <svg class="h-5 w-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
            </svg>
        </div>
        <div>
            <p class="text-sm font-semibold text-white tracking-tight">AI Operations</p>
            <p class="text-[10px] text-slate-500 uppercase tracking-widest">Control Plane</p>
        </div>
    </div>
    <nav class="flex-1 px-3 py-4 space-y-1">
        @foreach ($nav as $item)
            @php
                $active = match ($item['route']) {
                    'ai-agent.dashboard' => request()->routeIs('ai-agent.dashboard'),
                    'ai-agent.settings' => request()->routeIs('ai-agent.settings'),
                    default => request()->routeIs('ai-agent.tasks.*'),
                };
                $href = isset($item['params'])
                    ? route($item['route'], $item['params'])
                    : route($item['route']);
            @endphp
            <a href="{{ $href }}"
               class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition
                      {{ $active ? 'bg-accent-muted text-white' : 'text-slate-400 hover:bg-surface-elevated hover:text-slate-200' }}">
                @if ($item['icon'] === 'grid')
                    <svg class="h-5 w-5 shrink-0 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" /></svg>
                @elseif ($item['icon'] === 'list')
                    <svg class="h-5 w-5 shrink-0 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm0 5.25h.007v.008H3.75v-.008zm0 5.25h.007v.008H3.75v-.008z" /></svg>
                @else
                    <svg class="h-5 w-5 shrink-0 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                @endif
                {{ $item['label'] }}
            </a>
        @endforeach
    </nav>
    <div class="p-4 border-t border-surface-border">
        <form method="post" action="{{ route('ai-agent.jira-batch.run') }}"
              onsubmit="return confirm('Start Jira ai-fix batch now?');">
            @csrf
            <button type="submit"
                    class="w-full rounded-lg bg-accent px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 transition shadow-sm">
                Run Jira Batch
            </button>
        </form>
        <p class="mt-2 text-[10px] text-slate-500 text-center">One issue per cycle</p>
    </div>
</aside>

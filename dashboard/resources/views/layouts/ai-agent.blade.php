<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>@yield('title', 'Overview') — AI Operations</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
                        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
                    },
                    colors: {
                        surface: { DEFAULT: '#0f1419', elevated: '#1a2332', border: '#2d3a4f' },
                        accent: { DEFAULT: '#3b82f6', muted: '#1e3a5f' },
                    },
                },
            },
        };
    </script>
    <style>
        [x-cloak] { display: none !important; }
    </style>
</head>
<body class="h-full bg-[#f4f6f9] text-slate-900 font-sans antialiased">
    <div class="min-h-full flex flex-col lg:flex-row">
        <div class="lg:hidden bg-surface text-white px-4 py-3 flex items-center justify-between">
            <span class="text-sm font-semibold">AI Operations</span>
            <nav class="flex gap-3 text-xs">
                <a href="{{ route('ai-agent.dashboard') }}" class="text-slate-300">Overview</a>
                <a href="{{ route('ai-agent.tasks.index') }}" class="text-slate-300">Tasks</a>
                <a href="{{ route('ai-agent.settings') }}" class="text-slate-300">Settings</a>
            </nav>
        </div>
        @include('ai-agent.partials.sidebar')

        <div class="flex-1 flex flex-col min-w-0 lg:pl-64">
            <header class="sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-slate-200">
                <div class="px-6 py-4 flex items-center justify-between gap-4">
                    <div>
                        <p class="text-xs font-medium text-slate-500 uppercase tracking-wider">Blue Lotus Vacations</p>
                        <h1 class="text-lg font-semibold text-slate-900">@yield('page_title', 'Operations')</h1>
                    </div>
                    <div class="flex items-center gap-3">
                        @yield('header_actions')
                        @php $healthReady = ($health['ready'] ?? null); @endphp
                        @if ($healthReady !== null)
                            <span class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium {{ $healthReady ? 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200' : 'bg-amber-50 text-amber-800 ring-1 ring-amber-200' }}">
                                <span class="h-1.5 w-1.5 rounded-full {{ $healthReady ? 'bg-emerald-500' : 'bg-amber-500' }}"></span>
                                {{ $healthReady ? 'System ready' : 'Config incomplete' }}
                            </span>
                        @endif
                    </div>
                </div>
            </header>

            <main class="flex-1 px-6 py-8">
                @include('ai-agent.partials.flash')
                @yield('content')
            </main>

            <footer class="px-6 py-4 border-t border-slate-200 text-xs text-slate-500">
                Autonomous coding agent control plane · Python pipeline · Draft PRs only
            </footer>
        </div>
    </div>
</body>
</html>

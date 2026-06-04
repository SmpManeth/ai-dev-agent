<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>@yield('title', 'AI Agent') — {{ config('app.name') }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
    <nav class="bg-slate-900 text-white shadow">
        <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <a href="{{ route('ai-agent.tasks.index') }}" class="font-semibold text-lg tracking-tight">
                AI Coding Agent
            </a>
            <span class="text-sm text-slate-400">Control Panel</span>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto px-4 py-8">
        @if (session('success'))
            <div class="mb-4 rounded-lg bg-green-50 border border-green-200 text-green-800 px-4 py-3">
                {{ session('success') }}
            </div>
        @endif
        @if (session('error'))
            <div class="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-800 px-4 py-3">
                {{ session('error') }}
            </div>
        @endif

        @yield('content')
    </main>
</body>
</html>

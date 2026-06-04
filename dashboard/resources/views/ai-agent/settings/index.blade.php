@extends('layouts.ai-agent')

@section('title', 'Settings')
@section('page_title', 'Configuration')

@section('content')
    @php
        $tabs = [
            'runtime' => 'Runtime',
            'integrations' => 'Integrations',
            'scheduler' => 'Scheduler',
            'python-env' => 'Python .env',
            'security' => 'Security',
            'production' => 'Production hardening',
        ];
    @endphp

    @if (session('status'))
        <div class="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            {{ session('status') }}
        </div>
    @endif
    @if (session('error'))
        <div class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
            {{ session('error') }}
        </div>
    @endif

    @if ($section !== 'production')
        <div class="mb-6 rounded-lg border border-blue-100 bg-blue-50/80 px-4 py-3 text-sm text-blue-900">
            Configuration is read-only in this panel. Edit <code class="font-mono text-xs bg-white/80 px-1 rounded">dashboard/.env</code>
            and the Python project <code class="font-mono text-xs bg-white/80 px-1 rounded">.env</code>, then restart
            <code class="font-mono text-xs">php artisan serve</code> or clear config cache.
        </div>
    @endif

    <div class="border-b border-slate-200 mb-6">
        <nav class="flex gap-1 overflow-x-auto" aria-label="Settings sections">
            @foreach ($tabs as $key => $label)
                <a href="{{ route('ai-agent.settings', ['section' => $key]) }}"
                   class="whitespace-nowrap px-4 py-3 text-sm font-medium border-b-2 transition
                          {{ $section === $key ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300' }}">
                    {{ $label }}
                </a>
            @endforeach
        </nav>
    </div>

    @if ($section === 'runtime')
        @include('ai-agent.partials.env-table', [
            'rows' => collect($laravelSettings)->filter(fn ($r) => in_array($r['group'], ['Runtime', 'Laravel'], true))->values()->all(),
            'title' => 'Dashboard & agent runtime',
            'description' => 'Values from dashboard/.env via config/ai_agent.php',
        ])
    @endif

    @if ($section === 'integrations')
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div class="rounded-xl bg-white ring-1 ring-slate-200 p-5 shadow-sm">
                <h3 class="text-sm font-semibold text-slate-900 mb-3">GitHub</h3>
                <dl class="space-y-2 text-sm">
                    <div><dt class="text-slate-500 text-xs">Target</dt><dd class="font-mono">{{ $integrations['github_target'] ?: '—' }}</dd></div>
                    <div><dt class="text-slate-500 text-xs">Repository URL</dt>
                        <dd>@if ($integrations['github_url'])<a href="{{ $integrations['github_url'] }}" class="text-blue-600 hover:underline break-all" target="_blank">{{ $integrations['github_url'] }}</a>@else — @endif</dd>
                    </div>
                </dl>
            </div>
            <div class="rounded-xl bg-white ring-1 ring-slate-200 p-5 shadow-sm">
                <h3 class="text-sm font-semibold text-slate-900 mb-3">Workspace</h3>
                <dl class="space-y-2 text-sm">
                    <div><dt class="text-slate-500 text-xs">Clone path</dt><dd class="font-mono text-xs break-all">{{ $integrations['workspace_path'] }}</dd></div>
                    <div><dt class="text-slate-500 text-xs">On disk</dt><dd class="{{ $integrations['workspace_exists'] ? 'text-emerald-700' : 'text-amber-700' }} font-medium">{{ $integrations['workspace_exists'] ? 'Present' : 'Missing — run batch sync' }}</dd></div>
                    <div><dt class="text-slate-500 text-xs">Python entry</dt><dd class="font-mono text-xs">{{ $integrations['python_main'] }}</dd></div>
                </dl>
            </div>
        </div>
        @include('ai-agent.partials.env-table', [
            'rows' => collect($laravelSettings)->filter(fn ($r) => in_array($r['group'], ['GitHub', 'Jira'], true))->values()->all(),
            'title' => 'Integration variables (dashboard)',
        ])
        <p class="mt-4 text-xs text-slate-500">API tokens for GitHub and Jira are configured in the Python <code>.env</code> (see Python .env tab).</p>
    @endif

    @if ($section === 'scheduler')
        <div class="rounded-xl bg-white ring-1 ring-slate-200 p-6 shadow-sm mb-6 max-w-2xl">
            <h3 class="text-sm font-semibold text-slate-900 mb-4">Automatic Jira polling</h3>
            <dl class="grid grid-cols-2 gap-4 text-sm">
                <div><dt class="text-slate-500 text-xs">Enabled</dt><dd class="font-medium">{{ config('ai_agent.schedule_enabled') ? 'Yes' : 'No' }}</dd></div>
                <div><dt class="text-slate-500 text-xs">Interval</dt><dd class="font-medium">{{ config('ai_agent.schedule_interval_minutes') }} minutes</dd></div>
                <div><dt class="text-slate-500 text-xs">Overlap lock</dt><dd class="font-medium">{{ config('ai_agent.schedule_overlap_minutes') }} minutes</dd></div>
                <div><dt class="text-slate-500 text-xs">Issues per cycle</dt><dd class="font-medium">{{ config('ai_agent.jira_batch_max_tasks') }}</dd></div>
            </dl>
            @if (!empty($scheduler['last_run_at']))
                <div class="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-600">
                    <p><strong>Last run:</strong> {{ $scheduler['last_run_at'] }} ({{ $scheduler['last_triggered_by'] ?? 'unknown' }})</p>
                    @if (isset($scheduler['last_stats']))
                        <p class="mt-1">PR {{ $scheduler['last_stats']['pr_created'] ?? 0 }} · Failed {{ $scheduler['last_stats']['failed'] ?? 0 }} · Skipped {{ $scheduler['last_stats']['skipped'] ?? 0 }}</p>
                    @endif
                </div>
            @endif
            <pre class="mt-4 rounded-lg bg-slate-900 text-slate-100 text-xs p-4 overflow-x-auto font-mono">* * * * * cd {{ base_path() }} && php artisan schedule:run >> storage/logs/cron.log 2>&1</pre>
        </div>
        @include('ai-agent.partials.env-table', [
            'rows' => collect($laravelSettings)->filter(fn ($r) => $r['group'] === 'Scheduler')->values()->all(),
            'title' => 'Scheduler environment variables',
        ])
    @endif

    @if ($section === 'python-env')
        @if (! $pythonEnv['exists'])
            <div class="rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900">
                Python environment file not found at <code class="font-mono text-xs">{{ $pythonEnv['path'] }}</code>.
                Copy <code>.env.example</code> in the agent project root.
            </div>
        @else
            @include('ai-agent.partials.env-table', [
                'rows' => $pythonEnv['rows'],
                'title' => 'Python agent environment',
                'description' => $pythonEnv['path'].' — secrets are masked',
            ])
        @endif
    @endif

    @if ($section === 'security')
        @include('ai-agent.partials.env-table', [
            'rows' => collect($laravelSettings)->filter(fn ($r) => $r['group'] === 'Safety')->values()->all(),
            'title' => 'Approval & safety',
        ])
        <div class="mt-6 rounded-xl bg-white ring-1 ring-slate-200 p-5 shadow-sm">
            <h3 class="text-sm font-semibold text-slate-900 mb-2">High-risk keywords</h3>
            <p class="text-xs text-slate-500 mb-3">Tasks matching these terms in description require manual approval before run.</p>
            <div class="flex flex-wrap gap-2">
                @foreach (config('ai_agent.high_risk_keywords', []) as $keyword)
                    <span class="inline-flex rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{{ $keyword }}</span>
                @endforeach
            </div>
        </div>
        <ul class="mt-6 text-sm text-slate-600 space-y-2 list-disc list-inside">
            <li>Draft PRs only — no automatic merge</li>
            <li>Forbidden paths: <code class="text-xs">.env</code>, migrations, <code class="text-xs">composer.json</code>, etc.</li>
            <li>Credentials never stored in task logs (redacted on write)</li>
        </ul>
    @endif

    @if ($section === 'production')
        @if (! ($hardening['agent_enabled'] ?? true))
            <div class="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <strong>Kill switch active</strong> — the agent will not run until re-enabled below.
            </div>
        @endif
        @include('ai-agent.settings.partials.production-hardening')
        <div class="mt-8 text-sm text-slate-600">
            <p class="font-medium text-slate-800 mb-2">Build sandbox image</p>
            <pre class="rounded-lg bg-slate-900 text-slate-100 text-xs p-4 overflow-x-auto font-mono">cd docker && docker build -f Dockerfile.sandbox -t ai-dev-agent-sandbox:latest .</pre>
        </div>
    @endif
@endsection

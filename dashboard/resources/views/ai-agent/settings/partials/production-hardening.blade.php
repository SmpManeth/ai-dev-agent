@php
    $list = static function (string $key) use ($hardening): string {
        $items = $hardening[$key] ?? [];
        return is_array($items) ? implode("\n", $items) : '';
    };
@endphp

<form method="post" action="{{ route('ai-agent.settings.update') }}" class="space-y-6 max-w-3xl">
    @csrf

    <div class="rounded-xl bg-white ring-1 ring-slate-200 p-6 shadow-sm">
        <h3 class="text-sm font-semibold text-slate-900 mb-1">Kill switch & sandbox</h3>
        <p class="text-xs text-slate-500 mb-4">Saved to <code class="text-xs font-mono">{{ $hardeningPath }}</code> — consumed by Python via <code class="text-xs">AI_AGENT_HARDENING_CONFIG</code>.</p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <label class="flex items-center gap-2">
                <input type="hidden" name="agent_enabled" value="0">
                <input type="checkbox" name="agent_enabled" value="1" class="rounded border-slate-300"
                       @checked($hardening['agent_enabled'] ?? true)>
                <span>Agent enabled</span>
            </label>
            <label class="flex items-center gap-2">
                <input type="hidden" name="sandbox_enabled" value="0">
                <input type="checkbox" name="sandbox_enabled" value="1" class="rounded border-slate-300"
                       @checked($hardening['sandbox_enabled'] ?? false)>
                <span>Docker sandbox for tests/composer</span>
            </label>
            <label class="flex items-center gap-2 sm:col-span-2">
                <input type="hidden" name="require_approval_before_pr" value="0">
                <input type="checkbox" name="require_approval_before_pr" value="1" class="rounded border-slate-300"
                       @checked($hardening['require_approval_before_pr'] ?? false)>
                <span>Require approval before PR (dashboard must approve task)</span>
            </label>
        </div>

        <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
                <label class="block text-xs text-slate-500 mb-1">Sandbox image</label>
                <input type="text" name="sandbox_image" value="{{ $hardening['sandbox_image'] ?? 'ai-dev-agent-sandbox:latest' }}"
                       class="w-full rounded-lg border-slate-300 text-sm font-mono">
            </div>
            <div>
                <label class="block text-xs text-slate-500 mb-1">Sandbox network</label>
                <select name="sandbox_network" class="w-full rounded-lg border-slate-300 text-sm">
                    @foreach (['none', 'bridge'] as $mode)
                        <option value="{{ $mode }}" @selected(($hardening['sandbox_network'] ?? 'none') === $mode)>{{ $mode }}</option>
                    @endforeach
                </select>
            </div>
        </div>
    </div>

    <div class="rounded-xl bg-white ring-1 ring-slate-200 p-6 shadow-sm">
        <h3 class="text-sm font-semibold text-slate-900 mb-4">Limits</h3>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
                <label class="block text-xs text-slate-500 mb-1">Max retries</label>
                <input type="number" name="max_retries" min="0" max="10" value="{{ $hardening['max_retries'] ?? 3 }}"
                       class="w-full rounded-lg border-slate-300">
            </div>
            <div>
                <label class="block text-xs text-slate-500 mb-1">Max runtime (min)</label>
                <input type="number" name="max_runtime_minutes" min="5" max="480"
                       value="{{ $hardening['max_runtime_minutes'] ?? 120 }}"
                       class="w-full rounded-lg border-slate-300">
            </div>
            <div>
                <label class="block text-xs text-slate-500 mb-1">Max tokens / task</label>
                <input type="number" name="max_tokens_per_task" min="10000"
                       value="{{ $hardening['max_tokens_per_task'] ?? 500000 }}"
                       class="w-full rounded-lg border-slate-300">
            </div>
            <div>
                <label class="block text-xs text-slate-500 mb-1">Risk threshold</label>
                <select name="risk_threshold" class="w-full rounded-lg border-slate-300">
                    @foreach (['low', 'medium', 'high'] as $level)
                        <option value="{{ $level }}" @selected(($hardening['risk_threshold'] ?? 'medium') === $level)>{{ ucfirst($level) }}</option>
                    @endforeach
                </select>
            </div>
        </div>
    </div>

    <div class="rounded-xl bg-white ring-1 ring-slate-200 p-6 shadow-sm">
        <label class="block text-sm font-semibold text-slate-900 mb-1">Allowed repositories</label>
        <p class="text-xs text-slate-500 mb-2">One per line as <code class="font-mono">owner/repo</code>. Empty = allow all configured workspaces.</p>
        <textarea name="allowed_repositories" rows="4" class="w-full rounded-lg border-slate-300 text-sm font-mono">{{ $list('allowed_repositories') }}</textarea>
    </div>

    <div class="rounded-xl bg-white ring-1 ring-slate-200 p-6 shadow-sm">
        <label class="block text-sm font-semibold text-slate-900 mb-1">Blocked file patterns</label>
        <p class="text-xs text-slate-500 mb-2">Substring match on paths (e.g. <code class="font-mono">.env</code>, <code class="font-mono">.github/workflows</code>).</p>
        <textarea name="blocked_file_patterns" rows="8" class="w-full rounded-lg border-slate-300 text-xs font-mono">{{ $list('blocked_file_patterns') }}</textarea>
    </div>

    <div class="rounded-xl bg-white ring-1 ring-slate-200 p-6 shadow-sm">
        <label class="block text-sm font-semibold text-slate-900 mb-1">Blocked command patterns (regex)</label>
        <textarea name="blocked_command_patterns" rows="6" class="w-full rounded-lg border-slate-300 text-xs font-mono">{{ $list('blocked_command_patterns') }}</textarea>
    </div>

    <div class="rounded-xl bg-white ring-1 ring-slate-200 p-6 shadow-sm">
        <label class="block text-sm font-semibold text-slate-900 mb-1">Allowed command prefixes</label>
        <textarea name="allowed_command_prefixes" rows="5" class="w-full rounded-lg border-slate-300 text-xs font-mono">{{ $list('allowed_command_prefixes') }}</textarea>
    </div>

    <button type="submit" class="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
        Save production settings
    </button>
</form>

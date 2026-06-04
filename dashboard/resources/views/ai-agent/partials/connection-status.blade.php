<div class="mb-4 rounded-xl border {{ ($health['ready'] ?? false) ? 'border-green-200 bg-green-50' : 'border-amber-200 bg-amber-50' }} p-4 text-sm">
    <h2 class="font-semibold text-slate-800 mb-2">Connection</h2>
    <ul class="space-y-1.5">
        @foreach ($health['checks'] ?? [] as $check)
            <li class="flex flex-wrap gap-2 items-baseline">
                <span class="{{ $check['ok'] ? 'text-green-700' : 'text-amber-800' }} font-medium w-40 shrink-0">
                    {{ $check['ok'] ? '✓' : '○' }} {{ $check['label'] }}
                </span>
                <span class="text-slate-600 text-xs break-all">{{ $check['detail'] }}</span>
            </li>
        @endforeach
    </ul>
    @if (!empty($githubUrl))
        <p class="text-xs text-slate-500 mt-2">
            GitHub:
            <a href="{{ $githubUrl }}" target="_blank" rel="noopener" class="text-indigo-600 hover:underline">{{ $githubUrl }}</a>
        </p>
    @endif
</div>

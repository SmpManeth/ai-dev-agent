@props(['label', 'value', 'hint' => null, 'tone' => 'default'])
@php
    $tones = [
        'default' => 'bg-white ring-slate-200',
        'success' => 'bg-white ring-emerald-200',
        'danger' => 'bg-white ring-red-200',
        'warning' => 'bg-white ring-amber-200',
    ];
    $valueColors = [
        'default' => 'text-slate-900',
        'success' => 'text-emerald-700',
        'danger' => 'text-red-700',
        'warning' => 'text-amber-700',
    ];
@endphp
<div class="rounded-xl ring-1 {{ $tones[$tone] ?? $tones['default'] }} p-5 shadow-sm">
    <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">{{ $label }}</p>
    <p class="mt-2 text-3xl font-semibold tabular-nums {{ $valueColors[$tone] ?? $valueColors['default'] }}">{{ $value }}</p>
    @if ($hint)
        <p class="mt-1 text-xs text-slate-500">{{ $hint }}</p>
    @endif
</div>

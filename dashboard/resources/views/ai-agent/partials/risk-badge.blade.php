@php
    $colors = match ($risk) {
        'high' => 'bg-red-100 text-red-800',
        'medium' => 'bg-orange-100 text-orange-800',
        'low' => 'bg-emerald-100 text-emerald-800',
        default => 'bg-slate-100 text-slate-600',
    };
@endphp
<span class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium {{ $colors }}">
    {{ $risk ? ucfirst($risk) : 'Unknown' }}
</span>

@props(['rows', 'title' => 'Configuration', 'description' => null])
<div class="rounded-xl bg-white ring-1 ring-slate-200 shadow-sm overflow-hidden">
    <div class="px-5 py-4 border-b border-slate-100">
        <h3 class="text-sm font-semibold text-slate-900">{{ $title }}</h3>
        @if ($description)
            <p class="mt-1 text-xs text-slate-500">{{ $description }}</p>
        @endif
    </div>
    <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                <tr>
                    <th class="px-5 py-3 w-48">Variable</th>
                    <th class="px-5 py-3 w-32">Group</th>
                    <th class="px-5 py-3">Value</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
                @forelse ($rows as $row)
                    <tr class="hover:bg-slate-50/80">
                        <td class="px-5 py-3 font-mono text-xs text-slate-800">{{ $row['key'] }}</td>
                        <td class="px-5 py-3 text-xs text-slate-500">{{ $row['group'] }}</td>
                        <td class="px-5 py-3 font-mono text-xs break-all {{ $row['masked'] ? 'text-slate-400' : 'text-slate-700' }}">
                            {{ $row['value'] }}
                            @if ($row['masked'])
                                <span class="ml-2 inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium bg-slate-100 text-slate-500">masked</span>
                            @endif
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="3" class="px-5 py-8 text-center text-slate-500">No variables to display.</td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>
</div>

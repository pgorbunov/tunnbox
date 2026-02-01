<script lang="ts">
	interface Props {
		status: 'online' | 'offline' | 'active' | 'inactive';
		size?: 'sm' | 'md';
	}

	let { status, size = 'md' }: Props = $props();

	const isActive = $derived(status === 'online' || status === 'active');
	
	const colorClasses = {
		online: 'bg-emerald-500/10 text-emerald-500 ring-emerald-500/20',
		offline: 'bg-slate-500/10 text-slate-400 ring-slate-500/20',
		active: 'bg-emerald-500/10 text-emerald-500 ring-emerald-500/20',
		inactive: 'bg-slate-500/10 text-slate-400 ring-slate-500/20'
	};
	
	const dotColors = {
		online: 'bg-emerald-500',
		offline: 'bg-slate-500',
		active: 'bg-emerald-500',
		inactive: 'bg-slate-500'
	};

	const labels = {
		online: 'Online',
		offline: 'Offline',
		active: 'Active',
		inactive: 'Inactive'
	};

	const badgeSizes = {
		sm: 'text-xs px-2 py-0.5',
		md: 'text-sm px-2.5 py-1'
	};
	
	const dotSizes = {
		sm: 'h-1.5 w-1.5',
		md: 'h-2 w-2'
	};
</script>

<span class="inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset {colorClasses[status]} {badgeSizes[size]}">
	<span class="relative flex {dotSizes[size]}">
		<span class="{dotColors[status]} rounded-full {dotSizes[size]}"></span>
		{#if isActive}
			<span class="absolute inset-0 rounded-full {dotColors[status]} animate-ping opacity-75"></span>
		{/if}
	</span>
	{labels[status]}
</span>

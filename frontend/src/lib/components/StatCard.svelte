<script lang="ts">
	import type { ComponentType } from 'svelte';

	interface Props {
		icon: ComponentType;
		value: string | number;
		label: string;
		color?: 'blue' | 'emerald' | 'purple' | 'amber' | 'rose';
		trend?: {
			direction: 'up' | 'down' | 'neutral';
			value: string;
		};
		onclick?: () => void;
	}

	let { icon: Icon, value, label, color = 'blue', trend, onclick }: Props = $props();

	const colorClasses = {
		blue: {
			bg: 'bg-blue-600/10',
			icon: 'text-blue-500',
			hover: 'hover:border-blue-500/50'
		},
		emerald: {
			bg: 'bg-emerald-600/10',
			icon: 'text-emerald-500',
			hover: 'hover:border-emerald-500/50'
		},
		purple: {
			bg: 'bg-purple-600/10',
			icon: 'text-purple-500',
			hover: 'hover:border-purple-500/50'
		},
		amber: {
			bg: 'bg-amber-600/10',
			icon: 'text-amber-500',
			hover: 'hover:border-amber-500/50'
		},
		rose: {
			bg: 'bg-rose-600/10',
			icon: 'text-rose-500',
			hover: 'hover:border-rose-500/50'
		}
	};

	const colors = colorClasses[color];
	const isClickable = onclick !== undefined;
</script>

<button
	type="button"
	onclick={onclick}
	disabled={!isClickable}
	class="bg-white dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5 transition-all duration-200 text-left w-full
		{isClickable ? `cursor-pointer ${colors.hover} hover:scale-[1.02] active:scale-[0.98]` : 'cursor-default'}"
>
	<div class="flex items-center gap-3">
		<div class="p-2.5 rounded-lg {colors.bg}">
			<Icon class="h-5 w-5 {colors.icon}" />
		</div>
		<div class="flex-1">
			<p class="text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
			<p class="text-sm text-slate-600 dark:text-slate-400">{label}</p>
		</div>
		{#if trend}
			<div class="text-right">
				<p class="text-xs font-medium {trend.direction === 'up' ? 'text-emerald-500' : trend.direction === 'down' ? 'text-rose-400' : 'text-slate-600 dark:text-slate-400'}">
					{trend.direction === 'up' ? '↑' : trend.direction === 'down' ? '↓' : '−'} {trend.value}
				</p>
			</div>
		{/if}
	</div>
</button>

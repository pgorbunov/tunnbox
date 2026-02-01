<script lang="ts">
	import { toast, type Toast } from '$lib/stores/toast';
	import { CheckCircle, X, AlertCircle, Info, AlertTriangle } from 'lucide-svelte';
	import { fly, fade } from 'svelte/transition';

	const toasts = $derived($toast);

	function getIcon(type: Toast['type']) {
		switch (type) {
			case 'success':
				return CheckCircle;
			case 'error':
				return AlertCircle;
			case 'warning':
				return AlertTriangle;
			case 'info':
			default:
				return Info;
		}
	}

	function getStyles(type: Toast['type']) {
		switch (type) {
			case 'success':
				return 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';
			case 'error':
				return 'bg-rose-500/10 border-rose-500/20 text-rose-400';
			case 'warning':
				return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
			case 'info':
			default:
				return 'bg-blue-500/10 border-blue-500/20 text-blue-400';
		}
	}
</script>

<div class="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
	{#each toasts as item (item.id)}
		<div
			class="p-4 rounded-lg border flex items-center gap-3 shadow-lg pointer-events-auto {getStyles(
				item.type
			)}"
			in:fly={{ x: 300, duration: 300 }}
			out:fade={{ duration: 200 }}
		>
			{#if getIcon(item.type)}
				{@const Icon = getIcon(item.type)}
				<Icon class="h-5 w-5 flex-shrink-0" />
			{/if}
			<span class="flex-1">{item.message}</span>
			<button
				onclick={() => toast.remove(item.id)}
				class="p-1 hover:bg-white/10 rounded transition-colors"
				aria-label="Close notification"
			>
				<X class="h-4 w-4" />
			</button>
		</div>
	{/each}
</div>

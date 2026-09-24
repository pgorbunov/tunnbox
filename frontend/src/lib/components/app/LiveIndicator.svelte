<script lang="ts">
	/** "Updated 5s ago" pill with a manual refresh button; driven by page pollers. */
	import { RefreshCw } from 'lucide-svelte';
	import { liveStatus } from '$lib/stores/live.svelte';
	import { createTicker } from '$lib/utils/poll.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';

	const ticker = createTicker(1000);
	const ago = $derived.by(() => {
		if (!liveStatus.lastUpdated) return null;
		const s = Math.max(0, Math.round((ticker.now - liveStatus.lastUpdated) / 1000));
		if (s < 5) return 'just now';
		if (s < 60) return `${s}s ago`;
		const m = Math.floor(s / 60);
		return `${m}m ago`;
	});
</script>

{#if liveStatus.active}
	<div class="flex items-center gap-1 text-xs text-fg-subtle">
		<span class="hidden items-center gap-1.5 sm:inline-flex" aria-live="off">
			<span
				class={`inline-block h-1.5 w-1.5 rounded-full ${liveStatus.error ? 'bg-danger' : 'bg-success'} ${liveStatus.refreshing ? 'animate-pulse motion-reduce:animate-none' : ''}`}
				aria-hidden="true"
			></span>
			{#if liveStatus.error}
				Refresh failed
			{:else if ago}
				Updated {ago}
			{:else}
				Loading
			{/if}
		</span>
		<IconButton
			label="Refresh now"
			size="sm"
			onclick={() => liveStatus.refresh()}
			loading={liveStatus.refreshing}
		>
			<RefreshCw class="h-4 w-4" />
		</IconButton>
	</div>
{/if}

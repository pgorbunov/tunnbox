<script lang="ts">
	import { Power, PowerOff, Trash2, X } from 'lucide-svelte';
	import type { BulkAction } from '$lib/api/types';
	import Button from '$lib/components/ui/Button.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';

	interface Props {
		count: number;
		loading?: BulkAction | null;
		onaction: (action: BulkAction) => void;
		onclear: () => void;
	}

	let { count, loading = null, onaction, onclear }: Props = $props();
</script>

{#if count > 0}
	<div
		class="anim-slide-up sticky bottom-4 z-20 mx-auto flex w-fit max-w-full flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-raised px-3 py-2 shadow-lg"
		role="toolbar"
		aria-label="Bulk actions"
	>
		<span class="pr-1 text-sm font-medium text-fg tabular">{count} selected</span>
		<Button
			size="sm"
			onclick={() => onaction('enable')}
			loading={loading === 'enable'}
			disabled={loading !== null}
		>
			<Power class="h-4 w-4" aria-hidden="true" />
			Enable
		</Button>
		<Button
			size="sm"
			onclick={() => onaction('disable')}
			loading={loading === 'disable'}
			disabled={loading !== null}
		>
			<PowerOff class="h-4 w-4" aria-hidden="true" />
			Disable
		</Button>
		<Button
			size="sm"
			variant="danger-soft"
			onclick={() => onaction('delete')}
			loading={loading === 'delete'}
			disabled={loading !== null}
		>
			<Trash2 class="h-4 w-4" aria-hidden="true" />
			Delete
		</Button>
		<IconButton label="Clear selection" size="sm" onclick={onclear}>
			<X class="h-4 w-4" />
		</IconButton>
	</div>
{/if}

<script lang="ts">
	import { HOTKEY_HELP } from '$lib/utils/keyboard';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import Kbd from '$lib/components/ui/Kbd.svelte';

	let { open = $bindable(false) }: { open: boolean } = $props();
</script>

<Dialog bind:open title="Keyboard shortcuts" size="sm">
	<dl class="divide-y divide-border">
		{#each HOTKEY_HELP as item (item.description)}
			<div class="flex items-center justify-between gap-4 py-2 text-sm">
				<dt class="text-fg-muted">{item.description}</dt>
				<dd class="flex items-center gap-1">
					{#each item.keys as k, i (i)}
						{#if i > 0 && item.keys[0] === 'g'}<span class="text-xs text-fg-subtle">then</span>{/if}
						<Kbd>{k}</Kbd>
					{/each}
				</dd>
			</div>
		{/each}
	</dl>
</Dialog>

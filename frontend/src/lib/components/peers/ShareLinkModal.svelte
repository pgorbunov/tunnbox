<script lang="ts">
	import type { Peer } from '$lib/api/types';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import ShareLinkPanel from './ShareLinkPanel.svelte';

	let { open = $bindable(false), peer }: { open: boolean; peer: Peer | null } = $props();
</script>

{#if peer}
	<Dialog bind:open title={`Share ${peer.name}`} size="md">
		<ShareLinkPanel {peer} />
	</Dialog>
{/if}

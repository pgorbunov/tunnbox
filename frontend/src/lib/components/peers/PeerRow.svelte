<script lang="ts">
	/** Card layout for a peer (used by PeerTable below 768px). */
	import { ArrowDown, ArrowUp } from 'lucide-svelte';
	import type { Peer } from '$lib/api/types';
	import { formatBytes, formatRelative, stripPrefixes } from '$lib/utils/format';
	import PeerStatusBadge from '$lib/components/app/PeerStatusBadge.svelte';
	import type { PeerActionHandler } from './actions';
	import PeerActionsMenu from './PeerActionsMenu.svelte';

	interface Props {
		peer: Peer;
		canWrite: boolean;
		showInterface?: boolean;
		now: number;
		onopen: (peer: Peer) => void;
		onaction: PeerActionHandler;
	}

	let { peer, canWrite, showInterface = false, now, onopen, onaction }: Props = $props();
</script>

<div class="flex items-start gap-3">
	<div class="min-w-0 flex-1">
		<div class="flex items-center gap-2">
			<button type="button" class="min-w-0 truncate text-left text-sm font-medium text-fg hover:underline" onclick={() => onopen(peer)}>
				{peer.name}
			</button>
			<PeerStatusBadge status={peer.status} size="sm" />
		</div>
		<p class="mt-0.5 truncate font-mono text-[12px] text-fg-muted">
			{stripPrefixes(peer.allowed_ips)}{#if showInterface}<span class="text-fg-subtle"> · {peer.interface_name}</span>{/if}
		</p>
		<div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-fg-subtle">
			<span>Handshake {formatRelative(peer.latest_handshake_at, now)}</span>
			<span class="tabular inline-flex items-center gap-0.5"><ArrowDown class="h-3 w-3 text-chart-download" aria-hidden="true" /><span class="sr-only">Download</span>{formatBytes(peer.rx_total)}</span>
			<span class="tabular inline-flex items-center gap-0.5"><ArrowUp class="h-3 w-3 text-chart-upload" aria-hidden="true" /><span class="sr-only">Upload</span>{formatBytes(peer.tx_total)}</span>
			{#if peer.expires_at}
				<span class={peer.status === 'expired' ? 'text-danger' : ''}>Expires {formatRelative(peer.expires_at, now)}</span>
			{/if}
		</div>
	</div>
	<PeerActionsMenu {peer} {canWrite} {onaction} size="md" />
</div>

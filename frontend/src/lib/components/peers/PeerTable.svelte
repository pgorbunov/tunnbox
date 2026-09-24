<script lang="ts">
	/**
	 * Peer table: Status, Name, Address, Endpoint, Last handshake, Down, Up,
	 * Expires, actions. Collapses to PeerRow cards below 768px.
	 */
	import type { Snippet } from 'svelte';
	import type { SvelteSet } from 'svelte/reactivity';
	import type { Peer } from '$lib/api/types';
	import { formatBytes, formatDateTime, formatRelative, stripPrefixes } from '$lib/utils/format';
	import { createTicker } from '$lib/utils/poll.svelte';
	import PeerStatusBadge from '$lib/components/app/PeerStatusBadge.svelte';
	import Table, { type Column } from '$lib/components/ui/Table.svelte';
	import type { PeerActionHandler } from './actions';
	import PeerActionsMenu from './PeerActionsMenu.svelte';
	import PeerRow from './PeerRow.svelte';

	interface Props {
		peers: Peer[];
		loading?: boolean;
		refreshing?: boolean;
		sortKey?: string;
		sortOrder?: 'asc' | 'desc';
		onsort?: (key: string, order: 'asc' | 'desc') => void;
		selected?: SvelteSet<number>;
		canWrite: boolean;
		showInterface?: boolean;
		onopen: (peer: Peer) => void;
		onaction: PeerActionHandler;
		empty?: Snippet;
	}

	let {
		peers,
		loading = false,
		refreshing = false,
		sortKey,
		sortOrder = 'asc',
		onsort,
		selected,
		canWrite,
		showInterface = false,
		onopen,
		onaction,
		empty
	}: Props = $props();

	const ticker = createTicker(15_000);

	const columns = $derived<Column[]>([
		{ key: 'status', label: 'Status', class: 'w-28' },
		{ key: 'name', label: 'Name', sortable: true },
		{ key: 'address', label: 'Address' },
		...(showInterface ? [{ key: 'interface', label: 'Interface', class: 'hidden xl:table-cell' }] : []),
		{ key: 'endpoint', label: 'Endpoint', class: 'hidden xl:table-cell' },
		{ key: 'handshake', label: 'Last handshake', sortable: true, class: 'hidden lg:table-cell' },
		{ key: 'rx', label: 'Down', sortable: true, align: 'right', class: 'w-24' },
		{ key: 'tx', label: 'Up', sortable: true, align: 'right', class: 'w-24' },
		{ key: 'expires', label: 'Expires', class: 'hidden lg:table-cell' },
		{ key: 'actions', label: 'Actions', srOnly: true, align: 'right', class: 'w-12' }
	]);
</script>

<Table
	{columns}
	rows={peers}
	rowKey={(p) => p.id}
	caption="Peers"
	{loading}
	{refreshing}
	{sortKey}
	{sortOrder}
	{onsort}
	selectable={canWrite && !!selected}
	{selected}
	onrowclick={onopen}
	rowLabel={(p) => `Open ${p.name}`}
	{empty}
>
	{#snippet cell(peer, col)}
		{#if col.key === 'status'}
			<PeerStatusBadge status={peer.status} size="sm" />
		{:else if col.key === 'name'}
			<span class="block max-w-[14rem] truncate font-medium text-fg" title={peer.name}>{peer.name}</span>
			{#if peer.notes}
				<span class="block max-w-[14rem] truncate text-[12px] text-fg-subtle" title={peer.notes}>{peer.notes}</span>
			{/if}
		{:else if col.key === 'address'}
			<span class="font-mono text-[13px] text-fg-muted">{stripPrefixes(peer.allowed_ips)}</span>
		{:else if col.key === 'interface'}
			<a href={`/interfaces/${encodeURIComponent(peer.interface_name)}`} class="font-mono text-[13px] text-fg-muted hover:text-fg hover:underline">{peer.interface_name}</a>
		{:else if col.key === 'endpoint'}
			<span class="font-mono text-[13px] text-fg-muted">{peer.endpoint ?? '—'}</span>
		{:else if col.key === 'handshake'}
			<span class="text-fg-muted" title={peer.latest_handshake_at ? formatDateTime(peer.latest_handshake_at) : 'No handshake yet'}>
				{formatRelative(peer.latest_handshake_at, ticker.now)}
			</span>
		{:else if col.key === 'rx'}
			<span class="tabular text-fg-muted">{formatBytes(peer.rx_total)}</span>
		{:else if col.key === 'tx'}
			<span class="tabular text-fg-muted">{formatBytes(peer.tx_total)}</span>
		{:else if col.key === 'expires'}
			{#if peer.expires_at}
				<span class={peer.status === 'expired' ? 'text-danger' : 'text-fg-muted'} title={formatDateTime(peer.expires_at)}>
					{formatRelative(peer.expires_at, ticker.now)}
				</span>
			{:else}
				<span class="text-fg-subtle">Never</span>
			{/if}
		{:else if col.key === 'actions'}
			<div class="flex justify-end" data-no-row-click>
				<PeerActionsMenu {peer} {canWrite} {onaction} />
			</div>
		{/if}
	{/snippet}
	{#snippet card(peer)}
		<PeerRow {peer} {canWrite} {showInterface} now={ticker.now} {onopen} {onaction} />
	{/snippet}
</Table>

<script lang="ts">
	/** Peer details side panel: identity, traffic chart with range selector, quick actions. */
	import { Download, KeyRound, Link2, Pencil, Power, PowerOff, QrCode, Trash2 } from 'lucide-svelte';
	import { api, isAbortError, toApiError } from '$lib/api';
	import type { Peer, StatsRange, StatsResponse } from '$lib/api/types';
	import { formatBytes, formatDateTime, formatRelative, isFullTunnel } from '$lib/utils/format';
	import { createTicker } from '$lib/utils/poll.svelte';
	import PeerStatusBadge from '$lib/components/app/PeerStatusBadge.svelte';
	import AreaChart from '$lib/components/charts/AreaChart.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import Drawer from '$lib/components/ui/Drawer.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';
	import type { PeerActionHandler } from './actions';
	import PeerActionsMenu from './PeerActionsMenu.svelte';

	interface Props {
		open: boolean;
		peer: Peer | null;
		canWrite: boolean;
		onaction: PeerActionHandler;
	}

	let { open = $bindable(false), peer, canWrite, onaction }: Props = $props();

	const ticker = createTicker(10_000);
	let range = $state<StatsRange>('24h');
	let stats = $state<StatsResponse | null>(null);
	let statsLoading = $state(false);
	let statsError = $state<string | null>(null);
	let abort: AbortController | null = null;

	const RANGES = [
		{ value: '1h' as const, label: '1h' },
		{ value: '6h' as const, label: '6h' },
		{ value: '24h' as const, label: '24h' },
		{ value: '7d' as const, label: '7d' },
		{ value: '30d' as const, label: '30d' }
	];

	async function loadStats(id: number, r: StatsRange) {
		abort?.abort();
		abort = new AbortController();
		const signal = abort.signal;
		statsLoading = true;
		statsError = null;
		try {
			const res = await api.peers.stats(id, r, signal);
			if (!signal.aborted) stats = res;
		} catch (err) {
			if (isAbortError(err)) return;
			statsError = toApiError(err).detail;
		} finally {
			if (!signal.aborted) statsLoading = false;
		}
	}

	$effect(() => {
		if (!open || !peer) return;
		const id = peer.id;
		const r = range;
		void loadStats(id, r);
		const timer = setInterval(() => void loadStats(id, r), 30_000);
		return () => {
			clearInterval(timer);
			abort?.abort();
		};
	});

	$effect(() => {
		if (!open) stats = null;
	});
</script>

{#if peer}
	<Drawer bind:open title={peer.name} description={`${peer.interface_name} · ${peer.allowed_ips}`} width="lg">
		{#snippet actions()}
			<PeerActionsMenu {peer} {canWrite} {onaction} size="sm" />
		{/snippet}

		<div class="flex flex-col gap-6">
			<div class="flex flex-wrap items-center gap-2">
				<PeerStatusBadge status={peer.status} />
				{#if peer.has_private_key}
					<Button size="sm" onclick={() => onaction('qr', peer)}>
						<QrCode class="h-4 w-4" aria-hidden="true" />
						QR code
					</Button>
					<Button size="sm" onclick={() => onaction('download', peer)}>
						<Download class="h-4 w-4" aria-hidden="true" />
						Download
					</Button>
				{/if}
				{#if canWrite}
					<Button size="sm" onclick={() => onaction('share', peer)}>
						<Link2 class="h-4 w-4" aria-hidden="true" />
						Share
					</Button>
					<Button size="sm" onclick={() => onaction('edit', peer)}>
						<Pencil class="h-4 w-4" aria-hidden="true" />
						Edit
					</Button>
				{/if}
			</div>

			<section aria-labelledby="peer-traffic">
				<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
					<h3 id="peer-traffic" class="text-sm font-semibold text-fg">Traffic</h3>
					<SegmentedControl bind:value={range} label="Time range" options={RANGES} />
				</div>
				{#if statsError}
					<ErrorState compact message={statsError} onretry={() => peer && loadStats(peer.id, range)} />
				{:else}
					<AreaChart
						points={stats?.points ?? []}
						bucketSeconds={stats?.bucket_seconds}
						title={`Traffic for ${peer.name}`}
						loading={statsLoading && !stats}
						refreshing={statsLoading && !!stats}
						height={200}
					/>
				{/if}
			</section>

			<section aria-labelledby="peer-details">
				<h3 id="peer-details" class="mb-3 text-sm font-semibold text-fg">Details</h3>
				<dl class="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
					<div>
						<dt class="text-fg-subtle">Last handshake</dt>
						<dd class="text-fg" title={formatDateTime(peer.latest_handshake_at)}>{formatRelative(peer.latest_handshake_at, ticker.now)}</dd>
					</div>
					<div>
						<dt class="text-fg-subtle">Endpoint</dt>
						<dd class="font-mono text-[13px] text-fg">{peer.endpoint ?? '—'}</dd>
					</div>
					<div>
						<dt class="text-fg-subtle">Download / Upload</dt>
						<dd class="tabular text-fg">{formatBytes(peer.rx_total)} / {formatBytes(peer.tx_total)}</dd>
					</div>
					<div>
						<dt class="text-fg-subtle">Keepalive</dt>
						<dd class="text-fg">{peer.persistent_keepalive ? `${peer.persistent_keepalive}s` : 'Off'}</dd>
					</div>
					<div>
						<dt class="text-fg-subtle">Routing</dt>
						<dd class="text-fg">
							{isFullTunnel(peer.client_allowed_ips) ? 'Full tunnel' : 'Split tunnel'}
							<span class="block break-all font-mono text-[12px] text-fg-subtle">{peer.client_allowed_ips}</span>
						</dd>
					</div>
					<div>
						<dt class="text-fg-subtle">DNS</dt>
						<dd class="font-mono text-[13px] text-fg">{peer.client_dns ?? 'Interface default'}</dd>
					</div>
					<div>
						<dt class="text-fg-subtle">Expires</dt>
						<dd class={peer.status === 'expired' ? 'text-danger' : 'text-fg'} title={formatDateTime(peer.expires_at)}>
							{peer.expires_at ? formatRelative(peer.expires_at, ticker.now) : 'Never'}
						</dd>
					</div>
					<div>
						<dt class="text-fg-subtle">Created</dt>
						<dd class="text-fg">{formatDateTime(peer.created_at)}</dd>
					</div>
					<div class="sm:col-span-2">
						<dt class="text-fg-subtle">Public key</dt>
						<dd class="flex items-center gap-1">
							<code class="min-w-0 flex-1 truncate font-mono text-[12px] text-fg">{peer.public_key}</code>
							<CopyButton text={peer.public_key} label="Copy public key" />
						</dd>
					</div>
					<div class="sm:col-span-2">
						<dt class="text-fg-subtle">Keys</dt>
						<dd class="text-fg">
							{peer.has_private_key ? 'Private key stored' : 'Private key not stored'} · {peer.has_preshared_key ? 'Preshared key set' : 'No preshared key'}
						</dd>
					</div>
					{#if peer.notes}
						<div class="sm:col-span-2">
							<dt class="text-fg-subtle">Notes</dt>
							<dd class="whitespace-pre-wrap text-fg">{peer.notes}</dd>
						</div>
					{/if}
				</dl>
			</section>
		</div>

		{#snippet footer()}
			{#if canWrite}
				<Button size="sm" variant="ghost" onclick={() => onaction('rotate', peer)}>
					<KeyRound class="h-4 w-4" aria-hidden="true" />
					Rotate keys
				</Button>
				<Button size="sm" variant="ghost" onclick={() => onaction('toggle', peer)}>
					{#if peer.enabled}
						<PowerOff class="h-4 w-4" aria-hidden="true" />
						Disable
					{:else}
						<Power class="h-4 w-4" aria-hidden="true" />
						Enable
					{/if}
				</Button>
				<Button size="sm" variant="danger-soft" onclick={() => onaction('delete', peer)}>
					<Trash2 class="h-4 w-4" aria-hidden="true" />
					Delete
				</Button>
			{/if}
		{/snippet}
	</Drawer>
{/if}

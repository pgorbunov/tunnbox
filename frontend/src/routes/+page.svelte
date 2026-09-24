<script lang="ts">
	/** Dashboard: stat tiles, traffic chart, interfaces with toggles, top peers, recent activity. */
	import { Activity, ArrowDown, ArrowUp, Clock, Network, Plus, Users, UserX } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { Interface, Overview, StatsRange } from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { liveStatus } from '$lib/stores/live.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatBytes, formatDateTime, formatRelative } from '$lib/utils/format';
	import { createPoller, createTicker } from '$lib/utils/poll.svelte';
	import InterfaceStatusBadge from '$lib/components/app/InterfaceStatusBadge.svelte';
	import PageHeader from '$lib/components/app/PageHeader.svelte';
	import AreaChart from '$lib/components/charts/AreaChart.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import Stat from '$lib/components/ui/Stat.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';

	let range = $state<StatsRange>('24h');
	let overview = $state<Overview | null>(null);
	let interfaces = $state<Interface[]>([]);
	let toggling = $state<string | null>(null);

	const ticker = createTicker(15_000);
	const canWrite = $derived(auth.can('operator'));

	const poller = createPoller(
		async (signal) => {
			const [o, i] = await Promise.all([api.stats.overview(range, signal), api.interfaces.list(signal)]);
			overview = o;
			interfaces = i;
		},
		{ intervalMs: () => settingsStore.refreshMs }
	);

	$effect(() => poller.start());
	$effect(() => liveStatus.bind(poller));
	$effect(() => {
		void range;
		void poller.refresh();
	});

	async function toggle(iface: Interface, up: boolean) {
		const prev = interfaces;
		interfaces = interfaces.map((i) => (i.name === iface.name ? { ...i, enabled: up, is_active: up } : i));
		toggling = iface.name;
		try {
			const updated = up ? await api.interfaces.up(iface.name) : await api.interfaces.down(iface.name);
			interfaces = interfaces.map((i) => (i.name === updated.name ? updated : i));
			toast.success(`${updated.name} is ${updated.is_active ? 'up' : 'down'}`);
		} catch (err) {
			interfaces = prev;
			toast.error(`Could not bring ${iface.name} ${up ? 'up' : 'down'}`, {
				description: toApiError(err).detail
			});
		} finally {
			toggling = null;
		}
	}

	const RANGES = [
		{ value: '1h' as const, label: '1h' },
		{ value: '6h' as const, label: '6h' },
		{ value: '24h' as const, label: '24h' },
		{ value: '7d' as const, label: '7d' },
		{ value: '30d' as const, label: '30d' }
	];

	const loading = $derived(poller.loading && !overview);
</script>

<svelte:head>
	<title>Dashboard · TunnBox</title>
</svelte:head>

<PageHeader title="Dashboard" description="Live overview of your WireGuard server.">
	{#snippet actions()}
		<SegmentedControl bind:value={range} label="Time range" options={RANGES} />
	{/snippet}
</PageHeader>

{#if poller.error && !overview}
	<ErrorState message={poller.error.detail} onretry={() => poller.refresh()} retrying={poller.refreshing} />
{:else}
	<div class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-6">
		<Stat
			label="Interfaces"
			value={overview?.interfaces_active}
			suffix={overview ? `/ ${overview.interfaces_total} up` : undefined}
			{loading}
			href="/interfaces"
		>
			{#snippet icon()}<Network class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat
			label="Peers online"
			value={overview?.peers_online}
			suffix={overview ? `/ ${overview.peers_total}` : undefined}
			tone="success"
			{loading}
			href="/peers?status=online"
		>
			{#snippet icon()}<Users class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat
			label="Disabled"
			value={overview?.peers_disabled}
			tone="warning"
			{loading}
			href="/peers?status=disabled"
		>
			{#snippet icon()}<UserX class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat
			label="Expiring in 7 days"
			value={overview?.peers_expiring_7d}
			tone={overview && overview.peers_expiring_7d > 0 ? 'danger' : 'default'}
			{loading}
		>
			{#snippet icon()}<Clock class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat
			label="Download"
			value={overview ? formatBytes(overview.rx_total) : null}
			hint={`Last ${range}`}
			tone="download"
			{loading}
		>
			{#snippet icon()}<ArrowDown class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat
			label="Upload"
			value={overview ? formatBytes(overview.tx_total) : null}
			hint={`Last ${range}`}
			tone="upload"
			{loading}
		>
			{#snippet icon()}<ArrowUp class="h-4 w-4" />{/snippet}
		</Stat>
	</div>

	<div class="mt-6 grid gap-6 xl:grid-cols-3">
		<Card title="Traffic" description={`All interfaces · last ${range}`} class="xl:col-span-2">
			<AreaChart
				points={overview?.series ?? []}
				title="Traffic across all interfaces"
				{loading}
				refreshing={poller.refreshing && !!overview}
			/>
		</Card>

		<Card title="Top peers" description={`By traffic · last ${range}`} flush>
			{#if loading}
				<div class="divide-y divide-border">
					{#each [1, 2, 3] as i (i)}<div class="px-5 py-3"><Skeleton class="h-4 w-40" /></div>{/each}
				</div>
			{:else if !overview || overview.top_peers.length === 0}
				<EmptyState
					compact
					title="No traffic yet"
					description="Peers appear here once they start moving data."
				/>
			{:else}
				{@const max = Math.max(1, ...overview.top_peers.map((p) => p.rx + p.tx))}
				<ol class="divide-y divide-border">
					{#each overview.top_peers as p (p.peer_id)}
						<li class="px-5 py-3">
							<div class="flex items-center justify-between gap-3 text-sm">
								<a
									href={`/interfaces/${encodeURIComponent(p.interface_name)}?peer=${p.peer_id}`}
									class="min-w-0 truncate font-medium text-fg hover:underline">{p.name}</a
								>
								<span class="shrink-0 text-[13px] text-fg-muted tabular">{formatBytes(p.rx + p.tx)}</span>
							</div>
							<div
								class="mt-1.5 flex h-1.5 w-full overflow-hidden rounded-full bg-bg-subtle"
								aria-hidden="true"
							>
								<span class="h-full bg-chart-download" style={`width:${((p.rx / max) * 100).toFixed(1)}%`}
								></span>
								<span class="ml-px h-full bg-chart-upload" style={`width:${((p.tx / max) * 100).toFixed(1)}%`}
								></span>
							</div>
							<p class="mt-1 text-[12px] text-fg-subtle">
								<span class="font-mono">{p.interface_name}</span> · <span class="sr-only">Download</span>↓ {formatBytes(
									p.rx
								)} · <span class="sr-only">Upload</span>↑ {formatBytes(p.tx)}
							</p>
						</li>
					{/each}
				</ol>
			{/if}
		</Card>
	</div>

	<div class="mt-6 grid gap-6 xl:grid-cols-3">
		<Card title="Interfaces" flush class="xl:col-span-2">
			{#snippet actions()}
				{#if canWrite}
					<Button size="sm" href="/interfaces?new=1">
						<Plus class="h-4 w-4" aria-hidden="true" />
						New interface
					</Button>
				{/if}
			{/snippet}
			{#if loading}
				<div class="divide-y divide-border">
					{#each [1, 2] as i (i)}<div class="px-5 py-4">
							<Skeleton class="h-4 w-32" /><Skeleton class="mt-2 h-3 w-48" />
						</div>{/each}
				</div>
			{:else if interfaces.length === 0}
				<EmptyState
					compact
					title="No interfaces yet"
					description="Create a WireGuard interface to start adding peers."
				>
					{#snippet icon()}<Network class="h-6 w-6" />{/snippet}
					{#snippet actions()}
						{#if canWrite}
							<Button variant="primary" href="/interfaces?new=1"
								><Plus class="h-4 w-4" aria-hidden="true" />Create interface</Button
							>
						{/if}
					{/snippet}
				</EmptyState>
			{:else}
				<ul class="divide-y divide-border">
					{#each interfaces as iface (iface.id)}
						<li class="flex items-center gap-4 px-5 py-3">
							<div class="min-w-0 flex-1">
								<a
									href={`/interfaces/${encodeURIComponent(iface.name)}`}
									class="font-mono text-sm font-semibold text-fg hover:underline">{iface.name}</a
								>
								<p class="mt-0.5 truncate text-[13px] text-fg-subtle">
									<span class="font-mono">{iface.address}</span> · :{iface.listen_port} · {iface.online_peer_count}/{iface.peer_count}
									peers online
								</p>
							</div>
							<InterfaceStatusBadge {iface} size="sm" />
							{#if canWrite}
								<Switch
									checked={iface.enabled}
									label={`${iface.enabled ? 'Bring down' : 'Bring up'} ${iface.name}`}
									hideLabel
									size="sm"
									loading={toggling === iface.name}
									onchange={(v) => toggle(iface, v)}
								/>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</Card>

		<Card title="Recent activity" flush>
			{#snippet actions()}
				{#if auth.can('operator')}
					<Button size="sm" variant="ghost" href="/audit">View all</Button>
				{/if}
			{/snippet}
			{#if loading}
				<div class="divide-y divide-border">
					{#each [1, 2, 3, 4] as i (i)}<div class="px-5 py-3"><Skeleton class="h-3.5 w-52" /></div>{/each}
				</div>
			{:else if !overview || overview.recent_activity.length === 0}
				<EmptyState compact title="Nothing yet" description="Actions taken in TunnBox show up here.">
					{#snippet icon()}<Activity class="h-6 w-6" />{/snippet}
				</EmptyState>
			{:else}
				<ol class="divide-y divide-border">
					{#each overview.recent_activity as a (a.id)}
						<li class="flex items-start gap-3 px-5 py-2.5 text-[13px]">
							<span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-subtle/60" aria-hidden="true"
							></span>
							<div class="min-w-0 flex-1">
								<p class="text-fg">
									<span class="font-medium">{a.username ?? 'system'}</span>
									<span class="text-fg-muted"> · </span>
									<code class="font-mono text-[12px] text-fg-muted">{a.action}</code>
									{#if a.target}<span class="text-fg-muted"> → </span><span
											class="font-mono text-[12px] text-fg">{a.target}</span
										>{/if}
								</p>
								<p class="text-[12px] text-fg-subtle" title={formatDateTime(a.created_at)}>
									{formatRelative(a.created_at, ticker.now)}
								</p>
							</div>
						</li>
					{/each}
				</ol>
			{/if}
		</Card>
	</div>
{/if}

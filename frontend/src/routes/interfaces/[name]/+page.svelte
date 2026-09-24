<script lang="ts">
	/**
	 * Interface detail: header (status, toggle, actions), stat tiles, traffic chart,
	 * tabs Peers / Settings / Activity.
	 */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		Activity,
		ArrowDown,
		ArrowUp,
		Download,
		MoreHorizontal,
		Plus,
		Search,
		Settings2,
		Trash2,
		Users,
		Wifi
	} from 'lucide-svelte';
	import { api, isAbortError, toApiError } from '$lib/api';
	import type {
		AuditEntry,
		Interface,
		Peer,
		PeerSort,
		PeerStatus,
		SortOrder,
		StatsRange,
		StatsResponse
	} from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { liveStatus } from '$lib/stores/live.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatBytes, formatDateTime, formatRelative } from '$lib/utils/format';
	import { createPoller } from '$lib/utils/poll.svelte';
	import InterfaceStatusBadge from '$lib/components/app/InterfaceStatusBadge.svelte';
	import PageHeader from '$lib/components/app/PageHeader.svelte';
	import AreaChart from '$lib/components/charts/AreaChart.svelte';
	import InterfaceSettingsPanel from '$lib/components/interfaces/InterfaceSettingsPanel.svelte';
	import PeerManager from '$lib/components/peers/PeerManager.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import DropdownMenu, { type MenuItem } from '$lib/components/ui/DropdownMenu.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';
	import Select from '$lib/components/ui/Select.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import Stat from '$lib/components/ui/Stat.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import Tabs from '$lib/components/ui/Tabs.svelte';

	type Tab = 'peers' | 'settings' | 'activity';

	const name = $derived(decodeURIComponent(page.params.name ?? ''));
	const canWrite = $derived(auth.can('operator'));
	const isAdmin = $derived(auth.can('admin'));

	let iface = $state<Interface | null>(null);
	let peers = $state<Peer[]>([]);
	let stats = $state<StatsResponse | null>(null);
	let range = $state<StatsRange>('24h');
	let tab = $state<Tab>('peers');
	let notFound = $state(false);

	let query = $state('');
	let statusFilter = $state<PeerStatus | ''>('');
	let sortKey = $state<PeerSort>('name');
	let sortOrder = $state<SortOrder>('asc');

	let toggling = $state(false);
	let createOpen = $state(false);
	let focusPeerId = $state<number | null>(null);
	let deleteOpen = $state(false);
	let deleting = $state(false);
	let downloading = $state(false);

	let activity = $state<AuditEntry[]>([]);
	let activityLoading = $state(false);
	let activityError = $state<string | null>(null);

	const poller = createPoller(
		async (signal) => {
			const n = name;
			try {
				const [i, p, s] = await Promise.all([
					api.interfaces.get(n, signal),
					api.interfaces.peers(
						n,
						{
							q: debouncedQuery || undefined,
							status: statusFilter || undefined,
							sort: sortKey,
							order: sortOrder
						},
						signal
					),
					api.interfaces.stats(n, range, signal)
				]);
				iface = i;
				peers = p;
				stats = s;
				notFound = false;
			} catch (err) {
				if (toApiError(err).status === 404) notFound = true;
				throw err;
			}
		},
		{ intervalMs: () => settingsStore.refreshMs, immediate: false }
	);
	$effect(() => poller.start());
	$effect(() => liveStatus.bind(poller));
	$effect(() => {
		// Re-fetch when any query input changes.
		void name;
		void range;
		void debouncedQuery;
		void statusFilter;
		void sortKey;
		void sortOrder;
		void poller.refresh();
	});

	// URL hooks: ?new=peer opens the create form, ?peer=<id> opens the drawer, ?tab= selects a tab.
	$effect(() => {
		const sp = page.url.searchParams;
		const t = sp.get('tab');
		if (t === 'peers' || t === 'settings' || t === 'activity') tab = t;
		const wantsNew = sp.get('new') === 'peer';
		const peerId = Number(sp.get('peer'));
		if (wantsNew && canWrite) createOpen = true;
		if (peerId) focusPeerId = peerId;
		if (wantsNew || peerId)
			void goto(`/interfaces/${encodeURIComponent(name)}`, { replaceState: true, noScroll: true });
	});

	let activityAbort: AbortController | null = null;
	async function loadActivity() {
		activityAbort?.abort();
		const ctl = new AbortController();
		activityAbort = ctl;
		activityLoading = true;
		activityError = null;
		try {
			const res = await api.audit.list({ q: name, page_size: 50 }, ctl.signal);
			if (ctl.signal.aborted) return;
			activity = res.items.filter(
				(a) => a.target === name || a.target?.startsWith(`${name}/`) || a.action.startsWith('interface.')
			);
		} catch (err) {
			if (isAbortError(err)) return;
			activityError = toApiError(err).detail;
		} finally {
			if (!ctl.signal.aborted) activityLoading = false;
		}
	}
	$effect(() => {
		if (tab === 'activity' && auth.can('operator')) void loadActivity();
		return () => activityAbort?.abort();
	});

	// Debounce the search box so each keystroke doesn't restart the poller.
	let debouncedQuery = $state('');
	$effect(() => {
		const q = query.trim();
		const t = setTimeout(() => (debouncedQuery = q), 200);
		return () => clearTimeout(t);
	});

	async function toggle(up: boolean) {
		if (!iface) return;
		const prev = iface;
		iface = { ...iface, enabled: up, is_active: up };
		toggling = true;
		try {
			iface = up ? await api.interfaces.up(prev.name) : await api.interfaces.down(prev.name);
			toast.success(`${iface.name} is ${iface.is_active ? 'up' : 'down'}`);
		} catch (err) {
			iface = prev;
			toast.error(`Could not bring ${prev.name} ${up ? 'up' : 'down'}`, {
				description: toApiError(err).detail
			});
		} finally {
			toggling = false;
		}
	}

	async function downloadServerConfig() {
		if (!iface) return;
		downloading = true;
		try {
			await api.interfaces.downloadConfig(iface.name);
		} catch (err) {
			toast.error('Download failed', { description: toApiError(err).detail });
		} finally {
			downloading = false;
		}
	}

	async function confirmDelete() {
		if (!iface) return;
		deleting = true;
		try {
			await api.interfaces.remove(iface.name);
			toast.success(`Interface ${iface.name} deleted`);
			deleteOpen = false;
			void goto('/interfaces');
		} catch (err) {
			toast.error('Could not delete interface', { description: toApiError(err).detail });
		} finally {
			deleting = false;
		}
	}

	const menuItems = $derived<MenuItem[]>([
		{ label: 'Edit settings', icon: Settings2, onselect: () => (tab = 'settings'), hidden: !canWrite },
		{
			label: 'Download server config',
			icon: Download,
			onselect: () => void downloadServerConfig(),
			hidden: !isAdmin
		},
		{
			label: 'Delete interface',
			icon: Trash2,
			danger: true,
			separator: true,
			onselect: () => (deleteOpen = true),
			hidden: !canWrite
		}
	]);

	const tabs = $derived([
		{ id: 'peers' as const, label: 'Peers', icon: Users, count: iface?.peer_count ?? null },
		{ id: 'settings' as const, label: 'Settings', icon: Settings2 },
		{ id: 'activity' as const, label: 'Activity', icon: Activity, hidden: !auth.can('operator') }
	]);

	const RANGES = [
		{ value: '1h' as const, label: '1h' },
		{ value: '6h' as const, label: '6h' },
		{ value: '24h' as const, label: '24h' },
		{ value: '7d' as const, label: '7d' },
		{ value: '30d' as const, label: '30d' }
	];
	const STATUS_OPTIONS = [
		{ value: '', label: 'All statuses' },
		{ value: 'online', label: 'Online' },
		{ value: 'offline', label: 'Offline' },
		{ value: 'disabled', label: 'Disabled' },
		{ value: 'expired', label: 'Expired' }
	];

	const loading = $derived(poller.loading && !iface);
	const filtered = $derived(!!query.trim() || !!statusFilter);
</script>

<svelte:head>
	<title>{name} · TunnBox</title>
</svelte:head>

{#if notFound}
	<ErrorState
		title="Interface not found"
		message={`There is no interface named "${name}".`}
		onretry={() => goto('/interfaces')}
	/>
{:else if poller.error && !iface}
	<ErrorState message={poller.error.detail} onretry={() => poller.refresh()} retrying={poller.refreshing} />
{:else}
	<PageHeader
		title={name}
		mono
		description={iface
			? `${iface.address} · UDP ${iface.listen_port}${iface.public_endpoint ? ` · ${iface.public_endpoint}` : ''}`
			: undefined}
	>
		{#snippet badge()}
			{#if iface}<InterfaceStatusBadge {iface} />{/if}
		{/snippet}
		{#snippet actions()}
			{#if iface && canWrite}
				<Switch
					checked={iface.enabled}
					label={iface.enabled ? 'Interface up' : 'Interface down'}
					size="sm"
					loading={toggling}
					onchange={(v) => toggle(v)}
				/>
				<Button variant="primary" onclick={() => (createOpen = true)}>
					<Plus class="h-4 w-4" aria-hidden="true" />
					New peer
				</Button>
			{/if}
			{#if iface && (canWrite || isAdmin)}
				<DropdownMenu items={menuItems} label="Interface actions">
					{#snippet trigger({ toggle: open, props })}
						<IconButton
							label="More actions"
							variant="outline"
							onclick={open}
							loading={downloading}
							{...props}
						>
							<MoreHorizontal class="h-4 w-4" />
						</IconButton>
					{/snippet}
				</DropdownMenu>
			{/if}
		{/snippet}
	</PageHeader>

	<div class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
		<Stat label="Peers" value={iface?.peer_count} {loading}>
			{#snippet icon()}<Users class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat label="Online" value={iface?.online_peer_count} tone="success" {loading}>
			{#snippet icon()}<Wifi class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat label="Download" value={iface ? formatBytes(iface.rx_total) : null} tone="download" {loading}>
			{#snippet icon()}<ArrowDown class="h-4 w-4" />{/snippet}
		</Stat>
		<Stat label="Upload" value={iface ? formatBytes(iface.tx_total) : null} tone="upload" {loading}>
			{#snippet icon()}<ArrowUp class="h-4 w-4" />{/snippet}
		</Stat>
	</div>

	<Card title="Traffic" class="mt-6">
		{#snippet actions()}
			<SegmentedControl bind:value={range} label="Time range" options={RANGES} />
		{/snippet}
		<AreaChart
			points={stats?.points ?? []}
			bucketSeconds={stats?.bucket_seconds}
			title={`Traffic on ${name}`}
			{loading}
			refreshing={poller.refreshing && !!stats}
		/>
	</Card>

	<div class="mt-6">
		<Tabs {tabs} bind:value={tab} label="Interface sections" idPrefix="iface" />
	</div>

	{#if tab === 'peers'}
		<div id="iface-panel-peers" role="tabpanel" aria-labelledby="iface-peers" class="mt-4">
			<Card flush>
				<div class="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
					<Input
						label="Search peers"
						hideLabel
						bind:value={query}
						placeholder="Search peers…"
						size="sm"
						class="w-full sm:w-64"
						data-hotkey-search
						type="search"
					>
						{#snippet leading()}<Search class="h-4 w-4" />{/snippet}
					</Input>
					<Select
						label="Status"
						hideLabel
						size="sm"
						bind:value={statusFilter}
						options={STATUS_OPTIONS}
						class="w-40"
					/>
				</div>
				{#if iface}
					<PeerManager
						{peers}
						interfaces={[iface]}
						{iface}
						loading={poller.loading && peers.length === 0}
						refreshing={poller.refreshing}
						bind:createOpen
						bind:focusPeerId
						{sortKey}
						{sortOrder}
						onsort={(k, o) => {
							sortKey = k as PeerSort;
							sortOrder = o;
						}}
						onupdated={(p) => (peers = peers.map((x) => (x.id === p.id ? p : x)))}
						oncreated={(p) => {
							peers = [p, ...peers];
							void poller.refresh();
						}}
						ondeleted={(ids) => {
							peers = peers.filter((x) => !ids.includes(x.id));
							void poller.refresh();
						}}
						onrefresh={() => void poller.refresh()}
					>
						{#snippet empty()}
							{#if filtered}
								<EmptyState compact title="No peers match" description="Try another search term or status.">
									{#snippet actions()}
										<Button
											size="sm"
											onclick={() => {
												query = '';
												statusFilter = '';
											}}
										>
											Clear filters
										</Button>
									{/snippet}
								</EmptyState>
							{:else}
								<EmptyState
									title="No peers yet"
									description="Add a device: TunnBox generates its keys and shows a QR code you can scan right away."
								>
									{#snippet icon()}<Users class="h-6 w-6" />{/snippet}
									{#snippet actions()}
										{#if canWrite}
											<Button variant="primary" onclick={() => (createOpen = true)}>
												<Plus class="h-4 w-4" aria-hidden="true" />
												Add first peer
											</Button>
										{/if}
									{/snippet}
								</EmptyState>
							{/if}
						{/snippet}
					</PeerManager>
				{:else}
					<div class="p-4"><Skeleton class="h-40 w-full" rounded="md" /></div>
				{/if}
			</Card>
		</div>
	{:else if tab === 'settings'}
		<div id="iface-panel-settings" role="tabpanel" aria-labelledby="iface-settings" class="mt-4">
			{#if iface}
				<InterfaceSettingsPanel {iface} {canWrite} onsaved={(i) => (iface = i)} />
			{/if}
		</div>
	{:else if tab === 'activity'}
		<div id="iface-panel-activity" role="tabpanel" aria-labelledby="iface-activity" class="mt-4">
			<Card title="Activity" description={`Audit entries mentioning ${name}`} flush>
				{#snippet actions()}
					<Button size="sm" variant="ghost" href={`/audit?q=${encodeURIComponent(name)}`}
						>Open in audit log</Button
					>
				{/snippet}
				{#if activityLoading}
					<div class="divide-y divide-border">
						{#each [1, 2, 3] as i (i)}<div class="px-5 py-3"><Skeleton class="h-3.5 w-64" /></div>{/each}
					</div>
				{:else if activityError}
					<ErrorState compact message={activityError} onretry={loadActivity} />
				{:else if activity.length === 0}
					<EmptyState compact title="No activity yet" />
				{:else}
					<ol class="divide-y divide-border">
						{#each activity as a (a.id)}
							<li class="flex items-start gap-3 px-5 py-2.5 text-[13px]">
								<span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-subtle/60" aria-hidden="true"
								></span>
								<div class="min-w-0 flex-1">
									<p class="text-fg">
										<span class="font-medium">{a.username ?? 'system'}</span>
										<span class="text-fg-muted"> · </span>
										<code class="font-mono text-[12px] text-fg-muted">{a.action}</code>
										{#if a.target}<span class="text-fg-muted"> → </span><span class="font-mono text-[12px]"
												>{a.target}</span
											>{/if}
									</p>
									<p class="text-[12px] text-fg-subtle" title={formatDateTime(a.created_at)}>
										{formatRelative(a.created_at)}
									</p>
								</div>
							</li>
						{/each}
					</ol>
				{/if}
			</Card>
		</div>
	{/if}

	<ConfirmDialog
		bind:open={deleteOpen}
		title={`Delete ${name}?`}
		message={`This brings the interface down and permanently deletes it together with all ${iface?.peer_count ?? 0} of its peers.`}
		confirmLabel="Delete interface"
		confirmText={name}
		loading={deleting}
		onconfirm={confirmDelete}
	/>
{/if}

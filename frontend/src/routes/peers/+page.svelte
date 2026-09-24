<script lang="ts">
	/** Global peer search across interfaces (paginated), same table + drawer. */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Search, Users } from 'lucide-svelte';
	import { api } from '$lib/api';
	import type { Interface, Peer, PeerStatus } from '$lib/api/types';
	import { liveStatus } from '$lib/stores/live.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { createPoller } from '$lib/utils/poll.svelte';
	import PageHeader from '$lib/components/app/PageHeader.svelte';
	import PeerManager from '$lib/components/peers/PeerManager.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import Select from '$lib/components/ui/Select.svelte';

	const STATUS_OPTIONS = [
		{ value: '', label: 'All statuses' },
		{ value: 'online', label: 'Online' },
		{ value: 'offline', label: 'Offline' },
		{ value: 'disabled', label: 'Disabled' },
		{ value: 'expired', label: 'Expired' }
	];

	const initialStatus = page.url.searchParams.get('status');
	let query = $state(page.url.searchParams.get('q') ?? '');
	let ifaceFilter = $state(page.url.searchParams.get('interface') ?? '');
	let statusFilter = $state<PeerStatus | ''>(
		initialStatus === 'online' ||
			initialStatus === 'offline' ||
			initialStatus === 'disabled' ||
			initialStatus === 'expired'
			? initialStatus
			: ''
	);
	let pageNo = $state(1);
	let pageSize = $state(25);
	let peers = $state<Peer[]>([]);
	let total = $state(0);
	let interfaces = $state<Interface[]>([]);
	let debounced = $state('');
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;

	$effect(() => {
		const q = query;
		if (debounceTimer) clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			debounced = q.trim();
			pageNo = 1;
		}, 250);
		return () => {
			if (debounceTimer) clearTimeout(debounceTimer);
		};
	});

	const poller = createPoller(
		async (signal) => {
			const [res, ifs] = await Promise.all([
				api.peers.search(
					{
						q: debounced || undefined,
						interface: ifaceFilter || undefined,
						status: statusFilter || undefined,
						page: pageNo,
						page_size: pageSize
					},
					signal
				),
				api.interfaces.list(signal)
			]);
			peers = res.items;
			total = res.total;
			interfaces = ifs;
		},
		{ intervalMs: () => settingsStore.refreshMs, immediate: false }
	);
	$effect(() => poller.start());
	$effect(() => liveStatus.bind(poller));
	$effect(() => {
		void debounced;
		void ifaceFilter;
		void statusFilter;
		void pageNo;
		void pageSize;
		void poller.refresh();
	});

	// Keep the URL shareable.
	$effect(() => {
		const sp = new URLSearchParams();
		if (debounced) sp.set('q', debounced);
		if (ifaceFilter) sp.set('interface', ifaceFilter);
		if (statusFilter) sp.set('status', statusFilter);
		const s = sp.toString();
		const target = s ? `/peers?${s}` : '/peers';
		if (page.url.pathname + page.url.search !== target)
			void goto(target, { replaceState: true, noScroll: true, keepFocus: true });
	});

	const filtered = $derived(!!debounced || !!ifaceFilter || !!statusFilter);
	const ifaceOptions = $derived([
		{ value: '', label: 'All interfaces' },
		...interfaces.map((i) => ({ value: i.name, label: i.name }))
	]);
</script>

<svelte:head>
	<title>Peers · TunnBox</title>
</svelte:head>

<PageHeader title="Peers" description="Every peer across all interfaces.">
	<div class="flex flex-wrap items-center gap-2">
		<Input
			label="Search peers"
			hideLabel
			bind:value={query}
			placeholder="Search by name, address or key…"
			size="sm"
			class="w-full sm:w-72"
			data-hotkey-search
			type="search"
		>
			{#snippet leading()}<Search class="h-4 w-4" />{/snippet}
		</Input>
		<Select
			label="Interface"
			hideLabel
			size="sm"
			bind:value={ifaceFilter}
			options={ifaceOptions}
			class="w-40"
			onchange={() => (pageNo = 1)}
		/>
		<Select
			label="Status"
			hideLabel
			size="sm"
			bind:value={statusFilter}
			options={STATUS_OPTIONS}
			class="w-40"
			onchange={() => (pageNo = 1)}
		/>
	</div>
</PageHeader>

{#if poller.error && peers.length === 0}
	<ErrorState message={poller.error.detail} onretry={() => poller.refresh()} retrying={poller.refreshing} />
{:else}
	<Card flush>
		<PeerManager
			{peers}
			{interfaces}
			loading={poller.loading && peers.length === 0}
			refreshing={poller.refreshing}
			showInterface
			onupdated={(p) => (peers = peers.map((x) => (x.id === p.id ? p : x)))}
			oncreated={() => void poller.refresh()}
			ondeleted={(ids) => {
				peers = peers.filter((x) => !ids.includes(x.id));
				void poller.refresh();
			}}
			onrefresh={() => void poller.refresh()}
		>
			{#snippet empty()}
				{#if filtered}
					<EmptyState compact title="No peers match" description="Try another search or clear the filters.">
						{#snippet actions()}
							<Button
								size="sm"
								onclick={() => {
									query = '';
									ifaceFilter = '';
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
						description="Peers are created on an interface. Open one to add your first device."
					>
						{#snippet icon()}<Users class="h-6 w-6" />{/snippet}
						{#snippet actions()}
							<Button variant="primary" href="/interfaces">Go to interfaces</Button>
						{/snippet}
					</EmptyState>
				{/if}
			{/snippet}
		</PeerManager>
		{#if total > 0}
			<div class="border-t border-border px-4 py-3">
				<Pagination bind:page={pageNo} bind:pageSize {total} />
			</div>
		{/if}
	</Card>
{/if}

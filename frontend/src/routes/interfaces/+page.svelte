<script lang="ts">
	/** Interfaces: card grid with status filter, sort and the create wizard (?new=1). */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Network, Plus, Search } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { Interface } from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { liveStatus } from '$lib/stores/live.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { createPoller } from '$lib/utils/poll.svelte';
	import PageHeader from '$lib/components/app/PageHeader.svelte';
	import InterfaceCard from '$lib/components/interfaces/InterfaceCard.svelte';
	import InterfaceForm from '$lib/components/interfaces/InterfaceForm.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';
	import Select from '$lib/components/ui/Select.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';

	type Filter = 'all' | 'active' | 'inactive';
	type Sort = 'name' | 'peers' | 'traffic' | 'created';

	let interfaces = $state<Interface[]>([]);
	let filter = $state<Filter>('all');
	let sort = $state<Sort>('name');
	let query = $state('');
	let createOpen = $state(false);
	let toggling = $state<string | null>(null);

	const canWrite = $derived(auth.can('operator'));

	const poller = createPoller(
		async (signal) => {
			interfaces = await api.interfaces.list(signal);
		},
		{ intervalMs: () => settingsStore.refreshMs }
	);
	$effect(() => poller.start());
	$effect(() => liveStatus.bind(poller));

	// ?new=1 opens the wizard (from setup / command palette / dashboard).
	$effect(() => {
		if (page.url.searchParams.get('new') === '1' && canWrite) {
			createOpen = true;
			void goto('/interfaces', { replaceState: true, noScroll: true });
		}
	});

	const visible = $derived.by(() => {
		const q = query.trim().toLowerCase();
		const list = interfaces.filter((i) => {
			if (filter === 'active' && !i.is_active) return false;
			if (filter === 'inactive' && i.is_active) return false;
			if (q && !`${i.name} ${i.address} ${i.listen_port}`.toLowerCase().includes(q)) return false;
			return true;
		});
		const cmp: Record<Sort, (a: Interface, b: Interface) => number> = {
			name: (a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }),
			peers: (a, b) => b.peer_count - a.peer_count || a.name.localeCompare(b.name),
			traffic: (a, b) => b.rx_total + b.tx_total - (a.rx_total + a.tx_total),
			created: (a, b) => b.created_at.localeCompare(a.created_at)
		};
		return [...list].sort(cmp[sort]);
	});

	const counts = $derived({
		all: interfaces.length,
		active: interfaces.filter((i) => i.is_active).length,
		inactive: interfaces.filter((i) => !i.is_active).length
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

	function oncreated(iface: Interface) {
		interfaces = [...interfaces, iface];
		void goto(`/interfaces/${encodeURIComponent(iface.name)}?new=peer`);
	}
</script>

<svelte:head>
	<title>Interfaces · TunnBox</title>
</svelte:head>

<PageHeader title="Interfaces" description="WireGuard interfaces on this server.">
	{#snippet actions()}
		{#if canWrite}
			<Button variant="primary" onclick={() => (createOpen = true)}>
				<Plus class="h-4 w-4" aria-hidden="true" />
				New interface
			</Button>
		{/if}
	{/snippet}
	<div class="flex flex-wrap items-center gap-2">
		<Input
			label="Search interfaces"
			hideLabel
			bind:value={query}
			placeholder="Search…"
			size="sm"
			class="w-full sm:w-56"
			data-hotkey-search
			type="search"
		>
			{#snippet leading()}<Search class="h-4 w-4" />{/snippet}
		</Input>
		<SegmentedControl
			bind:value={filter}
			label="Status filter"
			options={[
				{ value: 'all', label: `All (${counts.all})` },
				{ value: 'active', label: `Up (${counts.active})` },
				{ value: 'inactive', label: `Down (${counts.inactive})` }
			]}
		/>
		<Select
			label="Sort"
			hideLabel
			size="sm"
			bind:value={sort}
			class="ml-auto w-40"
			options={[
				{ value: 'name', label: 'Sort: name' },
				{ value: 'peers', label: 'Sort: peers' },
				{ value: 'traffic', label: 'Sort: traffic' },
				{ value: 'created', label: 'Sort: newest' }
			]}
		/>
	</div>
</PageHeader>

{#if poller.loading && interfaces.length === 0}
	<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true">
		{#each [1, 2, 3] as i (i)}
			<div class="rounded-lg border border-border bg-surface p-4">
				<Skeleton class="h-5 w-24" /><Skeleton class="mt-2 h-3 w-40" /><Skeleton
					class="mt-5 h-12 w-full"
					rounded="md"
				/>
			</div>
		{/each}
	</div>
{:else if poller.error && interfaces.length === 0}
	<ErrorState message={poller.error.detail} onretry={() => poller.refresh()} retrying={poller.refreshing} />
{:else if interfaces.length === 0}
	<div class="rounded-lg border border-dashed border-border bg-surface">
		<EmptyState
			title="No interfaces yet"
			description="An interface is a WireGuard network with its own subnet and port. Create one to start adding peers."
		>
			{#snippet icon()}<Network class="h-6 w-6" />{/snippet}
			{#snippet actions()}
				{#if canWrite}
					<Button variant="primary" onclick={() => (createOpen = true)}>
						<Plus class="h-4 w-4" aria-hidden="true" />
						Create interface
					</Button>
				{:else}
					<p class="text-sm text-fg-subtle">Ask an operator or admin to create one.</p>
				{/if}
			{/snippet}
		</EmptyState>
	</div>
{:else if visible.length === 0}
	<div class="rounded-lg border border-dashed border-border bg-surface">
		<EmptyState compact title="No matches" description="Try a different search or filter.">
			{#snippet actions()}
				<Button
					size="sm"
					onclick={() => {
						query = '';
						filter = 'all';
					}}
				>
					Clear filters
				</Button>
			{/snippet}
		</EmptyState>
	</div>
{:else}
	<div
		class={`grid gap-4 transition-opacity sm:grid-cols-2 xl:grid-cols-3 ${poller.refreshing ? 'opacity-90' : ''}`}
	>
		{#each visible as iface (iface.id)}
			<InterfaceCard {iface} {canWrite} toggling={toggling === iface.name} ontoggle={toggle} />
		{/each}
	</div>
{/if}

{#if canWrite}
	<InterfaceForm bind:open={createOpen} existing={interfaces} {oncreated} />
{/if}

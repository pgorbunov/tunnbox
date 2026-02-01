<script lang="ts">
	import { onMount, onDestroy } from "svelte";
	import { interfaces } from "$lib/stores/interfaces";
	import InterfaceCard from "$lib/components/InterfaceCard.svelte";
	import Button from "$lib/components/Button.svelte";
	import { Plus, RefreshCw, Network } from "lucide-svelte";
	import { useAutoRefresh } from "$lib/utils/autoRefresh.svelte";

	let manualRefreshing = $state(false);

	// Set up auto-refresh (every 5 seconds)
	const autoRefresh = useAutoRefresh(async () => {
		await interfaces.load(true); // true = silent mode
	}, 5000);

	onMount(() => {
		interfaces.load();
	});

	async function handleRefresh() {
		manualRefreshing = true;
		await autoRefresh.manualRefresh();
		manualRefreshing = false;
	}
</script>

<svelte:head>
	<title>Interfaces - Tunnbox</title>
</svelte:head>

<div class="max-w-7xl mx-auto">
	<div
		class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8"
	>
		<div>
			<h1 class="text-2xl font-bold text-slate-900 dark:text-white">
				Interfaces
			</h1>
			<p class="text-slate-600 dark:text-slate-400 mt-1">
				All WireGuard interfaces on this server · Auto-updates every 5s
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button
				variant="secondary"
				onclick={handleRefresh}
				loading={manualRefreshing}
			>
				<RefreshCw class="h-4 w-4 mr-2" />
				Refresh
			</Button>
			<Button onclick={() => (window.location.href = "/interfaces/new")}>
				<Plus class="h-4 w-4 mr-2" />
				New Interface
			</Button>
		</div>
	</div>

	{#if $interfaces.loading}
		<div class="flex items-center justify-center py-12">
			<div
				class="h-8 w-8 border-4 border-slate-300 dark:border-slate-700 border-t-emerald-500 rounded-full animate-spin"
			></div>
		</div>
	{:else if $interfaces.error}
		<div class="text-center py-12">
			<p class="text-rose-600 dark:text-rose-400">{$interfaces.error}</p>
			<Button variant="secondary" class="mt-4" onclick={handleRefresh}
				>Try Again</Button
			>
		</div>
	{:else if $interfaces.interfaces.length === 0}
		<div
			class="text-center py-12 bg-slate-100 dark:bg-slate-800/30 rounded-xl border border-slate-200 dark:border-slate-700/50"
		>
			<Network
				class="h-12 w-12 text-slate-400 dark:text-slate-600 mx-auto mb-4"
			/>
			<h3 class="text-lg font-medium text-slate-900 dark:text-white mb-2">
				No interfaces found
			</h3>
			<p class="text-slate-600 dark:text-slate-400 mb-6">
				Create your first WireGuard interface to get started.
			</p>
			<Button onclick={() => (window.location.href = "/interfaces/new")}>
				<Plus class="h-4 w-4 mr-2" />
				Create Interface
			</Button>
		</div>
	{:else}
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each $interfaces.interfaces as iface (iface.name)}
				<InterfaceCard {iface} />
			{/each}
		</div>
	{/if}
</div>

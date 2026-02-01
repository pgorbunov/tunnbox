<script lang="ts">
	import { onMount } from "svelte";
	import { goto } from "$app/navigation";
	import { interfaces } from "$lib/stores/interfaces";
	import InterfaceCard from "$lib/components/InterfaceCard.svelte";
	import StatCard from "$lib/components/StatCard.svelte";
	import Button from "$lib/components/Button.svelte";
	import { useAutoRefresh } from "$lib/utils/autoRefresh.svelte";
	import {
		Plus,
		RefreshCw,
		Network,
		Shield,
		Users,
		Activity,
	} from "lucide-svelte";

	let refreshing = $state(false);

	const autoRefresh = useAutoRefresh(async () => {
		await interfaces.load(true);
	});

	onMount(() => {
		interfaces.load();
	});

	async function handleRefresh() {
		refreshing = true;
		await autoRefresh.manualRefresh();
		refreshing = false;
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return "0 B";
		const k = 1024;
		const sizes = ["B", "KB", "MB", "GB", "TB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
	}

	const stats = $derived.by(() => {
		const ifaces = $interfaces.interfaces;
		return {
			total: ifaces.length,
			active: ifaces.filter((i) => i.is_active).length,
			totalPeers: ifaces.reduce((sum, i) => sum + i.peer_count, 0),
			totalBandwidth: ifaces.reduce(
				(sum, i) => sum + i.total_transfer_rx + i.total_transfer_tx,
				0,
			),
		};
	});
</script>

<svelte:head>
	<title>Dashboard - TunnBox</title>
</svelte:head>

<div class="max-w-7xl mx-auto">
	<!-- Header -->
	<div
		class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8"
	>
		<div>
			<h1 class="text-2xl font-bold text-slate-900 dark:text-white">
				Dashboard
			</h1>
			<p class="text-slate-600 dark:text-slate-400 mt-1">
				Manage your WireGuard VPN interfaces
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button
				variant="secondary"
				onclick={handleRefresh}
				loading={refreshing}
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

	<!-- Stats -->
	<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
		<StatCard
			icon={Network}
			value={stats.total}
			label="Interfaces"
			color="blue"
			onclick={() => goto("/interfaces")}
		/>

		<StatCard
			icon={Shield}
			value={stats.active}
			label="Active"
			color="emerald"
			onclick={() => goto("/interfaces")}
		/>

		<StatCard
			icon={Users}
			value={stats.totalPeers}
			label="Total Peers"
			color="purple"
			onclick={() => goto("/interfaces")}
		/>

		<StatCard
			icon={Activity}
			value={formatBytes(stats.totalBandwidth)}
			label="Total Transfer"
			color="amber"
		/>
	</div>

	<!-- Interfaces Grid -->
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
			class="text-center py-16 bg-slate-100 dark:bg-slate-800/30 rounded-xl border border-slate-200 dark:border-slate-700/50"
		>
			<div class="max-w-md mx-auto px-6">
				<div class="mb-6 inline-flex p-4 rounded-full bg-blue-600/10">
					<Network class="h-12 w-12 text-blue-500" />
				</div>
				<h3
					class="text-xl font-semibold text-slate-900 dark:text-white mb-3"
				>
					No WireGuard Interfaces
				</h3>
				<p
					class="text-slate-600 dark:text-slate-400 mb-8 leading-relaxed"
				>
					Get started by creating your first WireGuard interface.
					You'll be able to add peers, manage connections, and monitor
					traffic in no time.
				</p>
				<Button
					onclick={() => (window.location.href = "/interfaces/new")}
					class="inline-flex"
				>
					<Plus class="h-4 w-4 mr-2" />
					Create Your First Interface
				</Button>
			</div>
		</div>
	{:else}
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each $interfaces.interfaces as iface (iface.name)}
				<InterfaceCard {iface} />
			{/each}
		</div>
	{/if}
</div>

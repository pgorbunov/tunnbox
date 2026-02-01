<script lang="ts">
	import { page } from "$app/stores";
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";
	import { api, type Interface, type Peer } from "$lib/api";
	import { interfaces, peers } from "$lib/stores/interfaces";
	import Button from "$lib/components/Button.svelte";
	import Toggle from "$lib/components/Toggle.svelte";
	import StatusBadge from "$lib/components/StatusBadge.svelte";
	import PeerCard from "$lib/components/PeerCard.svelte";
	import PeerModal from "$lib/components/PeerModal.svelte";
	import QRCodeModal from "$lib/components/QRCodeModal.svelte";
	import DeleteConfirmationModal from "$lib/components/DeleteConfirmationModal.svelte";
	import { useAutoRefresh } from "$lib/utils/autoRefresh.svelte";
	import {
		ArrowLeft,
		RefreshCw,
		Plus,
		Trash2,
		Copy,
		Check,
		ArrowDownToLine,
		ArrowUpFromLine,
		Network,
		Key,
		Edit,
		Save,
		X,
		HelpCircle,
		Server,
	} from "lucide-svelte";

	const interfaceName = $derived($page.params.name);

	let iface = $state<Interface | null>(null);
	let loading = $state(true);
	let manualRefreshing = $state(false);
	let toggling = $state(false);
	let deleting = $state(false);
	let copied = $state(false);
	let error = $state("");

	let showPeerModal = $state(false);
	let showQRModal = $state(false);
	let showDeleteModal = $state(false);
	let editingPeer = $state<Peer | null>(null);
	let qrPeer = $state<Peer | null>(null);

	// DNS editing state
	let editingDns = $state(false);
	let dnsValue = $state("");
	let dnsError = $state("");
	let savingSettings = $state(false);

	async function loadData(silent: boolean = false) {
		if (!loading && !silent) {
			// Only show loading spinner on initial load and manual refresh
			error = "";
		}
		try {
			iface = await api.getInterface(interfaceName);
			await peers.load(interfaceName, silent);
			error = "";
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load interface";
		} finally {
			loading = false;
		}
	}

	// Set up auto-refresh (every 5 seconds) for real-time stats - silent mode
	const autoRefresh = useAutoRefresh(async () => {
		await loadData(true); // true = silent mode
	}, 5000);

	onMount(() => {
		loadData();
	});

	async function handleRefresh() {
		manualRefreshing = true;
		await autoRefresh.manualRefresh();
		manualRefreshing = false;
	}

	async function handleToggle(checked: boolean) {
		if (!iface) return;
		toggling = true;
		try {
			await interfaces.toggle(interfaceName, checked);
			iface = await api.getInterface(interfaceName);
		} catch (e) {
			console.error("Failed to toggle:", e);
		} finally {
			toggling = false;
		}
	}

	function openDeleteModal() {
		showDeleteModal = true;
	}

	async function confirmDelete() {
		deleting = true;
		try {
			await api.deleteInterface(interfaceName);
			interfaces.removeInterface(interfaceName);
			showDeleteModal = false;
			goto("/interfaces");
		} catch (e) {
			console.error("Failed to delete:", e);
			alert("Failed to delete interface");
		} finally {
			deleting = false;
		}
	}

	async function handleCopyPublicKey() {
		if (!iface) return;
		try {
			await navigator.clipboard.writeText(iface.public_key);
			copied = true;
			setTimeout(() => (copied = false), 2000);
		} catch (e) {
			console.error("Failed to copy:", e);
		}
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return "0 B";
		const k = 1024;
		const sizes = ["B", "KB", "MB", "GB", "TB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
	}

	function openAddPeer() {
		editingPeer = null;
		showPeerModal = true;
	}

	function openEditPeer(peer: Peer) {
		editingPeer = peer;
		showPeerModal = true;
	}

	function openQRModal(peer: Peer) {
		qrPeer = peer;
		showQRModal = true;
	}

	async function handlePeerSaved(peer: Peer) {
		// Refresh interface data to update peer count and stats
		await loadData();

		// Show QR code for newly created peer
		if (!editingPeer) {
			qrPeer = peer;
			showQRModal = true;
		}
	}

	async function handlePeerDeleted() {
		// Refresh interface data to update peer count and stats
		await loadData();
	}

	// DNS editing functions
	function startEditDns() {
		dnsValue = iface?.dns || "";
		dnsError = "";
		editingDns = true;
	}

	function cancelEditDns() {
		editingDns = false;
		dnsError = "";
	}

	async function saveDns() {
		dnsError = "";

		// Validate DNS format (basic IP validation)
		if (dnsValue) {
			const servers = dnsValue.split(",").map((s) => s.trim());
			for (const server of servers) {
				const parts = server.split(".");
				if (parts.length !== 4) {
					dnsError = "Invalid DNS format. Expected IPv4 address(es)";
					return;
				}
				for (const part of parts) {
					const num = parseInt(part);
					if (isNaN(num) || num < 0 || num > 255) {
						dnsError = "Invalid DNS format. Octets must be  0-255";
						return;
					}
				}
			}
		}

		try {
			savingSettings = true;
			const updated = await api.updateInterface(interfaceName, {
				dns: dnsValue,
			});
			iface = updated;
			editingDns = false;
		} catch (e) {
			dnsError = e instanceof Error ? e.message : "Failed to update DNS";
		} finally {
			savingSettings = false;
		}
	}
</script>

<svelte:head>
	<title>{interfaceName} - Tunnbox</title>
</svelte:head>

<div class="max-w-5xl mx-auto">
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<div
				class="h-8 w-8 border-4 border-slate-700 border-t-emerald-500 rounded-full animate-spin"
			></div>
		</div>
	{:else if error}
		<div class="text-center py-12">
			<p class="text-rose-400 mb-4">{error}</p>
			<Button variant="secondary" onclick={() => goto("/interfaces")}>
				<ArrowLeft class="h-4 w-4 mr-2" />
				Back to Interfaces
			</Button>
		</div>
	{:else if iface}
		<!-- Header -->
		<div class="mb-8">
			<a
				href="/interfaces"
				class="inline-flex items-center text-slate-400 hover:text-slate-200 transition-colors mb-4"
			>
				<ArrowLeft class="h-4 w-4 mr-2" />
				Back to Interfaces
			</a>

			<div
				class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
			>
				<div class="flex items-center gap-4">
					<div
						class="p-3 rounded-xl {iface.is_active
							? 'bg-emerald-600/10 text-emerald-500'
							: 'bg-slate-700 text-slate-400'}"
					>
						<Network class="h-8 w-8" />
					</div>
					<div>
						<div class="flex items-center gap-3">
							<h1 class="text-2xl font-bold text-white">
								{iface.name}
							</h1>
							<StatusBadge
								status={iface.is_active ? "active" : "inactive"}
							/>
						</div>
						<p class="text-slate-400 mt-0.5">
							Port {iface.listen_port} &bull; {iface.address} &bull;
							Live updates
						</p>
					</div>
				</div>

				<div class="flex items-center gap-3">
					<Toggle
						checked={iface.is_active}
						loading={toggling}
						onchange={handleToggle}
					/>
					<Button
						variant="secondary"
						onclick={handleRefresh}
						loading={manualRefreshing}
					>
						<RefreshCw class="h-4 w-4" />
					</Button>
					<Button variant="danger" onclick={openDeleteModal}>
						<Trash2 class="h-4 w-4" />
					</Button>
				</div>
			</div>
		</div>

		<!-- Stats -->
		<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
			<div
				class="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 transition-all duration-300"
			>
				<p class="text-xs text-slate-500 uppercase tracking-wider mb-1">
					Peers
				</p>
				<p
					class="text-2xl font-bold text-white transition-all duration-300"
				>
					{iface.peer_count}
				</p>
			</div>

			<div
				class="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 transition-all duration-300"
			>
				<p class="text-xs text-slate-500 uppercase tracking-wider mb-1">
					Status
				</p>
				<p
					class="text-lg font-semibold {iface.is_active
						? 'text-emerald-500'
						: 'text-slate-400'} transition-all duration-300"
				>
					{iface.is_active ? "Active" : "Inactive"}
				</p>
			</div>

			<div
				class="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 transition-all duration-300"
			>
				<div class="flex items-center gap-2 mb-1">
					<ArrowDownToLine class="h-4 w-4 text-emerald-500" />
					<p class="text-xs text-slate-500 uppercase tracking-wider">
						Download
					</p>
				</div>
				<p
					class="text-2xl font-bold text-white transition-all duration-300"
				>
					{formatBytes(iface.total_transfer_rx)}
				</p>
			</div>

			<div
				class="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 transition-all duration-300"
			>
				<div class="flex items-center gap-2 mb-1">
					<ArrowUpFromLine class="h-4 w-4 text-blue-500" />
					<p class="text-xs text-slate-500 uppercase tracking-wider">
						Upload
					</p>
				</div>
				<p
					class="text-2xl font-bold text-white transition-all duration-300"
				>
					{formatBytes(iface.total_transfer_tx)}
				</p>
			</div>
		</div>

		<!-- Public Key -->
		<div
			class="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 mb-8"
		>
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<Key class="h-5 w-5 text-slate-400" />
					<div>
						<p
							class="text-xs text-slate-500 uppercase tracking-wider"
						>
							Public Key
						</p>
						<p class="text-sm font-mono text-slate-200 mt-0.5">
							{iface.public_key}
						</p>
					</div>
				</div>
				<Button variant="ghost" size="sm" onclick={handleCopyPublicKey}>
					{#if copied}
						<Check class="h-4 w-4 text-emerald-500" />
					{:else}
						<Copy class="h-4 w-4" />
					{/if}
				</Button>
			</div>
		</div>

		<!-- Peers Section -->
		<div class="flex items-center justify-between mb-4">
			<h2 class="text-lg font-semibold text-white">Peers</h2>
			<Button onclick={openAddPeer}>
				<Plus class="h-4 w-4 mr-2" />
				Add Peer
			</Button>
		</div>

		{#if $peers.loading}
			<div class="flex items-center justify-center py-8">
				<div
					class="h-6 w-6 border-4 border-slate-700 border-t-emerald-500 rounded-full animate-spin"
				></div>
			</div>
		{:else if $peers.peers.length === 0}
			<div
				class="text-center py-12 bg-slate-800/30 rounded-xl border border-slate-700/50"
			>
				<p class="text-slate-400 mb-4">No peers configured yet</p>
				<Button onclick={openAddPeer}>
					<Plus class="h-4 w-4 mr-2" />
					Add Your First Peer
				</Button>
			</div>
		{:else}
			<div class="grid gap-4 sm:grid-cols-2">
				{#each $peers.peers as peer (peer.public_key)}
					<PeerCard
						{peer}
						{interfaceName}
						onShowQR={openQRModal}
						onEdit={openEditPeer}
						onDelete={handlePeerDeleted}
					/>
				{/each}
			</div>
		{/if}
	{/if}
</div>

{#if showPeerModal}
	<PeerModal
		{interfaceName}
		peer={editingPeer}
		onClose={() => (showPeerModal = false)}
		onSaved={handlePeerSaved}
	/>
{/if}

{#if showQRModal && qrPeer}
	<QRCodeModal
		peer={qrPeer}
		{interfaceName}
		onClose={() => (showQRModal = false)}
	/>
{/if}

{#if showDeleteModal}
	<DeleteConfirmationModal
		title="Delete Interface"
		message="Are you sure you want to delete this interface? This will remove all peers and cannot be undone."
		itemName={interfaceName}
		loading={deleting}
		onConfirm={confirmDelete}
		onCancel={() => (showDeleteModal = false)}
	/>
{/if}

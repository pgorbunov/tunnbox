<script lang="ts">
	import type { Peer } from '$lib/api';
	import { api } from '$lib/api';
	import { peers } from '$lib/stores/interfaces';
	import Button from './Button.svelte';
	import StatusBadge from './StatusBadge.svelte';
	import DeleteConfirmationModal from './DeleteConfirmationModal.svelte';
	import {
		User,
		QrCode,
		Download,
		Pencil,
		Trash2,
		ArrowDownToLine,
		ArrowUpFromLine,
		Clock
	} from 'lucide-svelte';

	interface Props {
		peer: Peer;
		interfaceName: string;
		onShowQR: (peer: Peer) => void;
		onEdit: (peer: Peer) => void;
		onDelete?: () => void;
	}

	let { peer, interfaceName, onShowQR, onEdit, onDelete }: Props = $props();

	let deleting = $state(false);
	let downloading = $state(false);
	let showDeleteModal = $state(false);

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}

	function formatHandshake(dateStr: string | undefined): { text: string; color: string; tooltip: string } {
		if (!dateStr) {
			return { 
				text: 'Never', 
				color: 'text-slate-400',
				tooltip: 'No handshake recorded'
			};
		}
		
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffSec = Math.floor(diffMs / 1000);
		const diffMin = Math.floor(diffSec / 60);
		const diffHour = Math.floor(diffMin / 60);
		const diffDay = Math.floor(diffHour / 24);

		let text: string;
		let color: string;

		if (diffSec < 60) {
			text = `${diffSec}s ago`;
			color = 'text-emerald-500'; // Very recent - green
		} else if (diffMin < 5) {
			text = `${diffMin}m ago`;
			color = 'text-emerald-500'; // Recent - green
		} else if (diffMin < 60) {
			text = `${diffMin}m ago`;
			color = 'text-yellow-500'; // Getting stale - yellow
		} else if (diffHour < 24) {
			text = `${diffHour}h ago`;
			color = diffHour < 2 ? 'text-yellow-500' : 'text-rose-400'; // Yellow -> Red
		} else {
			text = `${diffDay}d ago`;
			color = 'text-rose-400'; // Very stale - red
		}

		// Format exact timestamp for tooltip
		const tooltip = date.toLocaleString('en-US', {
			dateStyle: 'medium',
			timeStyle: 'medium'
		});

		return { text, color, tooltip };
	}

	async function handleDownload() {
		downloading = true;
		try {
			const config = await api.getPeerConfig(interfaceName, peer.public_key);
			const blob = new Blob([config], { type: 'text/plain' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${peer.name}.conf`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (error) {
			console.error('Failed to download config:', error);
			alert('Failed to download configuration');
		} finally {
			downloading = false;
		}
	}

	function openDeleteModal() {
		showDeleteModal = true;
	}

	async function confirmDelete() {
		deleting = true;
		try {
			await api.deletePeer(interfaceName, peer.public_key);
			peers.removePeer(peer.public_key);
			showDeleteModal = false;

			// Notify parent to refresh interface data
			if (onDelete) {
				await onDelete();
			}
		} catch (error) {
			console.error('Failed to delete peer:', error);
			alert('Failed to delete peer');
		} finally {
			deleting = false;
		}
	}
</script>

<div
	class="bg-slate-800/50 rounded-xl border border-slate-700/50 hover:border-slate-600 transition-all duration-200"
>
	<div class="p-6">
		<!-- Header with peer name and status -->
		<div class="flex items-start justify-between mb-6">
			<div class="flex items-center gap-3">
				<div
					class="p-2.5 rounded-lg transition-all duration-300 {peer.is_online
						? 'bg-emerald-600/10 text-emerald-500'
						: 'bg-slate-700 text-slate-400'}"
				>
					<User class="h-5 w-5" />
				</div>
				<div>
					<h3 class="font-semibold text-white text-lg">{peer.name}</h3>
					<p class="text-xs text-slate-500 font-mono truncate max-w-[150px] mt-0.5">
						{peer.public_key.substring(0, 20)}...
					</p>
				</div>
			</div>
			<StatusBadge status={peer.is_online ? 'online' : 'offline'} />
		</div>

		<!-- Connection Information Section -->
		<div class="space-y-3 text-sm mb-5">
			<div class="flex items-center justify-between py-1">
				<span class="text-slate-400">Allowed IPs</span>
				<span class="text-slate-200 font-mono text-xs">{peer.allowed_ips}</span>
			</div>

			{#if peer.endpoint}
				<div class="flex items-center justify-between py-1">
					<span class="text-slate-400">Endpoint</span>
					<span class="text-slate-200 font-mono text-xs">{peer.endpoint}</span>
				</div>
			{/if}

			<div class="flex items-center justify-between py-1">
				<span class="text-slate-400 flex items-center gap-1.5">
					<Clock class="h-3.5 w-3.5" />
					Last handshake
				</span>
				<span class="{formatHandshake(peer.latest_handshake).color} font-medium transition-all duration-300" title={formatHandshake(peer.latest_handshake).tooltip}>
					{formatHandshake(peer.latest_handshake).text}
				</span>
			</div>
		</div>

		<!-- Bandwidth Stats Section -->
		<div class="pt-5 border-t border-slate-700/50 mb-5">
			<div class="grid grid-cols-2 gap-5">
				<div class="flex items-start gap-3">
					<div class="p-2 rounded-lg bg-emerald-500/10">
						<ArrowDownToLine class="h-4 w-4 text-emerald-500" />
					</div>
					<div>
						<p class="text-xs text-slate-500 mb-0.5">Download</p>
						<p class="text-base font-semibold text-slate-200 transition-all duration-300">{formatBytes(peer.transfer_rx)}</p>
					</div>
				</div>
				<div class="flex items-start gap-3">
					<div class="p-2 rounded-lg bg-blue-500/10">
						<ArrowUpFromLine class="h-4 w-4 text-blue-500" />
					</div>
					<div>
						<p class="text-xs text-slate-500 mb-0.5">Upload</p>
						<p class="text-base font-semibold text-slate-200 transition-all duration-300">{formatBytes(peer.transfer_tx)}</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Action Buttons -->
		<div class="pt-5 border-t border-slate-700/50 flex items-center gap-2">
			<Button variant="ghost" size="sm" onclick={() => onShowQR(peer)} title="Show QR Code">
				<QrCode class="h-4 w-4" />
			</Button>
			<Button variant="ghost" size="sm" loading={downloading} onclick={handleDownload} title="Download Config">
				<Download class="h-4 w-4" />
			</Button>
			<Button variant="ghost" size="sm" onclick={() => onEdit(peer)} title="Edit Peer">
				<Pencil class="h-4 w-4" />
			</Button>
			<Button variant="ghost" size="sm" onclick={openDeleteModal} class="ml-auto text-rose-400 hover:text-rose-300" title="Delete Peer">
				<Trash2 class="h-4 w-4" />
			</Button>
		</div>
	</div>
</div>

{#if showDeleteModal}
	<DeleteConfirmationModal
		title="Delete Peer"
		message="Are you sure you want to delete this peer? The peer will no longer be able to connect to the VPN."
		itemName={peer.name}
		loading={deleting}
		onConfirm={confirmDelete}
		onCancel={() => (showDeleteModal = false)}
	/>
{/if}

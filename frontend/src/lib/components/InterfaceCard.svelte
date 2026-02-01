<script lang="ts">
	import type { Interface } from '$lib/api';
	import { interfaces } from '$lib/stores/interfaces';
	import Toggle from './Toggle.svelte';
	import StatusBadge from './StatusBadge.svelte';
	import Button from './Button.svelte';
	import { Network, Users, ArrowDownToLine, ArrowUpFromLine, Eye } from 'lucide-svelte';

	interface Props {
		iface: Interface;
	}

	let { iface }: Props = $props();

	let toggling = $state(false);

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}

	async function handleToggle(checked: boolean) {
		toggling = true;
		try {
			await interfaces.toggle(iface.name, checked);
		} catch (error) {
			console.error('Failed to toggle interface:', error);
		} finally {
			toggling = false;
		}
	}

	function handleViewPeers(e: MouseEvent) {
		e.preventDefault();
		window.location.href = `/interfaces/${iface.name}`;
	}
</script>

<div
	class="bg-white dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700/50 hover:border-slate-300 dark:hover:border-slate-600 transition-all duration-200"
>
	<a href="/interfaces/{iface.name}" class="block p-5">
		<div class="flex items-start justify-between mb-4">
			<div class="flex items-center gap-3">
				<div
					class="p-2.5 rounded-lg {iface.is_active
						? 'bg-emerald-600/10 text-emerald-500'
						: 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400'}"
				>
					<Network class="h-5 w-5" />
				</div>
				<div>
					<h3 class="font-semibold text-slate-900 dark:text-white">{iface.name}</h3>
					<p class="text-sm text-slate-600 dark:text-slate-500">Port {iface.listen_port}</p>
				</div>
			</div>
			<div onclick={(e) => e.preventDefault()}>
				<Toggle checked={iface.is_active} loading={toggling} onchange={handleToggle} />
			</div>
		</div>

		<div class="space-y-3">
			<div class="flex items-center justify-between text-sm">
				<span class="text-slate-600 dark:text-slate-400">Status</span>
				<StatusBadge status={iface.is_active ? 'active' : 'inactive'} />
			</div>

			<div class="flex items-center justify-between text-sm">
				<span class="text-slate-600 dark:text-slate-400">Address</span>
				<span class="text-slate-800 dark:text-slate-200 font-mono text-xs">{iface.address}</span>
			</div>

			<div class="flex items-center justify-between text-sm">
				<span class="text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
					<Users class="h-4 w-4" />
					Peers
				</span>
				<div class="flex items-center gap-2">
					<span class="text-slate-800 dark:text-slate-200">{iface.peer_count}</span>
					{#if iface.peer_count > 0}
						<span class="text-xs px-2 py-0.5 rounded-full {iface.active_peer_count === iface.peer_count ? 'bg-emerald-500/10 text-emerald-500 ring-emerald-500/20' : 'bg-amber-500/10 text-amber-500 ring-amber-500/20'} ring-1 ring-inset">
							{iface.active_peer_count}/{iface.peer_count} online
						</span>
					{/if}
				</div>
			</div>
		</div>

		<div class="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700/50 grid grid-cols-2 gap-4">
			<div class="flex items-center gap-2">
				<ArrowDownToLine class="h-4 w-4 text-emerald-500" />
				<div>
					<p class="text-xs text-slate-600 dark:text-slate-500">Download</p>
					<p class="text-sm font-medium text-slate-800 dark:text-slate-200">{formatBytes(iface.total_transfer_rx)}</p>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<ArrowUpFromLine class="h-4 w-4 text-blue-500" />
				<div>
					<p class="text-xs text-slate-600 dark:text-slate-500">Upload</p>
					<p class="text-sm font-medium text-slate-800 dark:text-slate-200">{formatBytes(iface.total_transfer_tx)}</p>
				</div>
			</div>
		</div>
	</a>

	<!-- Quick Actions -->
	<div class="px-5 pb-5 pt-2 flex items-center gap-2 border-t border-slate-200 dark:border-slate-700/50">
		<Button variant="ghost" size="sm" onclick={handleViewPeers} class="w-full" title="View peers for this interface">
			<Eye class="h-4 w-4 mr-2" />
			View Peers
		</Button>
	</div>
</div>

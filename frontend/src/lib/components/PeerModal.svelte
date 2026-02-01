<script lang="ts">
	import { api, type Peer, type PeerCreate } from "$lib/api";
	import { peers } from "$lib/stores/interfaces";
	import Button from "./Button.svelte";
	import { X } from "lucide-svelte";

	interface Props {
		interfaceName: string;
		peer?: Peer | null;
		onClose: () => void;
		onSaved: (peer: Peer) => void;
	}

	let { interfaceName, peer = null, onClose, onSaved }: Props = $props();

	let name = $state(peer?.name || "");
	let allowedIps = $state(peer?.allowed_ips || "");
	let persistentKeepalive = $state(peer?.persistent_keepalive || 25);
	let loading = $state(false);
	let error = $state("");
	let loadingNextIp = $state(false);

	const isEditing = peer !== null;

	$effect(() => {
		if (!isEditing && !allowedIps) {
			loadNextIp();
		}
	});

	async function loadNextIp() {
		loadingNextIp = true;
		try {
			const result = await api.getNextAvailableIP(interfaceName);
			allowedIps = result.next_ip;
		} catch (e) {
			console.error("Failed to get next IP:", e);
		} finally {
			loadingNextIp = false;
		}
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = "";

		if (!name.trim()) {
			error = "Peer name is required";
			return;
		}

		if (!allowedIps.trim()) {
			error = "Allowed IPs is required";
			return;
		}

		loading = true;
		try {
			if (isEditing) {
				const updated = await api.updatePeer(
					interfaceName,
					peer!.public_key,
					{
						name: name.trim(),
						allowed_ips: allowedIps.trim(),
						persistent_keepalive: persistentKeepalive,
					},
				);
				peers.updatePeer(peer!.public_key, updated);
				onSaved(updated);
			} else {
				const created = await api.addPeer(interfaceName, {
					name: name.trim(),
					allowed_ips: allowedIps.trim(),
					persistent_keepalive: persistentKeepalive,
				});
				peers.addPeer(created);
				onSaved(created);
			}
			onClose();
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to save peer";
		} finally {
			loading = false;
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
	onclick={onClose}
	onkeydown={(e) => e.key === "Escape" && onClose()}
>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="w-[calc(100vw-2rem)] max-w-md bg-slate-800 rounded-xl border border-slate-700 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
	>
		<div
			class="flex items-center justify-between p-5 border-b border-slate-700"
		>
			<h2 class="text-lg font-semibold text-white">
				{isEditing ? "Edit Peer" : "Add New Peer"}
			</h2>
			<button
				type="button"
				class="p-1.5 rounded-lg text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
				onclick={onClose}
			>
				<X class="h-5 w-5" />
			</button>
		</div>

		<form onsubmit={handleSubmit} class="p-5 space-y-4">
			{#if error}
				<div
					class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm"
				>
					{error}
				</div>
			{/if}

			<div>
				<label
					for="name"
					class="block text-sm font-medium text-slate-300 mb-1.5"
				>
					Peer Name
				</label>
				<input
					type="text"
					id="name"
					bind:value={name}
					placeholder="e.g., John's Phone"
					class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
				/>
			</div>

			<div>
				<label
					for="allowed_ips"
					class="block text-sm font-medium text-slate-300 mb-1.5"
				>
					Allowed IPs
				</label>
				<div class="relative">
					<input
						type="text"
						id="allowed_ips"
						bind:value={allowedIps}
						placeholder="e.g., 10.0.0.2/32"
						disabled={loadingNextIp}
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono text-sm disabled:opacity-50"
					/>
					{#if loadingNextIp}
						<div class="absolute right-3 top-1/2 -translate-y-1/2">
							<div
								class="h-4 w-4 border-2 border-slate-500 border-t-emerald-500 rounded-full animate-spin"
							></div>
						</div>
					{/if}
				</div>
				<p class="mt-1 text-xs text-slate-500">
					IP address assigned to this peer within the VPN
				</p>
			</div>

			<div>
				<label
					for="keepalive"
					class="block text-sm font-medium text-slate-300 mb-1.5"
				>
					Persistent Keepalive (seconds)
				</label>
				<input
					type="number"
					id="keepalive"
					bind:value={persistentKeepalive}
					min="0"
					max="65535"
					class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
				/>
				<p class="mt-1 text-xs text-slate-500">
					Set to 0 to disable. Recommended: 25
				</p>
			</div>

			<div class="flex justify-end gap-3 pt-4">
				<Button variant="secondary" onclick={onClose}>Cancel</Button>
				<Button type="submit" {loading}>
					{isEditing ? "Save Changes" : "Add Peer"}
				</Button>
			</div>
		</form>
	</div>
</div>

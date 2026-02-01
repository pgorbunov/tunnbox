<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";
	import { api } from "$lib/api";
	import { interfaces } from "$lib/stores/interfaces";
	import Button from "$lib/components/Button.svelte";
	import InterfaceCreatedModal from "$lib/components/InterfaceCreatedModal.svelte";
	import { ArrowLeft } from "lucide-svelte";

	let name = $state("wg0");
	let listenPort = $state(51820);
	let address = $state("10.0.0.1/24");
	let dns = $state("1.1.1.1");
	let postUp = $state("");
	let postDown = $state("");
	let loading = $state(false);
	let error = $state("");

	let showSuccessModal = $state(false);
	let createdInterface = $state<{ name: string; listenPort: number } | null>(
		null,
	);
	let allInterfacePorts = $state<{ name: string; port: number }[]>([]);

	onMount(async () => {
		// Reset form to defaults first (prevents values from previous visits)
		name = "wg0";
		listenPort = 51820;
		address = "10.0.0.1/24";
		dns = "1.1.1.1";
		postUp = "";
		postDown = "";

		try {
			// Fetch global settings for defaults
			const settings = await api.getSettings();

			// Fetch existing interfaces
			const existingInterfaces = await api.getInterfaces();

			if (existingInterfaces.length > 0) {
				// Calculate next name (wg0 -> wg1)
				let maxNum = -1;
				const wgRegex = /^wg(\d+)$/;

				// Calculate next port
				let maxPort = 51819; // Start below default so next is 51820

				existingInterfaces.forEach((iface) => {
					// Check name
					const match = iface.name.match(wgRegex);
					if (match) {
						const num = parseInt(match[1]);
						if (num > maxNum) maxNum = num;
					}

					// Check port
					if (iface.listen_port > maxPort) {
						maxPort = iface.listen_port;
					}
				});

				// Set smart defaults
				const nextNum = maxNum + 1;
				name = `wg${nextNum}`;
				listenPort = maxPort + 1;

				// Smart subnet: 10.x.0.1/24 where x is the interface number
				// This avoids collisions like 10.0.0.1 vs 10.0.1.1 conflicts
				address = `10.${nextNum}.0.1/24`;
			}

			// Pre-fill DNS from global defaults
			if (settings.wg_default_dns) {
				dns = settings.wg_default_dns;
			}
		} catch (err) {
			console.error(
				"Failed to load settings and interfaces for smart defaults",
				err,
			);
		}
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = "";

		if (!name.trim()) {
			error = "Interface name is required";
			return;
		}

		if (!address.trim()) {
			error = "Address is required";
			return;
		}

		loading = true;
		try {
			// Fetch current interfaces before creating (to include in port list)
			const existingInterfaces = await api.getInterfaces();

			const created = await api.createInterface({
				name: name.trim(),
				listen_port: listenPort,
				address: address.trim(),
				dns: dns.trim() || undefined,
				post_up: postUp.trim() || undefined,
				post_down: postDown.trim() || undefined,
			});
			interfaces.addInterface(created);

			// Build list of all interface ports (existing + new)
			allInterfacePorts = [
				...existingInterfaces.map((iface) => ({
					name: iface.name,
					port: iface.listen_port,
				})),
				{ name: created.name, port: created.listen_port },
			];

			// Show success modal with Docker instructions
			createdInterface = {
				name: created.name,
				listenPort: created.listen_port,
			};
			showSuccessModal = true;
		} catch (e) {
			error =
				e instanceof Error ? e.message : "Failed to create interface";
		} finally {
			loading = false;
		}
	}

	function handleModalClose() {
		showSuccessModal = false;
		if (createdInterface) {
			goto(`/interfaces/${createdInterface.name}`);
		}
	}
</script>

<svelte:head>
	<title>New Interface - Tunnbox</title>
</svelte:head>

{#if createdInterface}
	<InterfaceCreatedModal
		bind:open={showSuccessModal}
		interfaceName={createdInterface.name}
		listenPort={createdInterface.listenPort}
		allInterfaces={allInterfacePorts}
		onClose={handleModalClose}
	/>
{/if}

<div class="max-w-2xl mx-auto">
	<div class="mb-8">
		<a
			href="/interfaces"
			class="inline-flex items-center text-slate-400 hover:text-slate-200 transition-colors mb-4"
		>
			<ArrowLeft class="h-4 w-4 mr-2" />
			Back to Interfaces
		</a>
		<h1 class="text-2xl font-bold text-white">Create Interface</h1>
		<p class="text-slate-400 mt-1">Set up a new WireGuard interface</p>
	</div>

	<div class="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
		<form onsubmit={handleSubmit} class="space-y-6">
			{#if error}
				<div
					class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm"
				>
					{error}
				</div>
			{/if}

			<div class="grid gap-6 sm:grid-cols-2">
				<div>
					<label
						for="name"
						class="block text-sm font-medium text-slate-300 mb-1.5"
					>
						Interface Name
					</label>
					<input
						type="text"
						id="name"
						bind:value={name}
						placeholder="e.g., wg0"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono"
					/>
					<p class="mt-1 text-xs text-slate-500">
						Alphanumeric, max 15 characters
					</p>
				</div>

				<div>
					<label
						for="port"
						class="block text-sm font-medium text-slate-300 mb-1.5"
					>
						Listen Port
					</label>
					<input
						type="number"
						id="port"
						bind:value={listenPort}
						min="1"
						max="65535"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
					/>
				</div>
			</div>

			<div class="grid gap-6 sm:grid-cols-2">
				<div>
					<label
						for="address"
						class="block text-sm font-medium text-slate-300 mb-1.5"
					>
						Address (CIDR)
					</label>
					<input
						type="text"
						id="address"
						bind:value={address}
						placeholder="e.g., 10.0.0.1/24"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono"
					/>
					<p class="mt-1 text-xs text-slate-500">
						VPN subnet address for this server
					</p>
				</div>

				<div>
					<label
						for="dns"
						class="block text-sm font-medium text-slate-300 mb-1.5"
					>
						DNS Server (optional)
					</label>
					<input
						type="text"
						id="dns"
						bind:value={dns}
						placeholder="e.g., 1.1.1.1"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono"
					/>
					<p class="mt-1 text-xs text-slate-500">
						DNS server for clients
					</p>
				</div>
			</div>

			<div>
				<label
					for="postUp"
					class="block text-sm font-medium text-slate-300 mb-1.5"
				>
					PostUp Script (optional)
				</label>
				<textarea
					id="postUp"
					bind:value={postUp}
					placeholder="e.g., iptables -A FORWARD -i %i -j ACCEPT"
					rows="2"
					class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono text-sm"
				></textarea>
			</div>

			<div>
				<label
					for="postDown"
					class="block text-sm font-medium text-slate-300 mb-1.5"
				>
					PostDown Script (optional)
				</label>
				<textarea
					id="postDown"
					bind:value={postDown}
					placeholder="e.g., iptables -D FORWARD -i %i -j ACCEPT"
					rows="2"
					class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono text-sm"
				></textarea>
			</div>

			<div class="flex justify-end gap-3 pt-4 border-t border-slate-700">
				<Button variant="secondary" onclick={() => goto("/interfaces")}
					>Cancel</Button
				>
				<Button type="submit" {loading}>Create Interface</Button>
			</div>
		</form>
	</div>
</div>

<script lang="ts">
	import Modal from './Modal.svelte';
	import Button from './Button.svelte';
	import { CheckCircle, Copy, Check, Info, AlertTriangle } from 'lucide-svelte';

	interface InterfacePort {
		name: string;
		port: number;
	}

	interface Props {
		open: boolean;
		interfaceName: string;
		listenPort: number;
		allInterfaces: InterfacePort[];
		onClose: () => void;
	}

	let { open = $bindable(), interfaceName, listenPort, allInterfaces, onClose }: Props = $props();

	let copied = $state(false);

	function getDockerSnippet(interfaces: InterfacePort[]): string {
		const lines = ['ports:', '  - "8000:8000"      # Web UI'];
		for (const iface of interfaces) {
			lines.push(`  - "${iface.port}:${iface.port}/udp"  # ${iface.name} WireGuard`);
		}
		return lines.join('\n');
	}

	async function copyToClipboard() {
		try {
			await navigator.clipboard.writeText(getDockerSnippet(allInterfaces));
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 2000);
		} catch (err) {
			console.error('Failed to copy:', err);
		}
	}
</script>

<Modal {open} onClose={onClose} title="Interface Created Successfully!">
	<div class="space-y-4">
		<!-- Success Message -->
		<div class="flex items-start gap-3 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
			<CheckCircle class="h-5 w-5 text-emerald-500 mt-0.5 flex-shrink-0" />
			<div>
				<p class="font-medium text-emerald-400">Interface "{interfaceName}" created</p>
				<p class="text-sm text-emerald-300/80 mt-1">
					Listen port: {listenPort}
				</p>
			</div>
		</div>

		<!-- Warning for multiple interfaces -->
		{#if allInterfaces.length > 1}
			<div class="flex items-start gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
				<AlertTriangle class="h-5 w-5 text-amber-400 mt-0.5 flex-shrink-0" />
				<p class="text-sm text-amber-300/90">
					You have {allInterfaces.length} interfaces. The snippet below includes <strong>all</strong> ports — replace your entire <code class="px-1 py-0.5 rounded bg-slate-800 text-amber-300 font-mono text-xs">ports:</code> section.
				</p>
			</div>
		{/if}

		<!-- Docker Setup Instructions -->
		<div class="flex items-start gap-3 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
			<Info class="h-5 w-5 text-blue-400 mt-0.5 flex-shrink-0" />
			<div class="flex-1">
				<p class="font-medium text-blue-400 mb-2">Docker Setup Required</p>
				<p class="text-sm text-blue-300/80 mb-3">
					{#if allInterfaces.length > 1}
						Replace the <code class="px-1.5 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-xs">ports:</code> section in your <code class="px-1.5 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-xs">docker-compose.yml</code>:
					{:else}
						Add this to your <code class="px-1.5 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-xs">docker-compose.yml</code>:
					{/if}
				</p>

				<!-- Code Snippet -->
				<div class="relative">
					<pre class="p-3 rounded-lg bg-slate-900 border border-slate-700 text-sm font-mono text-slate-200 overflow-x-auto">{getDockerSnippet(allInterfaces)}</pre>
					
					<!-- Copy Button -->
					<button
						type="button"
						onclick={copyToClipboard}
						class="absolute top-2 right-2 p-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-300 hover:text-white transition-colors"
						title="Copy to clipboard"
					>
						{#if copied}
							<Check class="h-4 w-4 text-emerald-400" />
						{:else}
							<Copy class="h-4 w-4" />
						{/if}
					</button>
				</div>

				<!-- Restart Instructions -->
				<div class="mt-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
					<p class="text-xs text-slate-400 mb-1.5 font-medium">Then restart the container:</p>
					<code class="text-xs font-mono text-slate-300">docker compose up -d</code>
				</div>
			</div>
		</div>

		<!-- Action Buttons -->
		<div class="flex justify-end gap-3 pt-2">
			<Button variant="secondary" onclick={onClose}>
				I'll do this later
			</Button>
			<Button onclick={onClose}>
				Got it!
			</Button>
		</div>
	</div>
</Modal>

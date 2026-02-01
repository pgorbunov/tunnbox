<script lang="ts">
	import { api, type Peer } from '$lib/api';
	import Button from './Button.svelte';
	import { X, Download, Copy, Check } from 'lucide-svelte';

	interface Props {
		peer: Peer;
		interfaceName: string;
		onClose: () => void;
	}

	let { peer, interfaceName, onClose }: Props = $props();

	let copied = $state(false);
	let downloading = $state(false);
	let config = $state('');
	let loadingConfig = $state(true);
	let qrBlobUrl = $state('');
	let loadingQR = $state(true);

	$effect(() => {
		loadConfig();
		loadQRBlob();

		return () => {
			if (qrBlobUrl) {
				URL.revokeObjectURL(qrBlobUrl);
			}
		};
	});

	async function loadConfig() {
		try {
			config = await api.getPeerConfig(interfaceName, peer.public_key);
		} catch (e) {
			console.error('Failed to load config:', e);
		} finally {
			loadingConfig = false;
		}
	}

	async function loadQRBlob() {
		try {
			qrBlobUrl = await api.getPeerQRBlob(interfaceName, peer.public_key);
		} catch (e) {
			console.error('Failed to load QR code:', e);
		} finally {
			loadingQR = false;
		}
	}

	async function handleCopy() {
		try {
			await navigator.clipboard.writeText(config);
			copied = true;
			setTimeout(() => (copied = false), 2000);
		} catch (e) {
			console.error('Failed to copy:', e);
		}
	}

	async function handleDownload() {
		downloading = true;
		try {
			const blob = new Blob([config], { type: 'text/plain' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${peer.name}.conf`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} finally {
			downloading = false;
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="w-full max-w-sm bg-slate-800 rounded-xl border border-slate-700 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
	>
		<div class="flex items-center justify-between p-5 border-b border-slate-700">
			<div>
				<h2 class="text-lg font-semibold text-white">{peer.name}</h2>
				<p class="text-sm text-slate-400">Scan with WireGuard app</p>
			</div>
			<button
				type="button"
				class="p-1.5 rounded-lg text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
				onclick={(e) => {
					e.stopPropagation();
					onClose();
				}}
			>
				<X class="h-5 w-5" />
			</button>
		</div>

		<div class="p-5">
			<div class="bg-white p-4 rounded-xl mx-auto w-fit">
				{#if loadingQR}
					<div class="w-64 h-64 flex items-center justify-center text-slate-400">
						Loading QR code...
					</div>
				{:else if qrBlobUrl}
					<img src={qrBlobUrl} alt="QR Code for {peer.name}" class="w-64 h-64" />
				{:else}
					<div class="w-64 h-64 flex items-center justify-center text-red-400">
						Failed to load QR code
					</div>
				{/if}
			</div>

			<div class="mt-5 flex justify-center gap-3">
				<Button variant="secondary" onclick={handleCopy}>
					{#if copied}
						<Check class="h-4 w-4 mr-2" />
						Copied!
					{:else}
						<Copy class="h-4 w-4 mr-2" />
						Copy Config
					{/if}
				</Button>
				<Button loading={downloading} onclick={handleDownload}>
					<Download class="h-4 w-4 mr-2" />
					Download
				</Button>
			</div>
		</div>

		{#if !loadingConfig && config}
			<div class="px-5 pb-5">
				<details class="group">
					<summary
						class="cursor-pointer text-sm text-slate-400 hover:text-slate-300 transition-colors"
					>
						Show configuration
					</summary>
					<pre
						class="mt-3 p-3 bg-slate-900 rounded-lg text-xs text-slate-300 font-mono overflow-x-auto">{config}</pre>
				</details>
			</div>
		{/if}
	</div>
</div>

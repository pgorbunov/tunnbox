<script lang="ts">
	/**
	 * Public share page (no app shell): fetches the one-time payload exactly once,
	 * then offers QR, download and copy. Friendly states for invalid/expired/exhausted links.
	 */
	import { page } from '$app/state';
	import { Clock, Download, Link2Off, ShieldAlert } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { SharePayload } from '$lib/api/types';
	import { themeStore } from '$lib/stores/theme.svelte';
	import { formatDateTime, formatRelative } from '$lib/utils/format';
	import { createTicker } from '$lib/utils/poll.svelte';
	import Logo from '$lib/components/app/Logo.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CodeBlock from '$lib/components/ui/CodeBlock.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';

	themeStore.init();

	const token = $derived(page.params.token ?? '');
	const ticker = createTicker(30_000);

	let data = $state<SharePayload | null>(null);
	let loading = $state(true);
	let error = $state<{ kind: 'expired' | 'invalid' | 'ratelimit' | 'other'; message: string } | null>(null);
	let showConfig = $state(false);

	$effect(() => {
		const t = token;
		loading = true;
		error = null;
		const controller = new AbortController();
		void api.share
			.get(t, controller.signal)
			.then((d) => (data = d))
			.catch((err) => {
				const e = toApiError(err);
				if (e.status === 410)
					error = { kind: 'expired', message: 'This link has expired or has already been used.' };
				else if (e.status === 404)
					error = {
						kind: 'invalid',
						message: 'This link is not valid. Check that you copied the whole URL.'
					};
				else if (e.status === 429)
					error = { kind: 'ratelimit', message: 'Too many requests. Please wait a minute and reload.' };
				else error = { kind: 'other', message: e.detail };
			})
			.finally(() => (loading = false));
		return () => controller.abort();
	});

	const qrSrc = $derived(data ? `data:image/png;base64,${data.qr_png_base64}` : '');
	const fileName = $derived(
		data ? `${data.peer_name.replace(/[^a-zA-Z0-9_.-]+/g, '-')}.conf` : 'wireguard.conf'
	);

	function download() {
		if (!data) return;
		const blob = new Blob([data.config], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = fileName;
		a.style.display = 'none';
		document.body.appendChild(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}
</script>

<svelte:head>
	<title>{data ? `${data.peer_name} · WireGuard config` : 'Shared configuration'} · TunnBox</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<main class="flex min-h-dvh items-center justify-center bg-bg px-4 py-10">
	<div class="w-full max-w-md">
		<div class="mb-8 flex justify-center">
			<Logo size={40} />
		</div>

		<div class="rounded-lg border border-border bg-surface p-6 shadow-md sm:p-8">
			{#if loading}
				<div class="flex flex-col items-center gap-4" aria-busy="true">
					<Skeleton class="h-5 w-40" />
					<Skeleton class="h-56 w-56" rounded="md" />
					<Skeleton class="h-10 w-full" rounded="md" />
				</div>
			{:else if error}
				<div class="flex flex-col items-center text-center">
					<div
						class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-danger-soft text-danger"
						aria-hidden="true"
					>
						{#if error.kind === 'expired'}<Clock
								class="h-6 w-6"
							/>{:else if error.kind === 'ratelimit'}<ShieldAlert class="h-6 w-6" />{:else}<Link2Off
								class="h-6 w-6"
							/>{/if}
					</div>
					<h1 class="text-lg font-semibold text-fg" tabindex="-1">
						{error.kind === 'expired'
							? 'Link no longer available'
							: error.kind === 'invalid'
								? 'Invalid link'
								: 'Something went wrong'}
					</h1>
					<p class="mt-2 text-sm text-fg-muted">{error.message}</p>
					{#if error.kind === 'expired' || error.kind === 'invalid'}
						<p class="mt-3 text-[13px] text-fg-subtle">
							Share links are single-use and short-lived by design. Ask whoever sent it to create a new one.
						</p>
					{/if}
				</div>
			{:else if data}
				<h1 class="text-lg font-semibold text-fg" tabindex="-1">Your WireGuard configuration</h1>
				<p class="mt-1 text-sm text-fg-muted">
					<span class="font-medium text-fg">{data.peer_name}</span> on
					<span class="font-mono">{data.interface_name}</span>
				</p>

				<Alert tone="warning" class="mt-4">
					{#if data.remaining_uses <= 0}
						This was a one-time link — it will not open again. Save the configuration now.
					{:else}
						{data.remaining_uses}
						{data.remaining_uses === 1 ? 'use' : 'uses'} left · expires {formatRelative(
							data.expires_at,
							ticker.now
						)} ({formatDateTime(data.expires_at)}).
					{/if}
				</Alert>

				<div class="mt-5 flex flex-col items-center gap-3">
					<div class="rounded-lg border border-border bg-white p-3">
						<img
							src={qrSrc}
							alt="QR code containing the WireGuard configuration"
							width="224"
							height="224"
							class="block h-56 w-56"
						/>
					</div>
					<p class="text-center text-[13px] text-fg-muted">
						In the WireGuard app choose <strong>Add tunnel → Scan QR code</strong>, or import the file below
						on desktop.
					</p>
				</div>

				<div class="mt-5 flex flex-col gap-2">
					<Button variant="primary" size="lg" block onclick={download}>
						<Download class="h-4 w-4" aria-hidden="true" />
						Download {fileName}
					</Button>
					<div class="grid grid-cols-2 gap-2">
						<CopyButton text={data.config} label="Copy config" variant="button" />
						<Button variant="secondary" onclick={() => (showConfig = !showConfig)} aria-expanded={showConfig}>
							{showConfig ? 'Hide config' : 'Show config'}
						</Button>
					</div>
				</div>

				{#if showConfig}
					<div class="mt-4">
						<CodeBlock code={data.config} label="WireGuard configuration" maxHeight="16rem" />
						<p class="mt-2 text-[12px] text-fg-subtle">
							This file contains a private key. Do not forward it.
						</p>
					</div>
				{/if}
			{/if}
		</div>
		<p class="mt-6 text-center text-xs text-fg-subtle">Delivered securely by TunnBox</p>
	</div>
</main>

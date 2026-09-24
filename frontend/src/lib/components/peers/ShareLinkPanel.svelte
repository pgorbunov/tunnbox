<script lang="ts">
	/** Create a one-time share link for a peer and show it with a copy button. */
	import { Link2 } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { Peer, ShareCreated } from '$lib/api/types';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatDateTime } from '$lib/utils/format';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import Select from '$lib/components/ui/Select.svelte';

	let { peer }: { peer: Peer } = $props();

	let expires = $state('24');
	let maxUses = $state('1');
	let creating = $state(false);
	let link = $state<ShareCreated | null>(null);
	let error = $state<string | null>(null);

	const url = $derived(link ? `${window.location.origin}${link.url_path}` : '');

	async function create() {
		creating = true;
		error = null;
		try {
			link = await api.peers.share(peer.id, { expires_in_hours: Number(expires), max_uses: Number(maxUses) });
			toast.success('Share link created');
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			creating = false;
		}
	}
</script>

<div class="flex flex-col gap-4">
	<p class="text-sm text-fg-muted">
		A share link lets someone fetch this peer's configuration once, without signing in. Anyone with the link can use it until it
		expires or its uses run out.
	</p>
	{#if error}
		<Alert tone="danger">{error}</Alert>
	{/if}
	{#if link}
		<div class="rounded-md border border-border bg-bg-subtle p-3">
			<p class="mb-1.5 text-xs font-medium uppercase tracking-wide text-fg-subtle">Share link</p>
			<div class="flex items-center gap-2">
				<code class="min-w-0 flex-1 truncate font-mono text-[13px] text-fg">{url}</code>
				<CopyButton text={url} label="Copy link" />
			</div>
			<p class="mt-2 text-[13px] text-fg-subtle">
				Expires {formatDateTime(link.expires_at)} · {link.max_uses === 1 ? 'one-time use' : `${link.max_uses} uses`}
			</p>
		</div>
		<div class="flex gap-2">
			<CopyButton text={url} label="Copy link" variant="button" buttonVariant="primary" />
			<Button variant="ghost" onclick={() => (link = null)}>Create another</Button>
		</div>
	{:else}
		<div class="grid gap-3 sm:grid-cols-2">
			<Select
				label="Expires in"
				bind:value={expires}
				options={[
					{ value: '1', label: '1 hour' },
					{ value: '6', label: '6 hours' },
					{ value: '24', label: '24 hours' },
					{ value: '72', label: '3 days' },
					{ value: '168', label: '7 days' }
				]}
			/>
			<Select
				label="Maximum uses"
				bind:value={maxUses}
				options={[
					{ value: '1', label: '1 (one-time)' },
					{ value: '3', label: '3' },
					{ value: '5', label: '5' },
					{ value: '10', label: '10' }
				]}
			/>
		</div>
		<div>
			<Button variant="primary" onclick={create} loading={creating}>
				<Link2 class="h-4 w-4" aria-hidden="true" />
				Create share link
			</Button>
		</div>
	{/if}
</div>

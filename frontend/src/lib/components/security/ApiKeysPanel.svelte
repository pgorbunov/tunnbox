<script lang="ts">
	/** API keys: list, create dialog (name, scopes, expiry), show-once key, revoke. */
	import { KeyRound, Plus } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { ApiKey, ApiKeyScope } from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatDateTime, formatRelative } from '$lib/utils/format';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import CodeBlock from '$lib/components/ui/CodeBlock.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import DateTimePicker from '$lib/components/ui/DateTimePicker.svelte';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';

	const SCOPES: { value: ApiKeyScope; label: string; description: string; minRole: 'viewer' | 'operator' | 'admin' }[] = [
		{ value: 'read', label: 'read', description: 'Read interfaces, peers, stats and audit', minRole: 'viewer' },
		{ value: 'peers:write', label: 'peers:write', description: 'Create, edit, enable/disable and delete peers', minRole: 'operator' },
		{ value: 'interfaces:write', label: 'interfaces:write', description: 'Manage interfaces', minRole: 'operator' },
		{ value: 'admin', label: 'admin', description: 'Everything, including users and settings', minRole: 'admin' }
	];

	let keys = $state<ApiKey[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showAll = $state(false);

	let createOpen = $state(false);
	let name = $state('');
	let scopes = $state<Set<ApiKeyScope>>(new Set(['read']));
	let expires = $state('');
	let creating = $state(false);
	let createError = $state<string | null>(null);
	let createdKey = $state<string | null>(null);

	let revokeTarget = $state<ApiKey | null>(null);
	let revokeOpen = $state(false);
	let revoking = $state(false);

	const isAdmin = $derived(auth.can('admin'));

	async function load() {
		loading = true;
		error = null;
		try {
			keys = await api.apiKeys.list(showAll && isAdmin);
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		void showAll;
		void load();
	});

	function openCreate() {
		name = '';
		scopes = new Set(['read']);
		expires = '';
		createError = null;
		createdKey = null;
		createOpen = true;
	}

	function toggleScope(s: ApiKeyScope, on: boolean) {
		const next = new Set(scopes);
		if (on) next.add(s);
		else next.delete(s);
		scopes = next;
	}

	async function create() {
		if (!name.trim() || scopes.size === 0 || creating) return;
		creating = true;
		createError = null;
		try {
			const res = await api.apiKeys.create({ name: name.trim(), scopes: [...scopes], expires_at: expires || null });
			createdKey = res.key;
			keys = [res, ...keys];
			toast.success(`API key "${res.name}" created`);
		} catch (err) {
			createError = toApiError(err).detail;
		} finally {
			creating = false;
		}
	}

	async function revoke() {
		if (!revokeTarget) return;
		revoking = true;
		try {
			await api.apiKeys.revoke(revokeTarget.id);
			keys = keys.map((k) => (k.id === revokeTarget!.id ? { ...k, revoked_at: new Date().toISOString() } : k));
			revokeOpen = false;
			toast.success('API key revoked');
		} catch (err) {
			toast.error('Could not revoke key', { description: toApiError(err).detail });
		} finally {
			revoking = false;
		}
	}

	function status(k: ApiKey): { tone: 'neutral' | 'success' | 'danger' | 'warning'; label: string } {
		if (k.revoked_at) return { tone: 'danger', label: 'Revoked' };
		if (k.expires_at && new Date(k.expires_at).getTime() < Date.now()) return { tone: 'warning', label: 'Expired' };
		return { tone: 'success', label: 'Active' };
	}
</script>

<Card title="API keys" description="Use keys for automation: send them as a Bearer token or in the X-API-Key header." flush>
	{#snippet actions()}
		{#if isAdmin}
			<Switch bind:checked={showAll} label="All users" size="sm" />
		{/if}
		<Button size="sm" variant="primary" onclick={openCreate}>
			<Plus class="h-4 w-4" aria-hidden="true" />
			New key
		</Button>
	{/snippet}

	{#if loading}
		<div class="divide-y divide-border">
			{#each [1, 2] as i (i)}
				<div class="px-5 py-4"><Skeleton class="h-4 w-40" /><Skeleton class="mt-2 h-3 w-64" /></div>
			{/each}
		</div>
	{:else if error}
		<ErrorState compact message={error} onretry={load} />
	{:else if keys.length === 0}
		<EmptyState compact title="No API keys yet" description="Create a key to manage TunnBox from scripts or other tools.">
			{#snippet icon()}<KeyRound class="h-6 w-6" />{/snippet}
			{#snippet actions()}
				<Button variant="primary" onclick={openCreate}><Plus class="h-4 w-4" aria-hidden="true" />New key</Button>
			{/snippet}
		</EmptyState>
	{:else}
		<ul class="divide-y divide-border">
			{#each keys as k (k.id)}
				{@const s = status(k)}
				<li class="flex flex-wrap items-center gap-3 px-5 py-4">
					<div class="min-w-0 flex-1 text-sm">
						<p class="flex flex-wrap items-center gap-2">
							<span class="font-medium text-fg">{k.name}</span>
							<code class="font-mono text-[12px] text-fg-subtle">{k.prefix}…</code>
							<Badge tone={s.tone} size="sm">{s.label}</Badge>
						</p>
						<p class="mt-1 flex flex-wrap gap-1">
							{#each k.scopes as sc (sc)}
								<Badge tone="neutral" size="sm"><span class="font-mono">{sc}</span></Badge>
							{/each}
						</p>
						<p class="mt-1 text-[13px] text-fg-subtle">
							Created {formatDateTime(k.created_at)} · Last used {k.last_used_at ? formatRelative(k.last_used_at) : 'never'}
							{#if k.expires_at}
								· Expires {formatDateTime(k.expires_at)}
							{/if}
						</p>
					</div>
					{#if !k.revoked_at}
						<Button
							size="sm"
							variant="ghost"
							onclick={() => {
								revokeTarget = k;
								revokeOpen = true;
							}}
						>
							Revoke
						</Button>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</Card>

<Dialog bind:open={createOpen} title={createdKey ? 'Copy your new API key' : 'New API key'} size="md" locked={creating}>
	{#if createdKey}
		<div class="flex flex-col gap-4">
			<Alert tone="warning" title="Shown only once">Copy the key now — you will not be able to see it again.</Alert>
			<CodeBlock code={createdKey} label="API key" />
			<p class="text-[13px] text-fg-muted">
				Example: <code class="font-mono">curl -H "Authorization: Bearer {createdKey.slice(0, 8)}…" {window.location.origin}/api/interfaces</code>
			</p>
		</div>
	{:else}
		<form
			id="apikey-form"
			class="flex flex-col gap-5"
			onsubmit={(e) => {
				e.preventDefault();
				void create();
			}}
		>
			{#if createError}
				<Alert tone="danger">{createError}</Alert>
			{/if}
			<Input label="Name" bind:value={name} required placeholder="e.g. backup-script" autocomplete="off" />
			<fieldset class="flex flex-col gap-3">
				<legend class="mb-1 text-sm font-medium text-fg">Scopes</legend>
				{#each SCOPES as sc (sc.value)}
					<Checkbox
						label={sc.label}
						description={sc.description}
						checked={scopes.has(sc.value)}
						disabled={!auth.can(sc.minRole)}
						onchange={(on) => toggleScope(sc.value, on)}
					/>
				{/each}
				<p class="text-[13px] text-fg-subtle">A key can never exceed your own role.</p>
			</fieldset>
			<DateTimePicker label="Expires (optional)" bind:value={expires} min={new Date().toISOString()} hint="Leave empty for a key that does not expire." />
		</form>
	{/if}
	{#snippet footer()}
		{#if createdKey}
			<Button variant="primary" onclick={() => (createOpen = false)}>Done</Button>
		{:else}
			<Button variant="ghost" onclick={() => (createOpen = false)} disabled={creating}>Cancel</Button>
			<Button variant="primary" type="submit" form="apikey-form" loading={creating} disabled={!name.trim() || scopes.size === 0}>Create key</Button>
		{/if}
	{/snippet}
</Dialog>

<ConfirmDialog
	bind:open={revokeOpen}
	title={`Revoke "${revokeTarget?.name ?? ''}"?`}
	message="Requests using this key will be rejected immediately. This cannot be undone."
	confirmLabel="Revoke key"
	loading={revoking}
	onconfirm={revoke}
/>

<script lang="ts">
	/** Edit an existing interface's settings inline (Settings tab on the interface page). */
	import { api, toApiError } from '$lib/api';
	import type { Interface, InterfaceUpdateRequest } from '$lib/api/types';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatDateTime, joinList, splitList } from '$lib/utils/format';
	import { validateDnsList, validateEndpoint, validateInterfaceAddress, validateMtu, validatePort } from '$lib/utils/validation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';

	interface Props {
		iface: Interface;
		canWrite: boolean;
		onsaved: (iface: Interface) => void;
	}

	let { iface, canWrite, onsaved }: Props = $props();

	let address = $state('');
	let port = $state('');
	let dns = $state('');
	let endpoint = $state('');
	let mtu = $state('');
	let postUp = $state('');
	let postDown = $state('');
	let saving = $state(false);
	let formError = $state<string | null>(null);
	let touched = $state<Record<string, boolean>>({});

	const scriptsAllowed = $derived(settingsStore.server?.custom_scripts_allowed ?? false);

	function load(i: Interface) {
		address = i.address;
		port = String(i.listen_port);
		dns = i.dns ?? '';
		endpoint = i.public_endpoint ?? '';
		mtu = i.mtu === null ? '' : String(i.mtu);
		postUp = i.post_up ?? '';
		postDown = i.post_down ?? '';
		touched = {};
		formError = null;
	}
	$effect(() => {
		load(iface);
	});

	const errors = $derived({
		address: validateInterfaceAddress(address),
		port: validatePort(port),
		dns: validateDnsList(dns),
		endpoint: validateEndpoint(endpoint, { allowEmpty: true }),
		mtu: validateMtu(mtu)
	});
	const valid = $derived(Object.values(errors).every((e) => e === null));

	const body = $derived<InterfaceUpdateRequest>({
		address: joinList(splitList(address)),
		listen_port: Number(port),
		dns: dns.trim() ? joinList(splitList(dns)) : null,
		public_endpoint: endpoint.trim() || null,
		mtu: mtu.trim() ? Number(mtu) : null,
		...(scriptsAllowed ? { post_up: postUp.trim() || null, post_down: postDown.trim() || null } : {})
	});

	const dirty = $derived(
		body.address !== iface.address ||
			body.listen_port !== iface.listen_port ||
			body.dns !== iface.dns ||
			body.public_endpoint !== iface.public_endpoint ||
			body.mtu !== iface.mtu ||
			(scriptsAllowed && (body.post_up !== iface.post_up || body.post_down !== iface.post_down))
	);
	const willRestart = $derived(
		iface.is_active &&
			(body.address !== iface.address ||
				body.listen_port !== iface.listen_port ||
				body.mtu !== iface.mtu ||
				(scriptsAllowed && (body.post_up !== iface.post_up || body.post_down !== iface.post_down)))
	);

	function show(key: keyof typeof errors) {
		return touched[key] ? errors[key] : null;
	}
	function touch(key: string) {
		touched = { ...touched, [key]: true };
	}

	async function save() {
		touched = { address: true, port: true, dns: true, endpoint: true, mtu: true };
		if (!valid || saving || !dirty) return;
		saving = true;
		formError = null;
		try {
			const updated = await api.interfaces.update(iface.name, body);
			toast.success(`${updated.name} updated${willRestart ? ' and restarted' : ''}`);
			onsaved(updated);
		} catch (err) {
			formError = toApiError(err).detail;
		} finally {
			saving = false;
		}
	}
</script>

<div class="grid gap-6 lg:grid-cols-[1fr_320px]">
	<Card title="Interface settings" description={canWrite ? 'Changes to address, port, MTU or scripts restart the interface if it is running.' : 'Read-only'}>
		<form
			class="flex flex-col gap-5"
			onsubmit={(e) => {
				e.preventDefault();
				void save();
			}}
		>
			{#if formError}
				<Alert tone="danger">{formError}</Alert>
			{/if}
			<div class="grid gap-4 sm:grid-cols-[1fr_160px]">
				<Input label="Address" bind:value={address} mono required disabled={!canWrite} error={show('address')} onblur={() => touch('address')} />
				<Input label="Listen port" bind:value={port} type="number" inputmode="numeric" min="1" max="65535" required disabled={!canWrite} error={show('port')} onblur={() => touch('port')} />
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<Input label="DNS for clients" bind:value={dns} mono placeholder={settingsStore.server?.default_dns ?? ''} hint="Empty = global default." disabled={!canWrite} error={show('dns')} onblur={() => touch('dns')} />
				<Input label="Public endpoint override" bind:value={endpoint} mono placeholder={settingsStore.server?.public_endpoint || 'Global default'} hint="Host or IP without port." disabled={!canWrite} error={show('endpoint')} onblur={() => touch('endpoint')} />
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<Input label="MTU" bind:value={mtu} type="number" inputmode="numeric" min="1280" max="1500" placeholder="Default" disabled={!canWrite} error={show('mtu')} onblur={() => touch('mtu')} />
			</div>
			{#if scriptsAllowed}
				<Textarea label="PostUp" bind:value={postUp} mono rows={2} disabled={!canWrite} />
				<Textarea label="PostDown" bind:value={postDown} mono rows={2} disabled={!canWrite} />
			{:else if iface.post_up || iface.post_down}
				<Alert tone="warning" title="Custom scripts are locked">
					This interface has PostUp/PostDown scripts but WG_ALLOW_CUSTOM_SCRIPTS is off, so they cannot be edited here.
				</Alert>
			{/if}
			{#if canWrite}
				<div class="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4">
					{#if willRestart && dirty}
						<p class="mr-auto text-[13px] text-warning">Saving restarts {iface.name}; connected peers reconnect automatically.</p>
					{/if}
					<Button variant="ghost" onclick={() => load(iface)} disabled={!dirty || saving}>Reset</Button>
					<Button variant="primary" type="submit" loading={saving} disabled={!dirty}>Save changes</Button>
				</div>
			{/if}
		</form>
	</Card>

	<div class="flex flex-col gap-4">
		<Card title="Identity">
			<dl class="flex flex-col gap-3 text-sm">
				<div>
					<dt class="text-fg-subtle">Public key</dt>
					<dd class="mt-0.5 flex items-center gap-1">
						<code class="min-w-0 flex-1 break-all font-mono text-[12px] text-fg">{iface.public_key}</code>
						<CopyButton text={iface.public_key} label="Copy public key" />
					</dd>
				</div>
				<div>
					<dt class="text-fg-subtle">Created</dt>
					<dd class="text-fg">{formatDateTime(iface.created_at)}</dd>
				</div>
				<div>
					<dt class="text-fg-subtle">Last updated</dt>
					<dd class="text-fg">{formatDateTime(iface.updated_at)}</dd>
				</div>
			</dl>
		</Card>
	</div>
</div>

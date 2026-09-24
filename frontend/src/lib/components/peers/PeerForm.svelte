<script lang="ts">
	/** Create / edit peer dialog with inline validation and split-tunnel presets. */
	import { api, ApiError, toApiError } from '$lib/api';
	import type { Interface, Peer, PeerCreateRequest, PeerUpdateRequest } from '$lib/api/types';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { FULL_TUNNEL, LAN_RANGES, interfaceSubnets, isFullTunnel, joinList, splitList } from '$lib/utils/format';
	import {
		validateCidrList,
		validateDnsList,
		validateKeepalive,
		validatePeerName
	} from '$lib/utils/validation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import DateTimePicker from '$lib/components/ui/DateTimePicker.svelte';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';

	interface Props {
		open: boolean;
		iface: Interface;
		/** When set, the form edits this peer; otherwise it creates one. */
		peer?: Peer | null;
		onsaved: (peer: Peer, created: boolean) => void;
	}

	let { open = $bindable(false), iface, peer = null, onsaved }: Props = $props();

	type AddressMode = 'auto' | 'manual';
	type TunnelMode = 'full' | 'split';
	type SplitPreset = 'lan' | 'subnet' | 'custom';
	type ExpiryMode = 'none' | '1d' | '7d' | '30d' | 'custom';

	const editing = $derived(peer !== null);
	const subnets = $derived(interfaceSubnets(iface.address));
	const lanPreset = $derived(joinList([...LAN_RANGES, ...subnets.filter((s) => !LAN_RANGES.includes(s))]));
	const subnetPreset = $derived(joinList(subnets));

	let name = $state('');
	let addressMode = $state<AddressMode>('auto');
	let allowedIps = $state('');
	let nextIp = $state<string | null>(null);
	let tunnel = $state<TunnelMode>('full');
	let preset = $state<SplitPreset>('lan');
	let customRoutes = $state('');
	let dns = $state('');
	let keepalive = $state('25');
	let expiryMode = $state<ExpiryMode>('none');
	let expiresAt = $state('');
	let notes = $state('');
	let enabled = $state(true);

	let submitting = $state(false);
	let formError = $state<string | null>(null);
	let touched = $state<Record<string, boolean>>({});

	function sameList(a: string, b: string) {
		const x = [...splitList(a)].sort();
		const y = [...splitList(b)].sort();
		return x.length === y.length && x.every((v, i) => v === y[i]);
	}

	function reset() {
		const s = settingsStore.server;
		touched = {};
		formError = null;
		nextIp = null;
		if (peer) {
			name = peer.name;
			addressMode = 'manual';
			allowedIps = peer.allowed_ips;
			const cai = peer.client_allowed_ips;
			if (isFullTunnel(cai)) {
				tunnel = 'full';
				preset = 'lan';
				customRoutes = lanPreset;
			} else {
				tunnel = 'split';
				customRoutes = cai;
				preset = sameList(cai, lanPreset) ? 'lan' : sameList(cai, subnetPreset) ? 'subnet' : 'custom';
			}
			dns = peer.client_dns ?? '';
			keepalive = String(peer.persistent_keepalive);
			expiresAt = peer.expires_at ?? '';
			expiryMode = peer.expires_at ? 'custom' : 'none';
			notes = peer.notes ?? '';
			enabled = peer.enabled;
		} else {
			name = '';
			addressMode = 'auto';
			allowedIps = '';
			const def = s?.default_client_allowed_ips ?? FULL_TUNNEL;
			tunnel = isFullTunnel(def) ? 'full' : 'split';
			preset = tunnel === 'split' ? (sameList(def, lanPreset) ? 'lan' : sameList(def, subnetPreset) ? 'subnet' : 'custom') : 'lan';
			customRoutes = tunnel === 'split' ? def : lanPreset;
			dns = '';
			keepalive = String(s?.default_keepalive ?? 25);
			expiryMode = 'none';
			expiresAt = '';
			notes = '';
			enabled = true;
			void loadNextIp();
		}
	}

	async function loadNextIp() {
		try {
			const r = await api.interfaces.nextIp(iface.name);
			nextIp = r.allowed_ips;
		} catch {
			nextIp = null;
		}
	}

	$effect(() => {
		if (open) reset();
	});

	const effectiveRoutes = $derived.by(() => {
		if (tunnel === 'full') return FULL_TUNNEL;
		if (preset === 'lan') return lanPreset;
		if (preset === 'subnet') return subnetPreset;
		return customRoutes;
	});

	function expiryFromMode(mode: ExpiryMode): string | null {
		const days = mode === '1d' ? 1 : mode === '7d' ? 7 : mode === '30d' ? 30 : 0;
		if (mode === 'none') return null;
		if (mode === 'custom') return expiresAt || null;
		return new Date(Date.now() + days * 86400_000).toISOString();
	}

	const errors = $derived({
		name: validatePeerName(name),
		allowedIps: addressMode === 'manual' ? validateCidrList(allowedIps) : null,
		routes: tunnel === 'split' && preset === 'custom' ? validateCidrList(customRoutes) : null,
		dns: validateDnsList(dns),
		keepalive: validateKeepalive(keepalive),
		expiresAt: expiryMode === 'custom' && !expiresAt ? 'Pick a date and time' : null
	});
	const valid = $derived(Object.values(errors).every((e) => e === null));

	function show(key: keyof typeof errors) {
		return touched[key] ? errors[key] : null;
	}

	async function submit() {
		touched = { name: true, allowedIps: true, routes: true, dns: true, keepalive: true, expiresAt: true };
		if (!valid || submitting) return;
		submitting = true;
		formError = null;
		try {
			if (peer) {
				const body: PeerUpdateRequest = {
					name: name.trim(),
					allowed_ips: joinList(splitList(allowedIps)),
					client_allowed_ips: joinList(splitList(effectiveRoutes)),
					client_dns: dns.trim() ? joinList(splitList(dns)) : null,
					persistent_keepalive: Number(keepalive),
					expires_at: expiryFromMode(expiryMode),
					notes: notes.trim() || null,
					enabled
				};
				const saved = await api.peers.update(peer.id, body);
				toast.success(`Peer "${saved.name}" updated`);
				onsaved(saved, false);
			} else {
				const body: PeerCreateRequest = {
					name: name.trim(),
					allowed_ips: addressMode === 'auto' ? 'auto' : joinList(splitList(allowedIps)),
					client_allowed_ips: joinList(splitList(effectiveRoutes)),
					client_dns: dns.trim() ? joinList(splitList(dns)) : null,
					persistent_keepalive: Number(keepalive),
					expires_at: expiryFromMode(expiryMode),
					notes: notes.trim() || null,
					enabled: true
				};
				const created = await api.interfaces.createPeer(iface.name, body);
				toast.success(`Peer "${created.name}" created`);
				onsaved(created, true);
			}
			open = false;
		} catch (err) {
			const e = toApiError(err);
			formError = e instanceof ApiError ? e.detail : 'Could not save the peer';
		} finally {
			submitting = false;
		}
	}
</script>

<Dialog bind:open title={editing ? `Edit ${peer?.name}` : `New peer on ${iface.name}`} size="lg" locked={submitting}>
	<form
		id="peer-form"
		class="flex flex-col gap-5"
		onsubmit={(e) => {
			e.preventDefault();
			void submit();
		}}
	>
		{#if formError}
			<Alert tone="danger">{formError}</Alert>
		{/if}

		<Input
			label="Name"
			bind:value={name}
			placeholder="e.g. alice-laptop"
			required
			autocomplete="off"
			error={show('name')}
			onblur={() => (touched = { ...touched, name: true })}
		/>

		<fieldset class="flex flex-col gap-2">
			<legend class="mb-1 text-sm font-medium text-fg">Tunnel address</legend>
			<SegmentedControl
				bind:value={addressMode}
				label="Address assignment"
				options={[
					{ value: 'auto', label: 'Automatic' },
					{ value: 'manual', label: 'Manual' }
				]}
			/>
			{#if addressMode === 'auto'}
				<p class="text-[13px] text-fg-subtle">
					{#if nextIp}
						Next free address: <span class="font-mono text-fg">{nextIp}</span>
					{:else}
						The next free address in <span class="font-mono">{iface.address}</span> will be assigned.
					{/if}
				</p>
			{:else}
				<Input
					label="Allowed IPs (client addresses)"
					hideLabel
					mono
					bind:value={allowedIps}
					placeholder={nextIp ?? '10.8.0.2/32'}
					hint="Comma-separated CIDRs the client uses inside the tunnel."
					error={show('allowedIps')}
					onblur={() => (touched = { ...touched, allowedIps: true })}
				/>
			{/if}
		</fieldset>

		<fieldset class="flex flex-col gap-3">
			<legend class="mb-1 text-sm font-medium text-fg">Routing</legend>
			<SegmentedControl
				bind:value={tunnel}
				label="Tunnel mode"
				options={[
					{ value: 'full', label: 'Full tunnel' },
					{ value: 'split', label: 'Split tunnel' }
				]}
			/>
			{#if tunnel === 'full'}
				<p class="text-[13px] text-fg-subtle">All client traffic is routed through the VPN (<span class="font-mono">{FULL_TUNNEL}</span>).</p>
			{:else}
				<div class="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Split-tunnel preset">
					{#each [{ v: 'lan', t: 'LAN only', d: 'Private ranges + this subnet' }, { v: 'subnet', t: 'Interface subnet', d: subnetPreset || 'No subnet' }, { v: 'custom', t: 'Custom', d: 'Enter your own routes' }] as p (p.v)}
						<label
							class={`flex cursor-pointer flex-col gap-0.5 rounded-md border px-3 py-2.5 text-sm transition-colors ${preset === p.v ? 'border-accent bg-accent-soft/50' : 'border-border hover:border-border-strong'}`}
						>
							<span class="flex items-center gap-2 font-medium text-fg">
								<input type="radio" name="preset" value={p.v} bind:group={preset} class="accent-accent" />
								{p.t}
							</span>
							<span class="pl-5 font-mono text-[11px] text-fg-subtle break-all">{p.d}</span>
						</label>
					{/each}
				</div>
				{#if preset === 'custom'}
					<Textarea
						label="Routes"
						mono
						rows={2}
						bind:value={customRoutes}
						placeholder="10.8.0.0/24, 192.168.1.0/24"
						hint="Comma-separated CIDRs the client sends through the tunnel."
						error={show('routes')}
						onblur={() => (touched = { ...touched, routes: true })}
					/>
				{:else}
					<p class="font-mono text-[12px] text-fg-subtle break-all">{effectiveRoutes}</p>
				{/if}
			{/if}
		</fieldset>

		<div class="grid gap-4 sm:grid-cols-2">
			<Input
				label="DNS override"
				mono
				bind:value={dns}
				placeholder={iface.dns ?? settingsStore.server?.default_dns ?? '1.1.1.1'}
				hint="Leave empty to use the interface or global DNS."
				error={show('dns')}
				onblur={() => (touched = { ...touched, dns: true })}
			/>
			<Input
				label="Persistent keepalive (s)"
				type="number"
				inputmode="numeric"
				min="0"
				max="65535"
				bind:value={keepalive}
				hint="0 disables keepalive."
				error={show('keepalive')}
				onblur={() => (touched = { ...touched, keepalive: true })}
			/>
		</div>

		<fieldset class="flex flex-col gap-2">
			<legend class="mb-1 text-sm font-medium text-fg">Expiry</legend>
			<SegmentedControl
				bind:value={expiryMode}
				label="Expiry"
				options={[
					{ value: 'none', label: 'Never' },
					{ value: '1d', label: '1 day' },
					{ value: '7d', label: '7 days' },
					{ value: '30d', label: '30 days' },
					{ value: 'custom', label: 'Custom' }
				]}
			/>
			{#if expiryMode === 'custom'}
				<DateTimePicker label="Expires at" bind:value={expiresAt} error={show('expiresAt')} min={new Date().toISOString()} />
			{:else if expiryMode !== 'none'}
				<p class="text-[13px] text-fg-subtle">The peer disables itself automatically when it expires.</p>
			{/if}
		</fieldset>

		<Textarea label="Notes" bind:value={notes} rows={2} placeholder="Optional notes, e.g. device owner" />

		{#if editing}
			<Switch bind:checked={enabled} label="Enabled" description="Disabled peers are removed from the running configuration." />
		{/if}
	</form>

	{#snippet footer()}
		<Button variant="ghost" onclick={() => (open = false)} disabled={submitting}>Cancel</Button>
		<Button variant="primary" type="submit" form="peer-form" loading={submitting}>
			{editing ? 'Save changes' : 'Create peer'}
		</Button>
	{/snippet}
</Dialog>

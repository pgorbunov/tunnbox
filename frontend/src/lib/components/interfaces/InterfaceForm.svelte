<script lang="ts">
	/**
	 * Create-interface wizard: Basics -> Network -> Review. Suggests the next
	 * free name (wg0, wg1, …), subnet (10.<n>.0.1/24) and port (51820+).
	 */
	import { Check, ChevronLeft, ChevronRight } from 'lucide-svelte';
	import { untrack } from 'svelte';
	import { api, toApiError } from '$lib/api';
	import type { Interface, InterfaceCreateRequest } from '$lib/api/types';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { joinList, splitList } from '$lib/utils/format';
	import {
		validateDnsList,
		validateEndpoint,
		validateInterfaceAddress,
		validateInterfaceName,
		validateMtu,
		validatePort
	} from '$lib/utils/validation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';

	interface Props {
		open: boolean;
		existing: Interface[];
		oncreated: (iface: Interface) => void;
	}

	let { open = $bindable(false), existing, oncreated }: Props = $props();

	const STEPS = ['Basics', 'Network', 'Review'] as const;
	let step = $state(0);
	let name = $state('');
	let address = $state('');
	let port = $state('');
	let dns = $state('');
	let endpoint = $state('');
	let mtu = $state('');
	let postUp = $state('');
	let postDown = $state('');
	let enabled = $state(true);
	let advanced = $state(false);
	let submitting = $state(false);
	let formError = $state<string | null>(null);
	let touched = $state<Record<string, boolean>>({});

	const scriptsAllowed = $derived(settingsStore.server?.custom_scripts_allowed ?? false);

	function suggest() {
		const names = new Set(existing.map((i) => i.name));
		let n = 0;
		while (names.has(`wg${n}`)) n++;
		name = `wg${n}`;
		const used = new Set(
			existing.flatMap((i) => splitList(i.address).map((a) => a.split('.').slice(0, 2).join('.')))
		);
		let octet = 8;
		while (used.has(`10.${octet}`)) octet++;
		address = `10.${octet}.0.1/24`;
		const ports = new Set(existing.map((i) => i.listen_port));
		let p = 51820;
		while (ports.has(p)) p++;
		port = String(p);
		dns = settingsStore.server?.default_dns ?? '';
		endpoint = '';
		mtu = '';
		postUp = '';
		postDown = '';
		enabled = true;
		advanced = false;
		step = 0;
		touched = {};
		formError = null;
	}

	$effect(() => {
		if (open) untrack(suggest);
	});

	const errors = $derived({
		name:
			validateInterfaceName(name) ??
			(existing.some((i) => i.name === name.trim()) ? 'An interface with this name already exists' : null),
		address: validateInterfaceAddress(address),
		port:
			validatePort(port) ??
			(existing.some((i) => String(i.listen_port) === port.trim())
				? 'This port is already used by another interface'
				: null),
		dns: validateDnsList(dns),
		endpoint: validateEndpoint(endpoint, { allowEmpty: true }),
		mtu: validateMtu(mtu)
	});
	const stepValid = $derived([
		!errors.name && !errors.address && !errors.port,
		!errors.dns && !errors.endpoint && !errors.mtu,
		true
	]);

	function show(key: keyof typeof errors) {
		return touched[key] ? errors[key] : null;
	}
	function touch(key: string) {
		touched = { ...touched, [key]: true };
	}

	function next() {
		if (step === 0) touched = { ...touched, name: true, address: true, port: true };
		if (step === 1) touched = { ...touched, dns: true, endpoint: true, mtu: true };
		if (!stepValid[step]) return;
		step = Math.min(STEPS.length - 1, step + 1);
	}

	async function submit() {
		if (!stepValid[0] || !stepValid[1] || submitting) return;
		submitting = true;
		formError = null;
		const body: InterfaceCreateRequest = {
			name: name.trim(),
			address: joinList(splitList(address)),
			listen_port: Number(port),
			dns: dns.trim() ? joinList(splitList(dns)) : null,
			mtu: mtu.trim() ? Number(mtu) : null,
			public_endpoint: endpoint.trim() || null,
			post_up: scriptsAllowed && postUp.trim() ? postUp.trim() : null,
			post_down: scriptsAllowed && postDown.trim() ? postDown.trim() : null,
			enabled
		};
		try {
			const created = await api.interfaces.create(body);
			toast.success(`Interface ${created.name} created`);
			open = false;
			oncreated(created);
		} catch (err) {
			formError = toApiError(err).detail;
		} finally {
			submitting = false;
		}
	}
</script>

<Dialog bind:open title="New interface" size="lg" locked={submitting}>
	{#snippet header()}
		<ol class="flex items-center gap-2 text-[13px]" aria-label="Steps">
			{#each STEPS as label, i (label)}
				<li class="flex items-center gap-2" aria-current={i === step ? 'step' : undefined}>
					<span
						class={`flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold
							${i < step ? 'bg-accent text-accent-fg' : i === step ? 'bg-accent-soft text-accent ring-1 ring-accent' : 'bg-bg-subtle text-fg-subtle'}`}
					>
						{#if i < step}<Check class="h-3.5 w-3.5" aria-hidden="true" />{:else}{i + 1}{/if}
					</span>
					<span class={i === step ? 'font-medium text-fg' : 'text-fg-subtle'}>{label}</span>
					{#if i < STEPS.length - 1}<span class="h-px w-6 bg-border" aria-hidden="true"></span>{/if}
				</li>
			{/each}
		</ol>
	{/snippet}

	<form
		id="interface-form"
		class="flex flex-col gap-5"
		onsubmit={(e) => {
			e.preventDefault();
			if (step < STEPS.length - 1) next();
			else void submit();
		}}
	>
		{#if formError}
			<Alert tone="danger">{formError}</Alert>
		{/if}

		{#if step === 0}
			<Input
				label="Name"
				bind:value={name}
				mono
				required
				autocomplete="off"
				hint="1–15 characters, e.g. wg0"
				error={show('name')}
				onblur={() => touch('name')}
			/>
			<Input
				label="Address"
				bind:value={address}
				mono
				required
				hint="Server address with prefix; peers get addresses from this subnet. Add an IPv6 CIDR after a comma for dual-stack."
				error={show('address')}
				onblur={() => touch('address')}
			/>
			<Input
				label="Listen port"
				bind:value={port}
				type="number"
				inputmode="numeric"
				min="1"
				max="65535"
				required
				hint="UDP port to open on your firewall."
				error={show('port')}
				onblur={() => touch('port')}
			/>
		{:else if step === 1}
			<Input
				label="DNS for clients"
				bind:value={dns}
				mono
				hint="Comma-separated. Leave empty to use the global default."
				error={show('dns')}
				onblur={() => touch('dns')}
			/>
			<Input
				label="Public endpoint override"
				bind:value={endpoint}
				mono
				placeholder={settingsStore.server?.public_endpoint || 'vpn.example.com'}
				hint="Hostname or IP clients connect to. Defaults to the global endpoint in Settings."
				error={show('endpoint')}
				onblur={() => touch('endpoint')}
			/>
			<Switch bind:checked={advanced} label="Advanced options" size="sm" />
			{#if advanced}
				<div class="flex flex-col gap-4 rounded-md border border-border bg-bg-subtle/50 p-4">
					<Input
						label="MTU"
						bind:value={mtu}
						type="number"
						inputmode="numeric"
						min="1280"
						max="1500"
						placeholder="1420"
						hint="Leave empty for the default."
						error={show('mtu')}
						onblur={() => touch('mtu')}
					/>
					{#if scriptsAllowed}
						<Textarea
							label="PostUp"
							bind:value={postUp}
							mono
							rows={2}
							placeholder="iptables -A FORWARD -i %i -j ACCEPT; …"
						/>
						<Textarea
							label="PostDown"
							bind:value={postDown}
							mono
							rows={2}
							placeholder="iptables -D FORWARD -i %i -j ACCEPT; …"
						/>
					{:else}
						<p class="text-[13px] text-fg-subtle">
							PostUp/PostDown scripts are disabled on this server (WG_ALLOW_CUSTOM_SCRIPTS).
						</p>
					{/if}
				</div>
			{/if}
			<Switch bind:checked={enabled} label="Bring the interface up after creating it" size="sm" />
		{:else}
			<dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
				<dt class="text-fg-subtle">Name</dt>
				<dd class="font-mono text-fg">{name}</dd>
				<dt class="text-fg-subtle">Address</dt>
				<dd class="font-mono text-fg">{address}</dd>
				<dt class="text-fg-subtle">Listen port</dt>
				<dd class="font-mono text-fg">{port}/udp</dd>
				<dt class="text-fg-subtle">DNS</dt>
				<dd class="font-mono text-fg">{dns || 'Global default'}</dd>
				<dt class="text-fg-subtle">Endpoint</dt>
				<dd class="font-mono text-fg">
					{endpoint || settingsStore.server?.public_endpoint || 'Global default'}
				</dd>
				<dt class="text-fg-subtle">MTU</dt>
				<dd class="font-mono text-fg">{mtu || 'Default'}</dd>
				<dt class="text-fg-subtle">State</dt>
				<dd class="text-fg">{enabled ? 'Up after creation' : 'Created down'}</dd>
			</dl>
			<Alert tone="info"
				>A key pair is generated for the interface. Remember to open UDP port {port} on your firewall.</Alert
			>
		{/if}
	</form>

	{#snippet footer()}
		{#if step > 0}
			<Button variant="ghost" onclick={() => (step -= 1)} disabled={submitting} class="sm:mr-auto">
				<ChevronLeft class="h-4 w-4" aria-hidden="true" />
				Back
			</Button>
		{/if}
		<Button variant="ghost" onclick={() => (open = false)} disabled={submitting}>Cancel</Button>
		{#if step < STEPS.length - 1}
			<Button variant="primary" type="submit" form="interface-form">
				Continue
				<ChevronRight class="h-4 w-4" aria-hidden="true" />
			</Button>
		{:else}
			<Button variant="primary" type="submit" form="interface-form" loading={submitting}
				>Create interface</Button
			>
		{/if}
	{/snippet}
</Dialog>

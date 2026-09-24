<script lang="ts">
	/** MFA status card: enable (setup dialog), disable (password + code), regenerate recovery codes. */
	import { ShieldCheck, ShieldOff } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { validateTotpOrRecovery } from '$lib/utils/validation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import MfaSetupDialog from './MfaSetupDialog.svelte';
	import RecoveryCodes from './RecoveryCodes.svelte';

	const enabled = $derived(auth.user?.totp_enabled ?? false);

	let setupOpen = $state(false);
	let disableOpen = $state(false);
	let regenOpen = $state(false);
	let password = $state('');
	let code = $state('');
	let busy = $state(false);
	let error = $state<string | null>(null);
	let codes = $state<string[] | null>(null);
	let acknowledged = $state(false);

	function refreshUser() {
		void api.auth
			.me()
			.then((u) => auth.setUser(u))
			.catch(() => undefined);
	}

	$effect(() => {
		if (!disableOpen && !regenOpen) {
			password = '';
			code = '';
			codes = null;
			error = null;
		}
	});

	function openDisable() {
		password = '';
		code = '';
		error = null;
		disableOpen = true;
	}
	function openRegen() {
		password = '';
		error = null;
		codes = null;
		acknowledged = false;
		regenOpen = true;
	}

	async function disable() {
		const codeErr = validateTotpOrRecovery(code);
		if (!password || codeErr) {
			error = codeErr ?? 'Enter your password';
			return;
		}
		busy = true;
		error = null;
		try {
			await api.mfa.disable(password, code.trim());
			toast.success('Two-factor authentication disabled');
			disableOpen = false;
			refreshUser();
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			busy = false;
		}
	}

	async function regenerate() {
		if (!password) {
			error = 'Enter your password';
			return;
		}
		busy = true;
		error = null;
		try {
			const r = await api.mfa.regenerateRecoveryCodes(password);
			codes = r.recovery_codes;
			toast.success('New recovery codes generated', { description: 'Previous codes no longer work.' });
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			busy = false;
		}
	}
</script>

<Card
	title="Two-factor authentication"
	description="Require a code from an authenticator app when signing in."
>
	<div class="flex flex-wrap items-center justify-between gap-4">
		<div class="flex items-center gap-3">
			<span
				class={`flex h-10 w-10 items-center justify-center rounded-md ${enabled ? 'bg-success-soft text-success' : 'bg-bg-subtle text-fg-subtle'}`}
				aria-hidden="true"
			>
				{#if enabled}<ShieldCheck class="h-5 w-5" />{:else}<ShieldOff class="h-5 w-5" />{/if}
			</span>
			<div class="text-sm">
				<p class="flex items-center gap-2 font-medium text-fg">
					Authenticator app
					<Badge tone={enabled ? 'success' : 'neutral'} size="sm">{enabled ? 'Enabled' : 'Off'}</Badge>
				</p>
				<p class="text-[13px] text-fg-subtle">
					{enabled
						? 'Your account is protected with TOTP codes.'
						: 'Strongly recommended for admin accounts.'}
				</p>
			</div>
		</div>
		<div class="flex flex-wrap gap-2">
			{#if enabled}
				<Button size="sm" onclick={openRegen}>Regenerate recovery codes</Button>
				<Button size="sm" variant="danger-soft" onclick={openDisable}>Disable</Button>
			{:else}
				<Button size="sm" variant="primary" onclick={() => (setupOpen = true)}>Enable two-factor</Button>
			{/if}
		</div>
	</div>
</Card>

<MfaSetupDialog bind:open={setupOpen} onenabled={refreshUser} />

<Dialog bind:open={disableOpen} title="Disable two-factor authentication" size="sm" locked={busy}>
	<form
		id="mfa-disable-form"
		class="flex flex-col gap-4"
		onsubmit={(e) => {
			e.preventDefault();
			void disable();
		}}
	>
		{#if error}
			<Alert tone="danger">{error}</Alert>
		{/if}
		<Input label="Password" type="password" autocomplete="current-password" bind:value={password} required />
		<Input
			label="Authenticator or recovery code"
			mono
			inputmode="numeric"
			autocomplete="one-time-code"
			bind:value={code}
			required
		/>
	</form>
	{#snippet footer()}
		<Button variant="ghost" onclick={() => (disableOpen = false)} disabled={busy}>Cancel</Button>
		<Button variant="danger" type="submit" form="mfa-disable-form" loading={busy}>Disable</Button>
	{/snippet}
</Dialog>

<Dialog
	bind:open={regenOpen}
	title={codes ? 'Your new recovery codes' : 'Regenerate recovery codes'}
	size="md"
	locked={busy || (!!codes && !acknowledged)}
>
	{#if codes}
		<RecoveryCodes {codes} bind:acknowledged />
	{:else}
		<form
			id="mfa-regen-form"
			class="flex flex-col gap-4"
			onsubmit={(e) => {
				e.preventDefault();
				void regenerate();
			}}
		>
			<p class="text-sm text-fg-muted">
				This invalidates all existing recovery codes. Confirm your password to continue.
			</p>
			{#if error}
				<Alert tone="danger">{error}</Alert>
			{/if}
			<Input
				label="Password"
				type="password"
				autocomplete="current-password"
				bind:value={password}
				required
			/>
		</form>
	{/if}
	{#snippet footer()}
		{#if codes}
			<Button variant="primary" disabled={!acknowledged} onclick={() => (regenOpen = false)}>Done</Button>
		{:else}
			<Button variant="ghost" onclick={() => (regenOpen = false)} disabled={busy}>Cancel</Button>
			<Button variant="primary" type="submit" form="mfa-regen-form" loading={busy}>Generate new codes</Button>
		{/if}
	{/snippet}
</Dialog>

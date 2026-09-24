<script lang="ts">
	/**
	 * Enable TOTP in three steps: confirm password -> scan QR + verify code ->
	 * save recovery codes (shown once). The password is sent on both the setup
	 * and enable calls, per the API contract.
	 */
	import { api, toApiError } from '$lib/api';
	import type { MfaSetupResponse } from '$lib/api/types';
	import { toast } from '$lib/stores/toast.svelte';
	import { isTotpCode } from '$lib/utils/validation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import RecoveryCodes from './RecoveryCodes.svelte';

	interface Props {
		open: boolean;
		onenabled: () => void;
	}
	let { open = $bindable(false), onenabled }: Props = $props();

	type Step = 'password' | 'enrol' | 'codes';
	let step = $state<Step>('password');
	let password = $state('');
	let setup = $state<MfaSetupResponse | null>(null);
	let busy = $state(false);
	let error = $state<string | null>(null);
	let code = $state('');
	let codes = $state<string[] | null>(null);
	let acknowledged = $state(false);
	let lastAutoCode = '';

	const qrSrc = $derived(setup ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}` : '');
	const title = $derived(
		step === 'codes'
			? 'Save your recovery codes'
			: step === 'enrol'
				? 'Scan and verify'
				: 'Set up two-factor authentication'
	);

	$effect(() => {
		if (!open) return;
		step = 'password';
		password = '';
		setup = null;
		codes = null;
		code = '';
		error = null;
		acknowledged = false;
		lastAutoCode = '';
	});

	async function start() {
		if (!password || busy) return;
		busy = true;
		error = null;
		try {
			setup = await api.mfa.setup(password);
			step = 'enrol';
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			busy = false;
		}
	}

	async function verify() {
		const c = code.trim();
		if (!isTotpCode(c) || busy) return;
		busy = true;
		error = null;
		try {
			const r = await api.mfa.enable(c, password);
			codes = r.recovery_codes;
			step = 'codes';
			toast.success('Two-factor authentication enabled');
			onenabled();
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			busy = false;
		}
	}

	// Auto-verify once per fully typed / pasted 6-digit code.
	$effect(() => {
		const c = code.trim();
		if (step === 'enrol' && isTotpCode(c) && c !== lastAutoCode) {
			lastAutoCode = c;
			void verify();
		}
	});
</script>

<Dialog bind:open {title} size="md" locked={busy || (step === 'codes' && !acknowledged)}>
	{#if step === 'codes' && codes}
		<RecoveryCodes {codes} bind:acknowledged />
	{:else if step === 'password'}
		<form
			id="mfa-start-form"
			class="flex flex-col gap-4"
			onsubmit={(e) => {
				e.preventDefault();
				void start();
			}}
		>
			<p class="text-sm text-fg-muted">
				You will scan a QR code with an authenticator app and enter the code it shows. First, confirm your
				password.
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
	{:else}
		<div class="flex flex-col gap-5">
			{#if error}
				<Alert tone="danger">{error}</Alert>
			{/if}
			<ol class="flex flex-col gap-4 text-sm text-fg-muted">
				<li class="flex gap-3">
					<span
						class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-bg-subtle text-[12px] font-semibold text-fg"
						>1</span
					>
					<div class="flex-1">
						<p class="font-medium text-fg">Scan this QR code with an authenticator app</p>
						<p class="mt-0.5">Google Authenticator, 1Password, Aegis, Authy, and similar apps all work.</p>
						<div class="mt-3 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
							<div class="rounded-lg border border-border bg-white p-2">
								{#if setup}
									<img
										src={qrSrc}
										alt="TOTP enrolment QR code"
										width="160"
										height="160"
										class="block h-40 w-40"
									/>
								{:else}
									<Skeleton class="h-40 w-40" rounded="md" />
								{/if}
							</div>
							{#if setup}
								<div class="min-w-0 text-[13px]">
									<p class="text-fg-subtle">Or enter the key manually:</p>
									<div class="mt-1 flex items-center gap-1">
										<code class="font-mono break-all text-fg">{setup.secret}</code>
										<CopyButton text={setup.secret} label="Copy secret" />
									</div>
								</div>
							{/if}
						</div>
					</div>
				</li>
				<li class="flex gap-3">
					<span
						class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-bg-subtle text-[12px] font-semibold text-fg"
						>2</span
					>
					<div class="flex-1">
						<p class="font-medium text-fg">Enter the 6-digit code from the app</p>
						<form
							id="mfa-verify-form"
							class="mt-3 flex items-end gap-2"
							onsubmit={(e) => {
								e.preventDefault();
								void verify();
							}}
						>
							<Input
								label="Verification code"
								hideLabel
								bind:value={code}
								mono
								inputmode="numeric"
								autocomplete="one-time-code"
								maxlength={6}
								placeholder="123456"
								class="w-40"
							/>
							<Button variant="primary" type="submit" loading={busy} disabled={!isTotpCode(code)}
								>Verify</Button
							>
						</form>
					</div>
				</li>
			</ol>
		</div>
	{/if}

	{#snippet footer()}
		{#if step === 'codes'}
			<Button variant="primary" disabled={!acknowledged} onclick={() => (open = false)}>Done</Button>
		{:else if step === 'password'}
			<Button variant="ghost" onclick={() => (open = false)} disabled={busy}>Cancel</Button>
			<Button variant="primary" type="submit" form="mfa-start-form" loading={busy} disabled={!password}
				>Continue</Button
			>
		{:else}
			<Button variant="ghost" onclick={() => (open = false)} disabled={busy}>Cancel</Button>
		{/if}
	{/snippet}
</Dialog>

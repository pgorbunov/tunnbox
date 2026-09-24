<script lang="ts">
	/** Enable TOTP: show QR + secret, verify a code, then reveal recovery codes once. */
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

	let setup = $state<MfaSetupResponse | null>(null);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let code = $state('');
	let verifying = $state(false);
	let codes = $state<string[] | null>(null);
	let acknowledged = $state(false);
	let lastAutoCode = '';

	const qrSrc = $derived(setup ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}` : '');

	$effect(() => {
		if (!open) return;
		setup = null;
		codes = null;
		code = '';
		error = null;
		acknowledged = false;
		loading = true;
		void api.mfa
			.setup()
			.then((r) => (setup = r))
			.catch((err) => (error = toApiError(err).detail))
			.finally(() => (loading = false));
	});

	async function verify() {
		if (!isTotpCode(code) || verifying) return;
		verifying = true;
		error = null;
		try {
			const r = await api.mfa.enable(code.trim());
			codes = r.recovery_codes;
			toast.success('Two-factor authentication enabled');
			onenabled();
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			verifying = false;
		}
	}

	$effect(() => {
		const c = code.trim();
		if (isTotpCode(c) && !codes && c !== lastAutoCode) {
			lastAutoCode = c;
			void verify();
		}
	});
</script>

<Dialog
	bind:open
	title={codes ? 'Save your recovery codes' : 'Set up two-factor authentication'}
	size="md"
	locked={verifying || (!!codes && !acknowledged)}
>
	{#if codes}
		<RecoveryCodes {codes} bind:acknowledged />
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
								{#if setup && !loading}
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
								disabled={!setup}
								class="w-40"
							/>
							<Button variant="primary" type="submit" loading={verifying} disabled={!isTotpCode(code)}
								>Verify</Button
							>
						</form>
					</div>
				</li>
			</ol>
		</div>
	{/if}

	{#snippet footer()}
		{#if codes}
			<Button variant="primary" disabled={!acknowledged} onclick={() => (open = false)}>Done</Button>
		{:else}
			<Button variant="ghost" onclick={() => (open = false)} disabled={verifying}>Cancel</Button>
		{/if}
	{/snippet}
</Dialog>

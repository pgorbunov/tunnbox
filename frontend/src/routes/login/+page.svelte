<script lang="ts">
	/** Sign-in: username/password, then an optional TOTP / recovery-code step. */
	import { ArrowLeft, LogIn } from 'lucide-svelte';
	import { ApiError, toApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { isRecoveryCode, isTotpCode } from '$lib/utils/validation';
	import Logo from '$lib/components/app/Logo.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';

	let username = $state('');
	let password = $state('');
	let code = $state('');
	let mfaToken = $state<string | null>(null);
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let lockedUntil = $state<number | null>(null);
	let codeInput = $state<HTMLInputElement | null>(null);

	function describe(err: unknown): string {
		const e = toApiError(err);
		if (e instanceof ApiError) {
			if (e.status === 423) return 'Account temporarily locked. Try again in about 15 minutes.';
			if (e.status === 429) {
				const s = e.retryAfter ?? 60;
				return `Too many attempts. Please wait ${s >= 60 ? `${Math.ceil(s / 60)} min` : `${s}s`} and try again.`;
			}
			if (e.status === 401 || e.status === 400) return mfaToken ? 'That code is not valid. Check your authenticator and try again.' : 'Incorrect username or password.';
			if (e.isNetwork) return e.detail;
			return e.detail;
		}
		return 'Sign-in failed. Please try again.';
	}

	async function submitCredentials() {
		if (submitting || !username.trim() || !password) return;
		submitting = true;
		error = null;
		try {
			const res = await auth.login(username.trim(), password);
			if ('mfa_required' in res) {
				mfaToken = res.mfa_token;
				code = '';
				requestAnimationFrame(() => codeInput?.focus());
			}
			// On success the root layout redirects.
		} catch (err) {
			error = describe(err);
			lockedUntil = toApiError(err).status === 423 ? Date.now() + 15 * 60_000 : null;
		} finally {
			submitting = false;
		}
	}

	async function submitCode() {
		if (submitting || !mfaToken) return;
		const c = code.trim();
		if (!isTotpCode(c) && !isRecoveryCode(c)) {
			error = 'Enter the 6-digit code from your authenticator or a recovery code (xxxx-xxxx).';
			return;
		}
		submitting = true;
		error = null;
		try {
			await auth.loginMfa(mfaToken, c);
		} catch (err) {
			const e = toApiError(err);
			error = describe(err);
			if (e.status === 401 && /expired|invalid.*token/i.test(e.detail)) {
				mfaToken = null;
				error = 'The sign-in step timed out. Enter your password again.';
			}
		} finally {
			submitting = false;
		}
	}

	// Auto-submit when a full 6-digit TOTP code is typed or pasted.
	$effect(() => {
		if (mfaToken && isTotpCode(code) && !submitting) void submitCode();
	});

	function oncodeinput() {
		// Normalise recovery-code paste like "abcd efgh" -> "abcd-efgh".
		const v = code.trim();
		if (/^[a-zA-Z0-9]{4}[\s-]?[a-zA-Z0-9]{4}$/.test(v) && !/^\d{6,}$/.test(v)) code = `${v.slice(0, 4)}-${v.slice(-4)}`;
	}
</script>

<svelte:head>
	<title>Sign in · TunnBox</title>
</svelte:head>

<main class="flex min-h-dvh items-center justify-center bg-bg px-4 py-10">
	<div class="w-full max-w-sm">
		<div class="mb-8 flex justify-center">
			<Logo size={40} />
		</div>
		<div class="rounded-lg border border-border bg-surface p-6 shadow-md sm:p-8">
			{#if mfaToken}
				<h1 class="text-lg font-semibold text-fg" tabindex="-1">Two-factor authentication</h1>
				<p class="mt-1 text-sm text-fg-muted">Enter the 6-digit code from your authenticator app.</p>
				<form
					class="mt-6 flex flex-col gap-4"
					onsubmit={(e) => {
						e.preventDefault();
						void submitCode();
					}}
				>
					{#if error}
						<Alert tone="danger">{error}</Alert>
					{/if}
					<Input
						label="Verification code"
						bind:value={code}
						bind:ref={codeInput}
						mono
						inputmode="numeric"
						autocomplete="one-time-code"
						placeholder="123456"
						maxlength={9}
						required
						spellcheck={false}
						hint="You can also paste a recovery code (xxxx-xxxx)."
						oninput={oncodeinput}
					/>
					<Button variant="primary" type="submit" block size="lg" loading={submitting}>Verify</Button>
					<Button
						variant="ghost"
						block
						onclick={() => {
							mfaToken = null;
							code = '';
							error = null;
						}}
					>
						<ArrowLeft class="h-4 w-4" aria-hidden="true" />
						Back
					</Button>
				</form>
			{:else}
				<h1 class="text-lg font-semibold text-fg" tabindex="-1">Sign in</h1>
				<p class="mt-1 text-sm text-fg-muted">Manage your WireGuard server.</p>
				<form
					class="mt-6 flex flex-col gap-4"
					onsubmit={(e) => {
						e.preventDefault();
						void submitCredentials();
					}}
				>
					{#if error}
						<Alert tone={lockedUntil ? 'warning' : 'danger'}>{error}</Alert>
					{/if}
					<Input label="Username" bind:value={username} autocomplete="username" required autocapitalize="off" spellcheck={false} />
					<Input label="Password" type="password" bind:value={password} autocomplete="current-password" required />
					<Button variant="primary" type="submit" block size="lg" loading={submitting}>
						<LogIn class="h-4 w-4" aria-hidden="true" />
						Sign in
					</Button>
				</form>
			{/if}
		</div>
		{#if auth.version}
			<p class="mt-6 text-center text-xs text-fg-subtle">TunnBox v{auth.version}</p>
		{/if}
	</div>
</main>

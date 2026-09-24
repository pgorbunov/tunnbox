<script lang="ts">
	/** First-run wizard: Create admin -> Server endpoint -> Done. */
	import { goto } from '$app/navigation';
	import { ArrowRight, Check, Network, PartyPopper } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { validateEndpoint, validatePassword, validateUsername } from '$lib/utils/validation';
	import Logo from '$lib/components/app/Logo.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';

	const STEPS = ['Create admin', 'Server endpoint', 'Done'];
	let step = $state(auth.setupFlow ? 1 : 0);

	let username = $state('');
	let password = $state('');
	let confirm = $state('');
	let endpoint = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let touched = $state<Record<string, boolean>>({});

	const errors = $derived({
		username: validateUsername(username),
		password: validatePassword(password, username),
		confirm: confirm === password ? null : 'Passwords do not match',
		endpoint: validateEndpoint(endpoint, { allowEmpty: true })
	});
	const show = (k: keyof typeof errors) => (touched[k] ? errors[k] : null);

	async function createAdmin() {
		touched = { username: true, password: true, confirm: true };
		if (errors.username || errors.password || errors.confirm || submitting) return;
		submitting = true;
		error = null;
		try {
			await auth.setup(username.trim(), password);
			await prefillEndpoint();
			step = 1;
		} catch (err) {
			const e = toApiError(err);
			error = e.status === 409 ? 'Setup was already completed. Please sign in instead.' : e.detail;
		} finally {
			submitting = false;
		}
	}

	async function prefillEndpoint() {
		try {
			const s = await settingsStore.load(true);
			endpoint = s.public_endpoint ?? '';
		} catch {
			endpoint = '';
		}
	}

	$effect(() => {
		if (step === 1 && auth.setupFlow && !endpoint) void prefillEndpoint();
	});

	async function saveEndpoint() {
		touched = { ...touched, endpoint: true };
		if (errors.endpoint || submitting) return;
		submitting = true;
		error = null;
		try {
			const s = await api.settings.update({ public_endpoint: endpoint.trim() });
			settingsStore.set(s);
			step = 2;
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			submitting = false;
		}
	}

	function finish(target: string) {
		auth.finishSetupFlow();
		void goto(target, { replaceState: true });
	}
</script>

<svelte:head>
	<title>Set up · TunnBox</title>
</svelte:head>

<main class="flex min-h-dvh items-center justify-center bg-bg px-4 py-10">
	<div class="w-full max-w-md">
		<div class="mb-8 flex justify-center">
			<Logo size={40} />
		</div>

		<ol class="mb-6 flex items-center justify-center gap-2 text-[13px]" aria-label="Setup steps">
			{#each STEPS as label, i (label)}
				<li class="flex items-center gap-2" aria-current={i === step ? 'step' : undefined}>
					<span
						class={`flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold ${i < step ? 'bg-accent text-accent-fg' : i === step ? 'bg-accent-soft text-accent ring-1 ring-accent' : 'bg-bg-subtle text-fg-subtle'}`}
					>
						{#if i < step}<Check class="h-3.5 w-3.5" aria-hidden="true" />{:else}{i + 1}{/if}
					</span>
					<span class={i === step ? 'font-medium text-fg' : 'text-fg-subtle'}>{label}</span>
					{#if i < STEPS.length - 1}<span class="h-px w-5 bg-border" aria-hidden="true"></span>{/if}
				</li>
			{/each}
		</ol>

		<div class="rounded-lg border border-border bg-surface p-6 shadow-md sm:p-8">
			{#if step === 0}
				<h1 class="text-lg font-semibold text-fg" tabindex="-1">Welcome to TunnBox</h1>
				<p class="mt-1 text-sm text-fg-muted">Create the administrator account for this server.</p>
				<form
					class="mt-6 flex flex-col gap-4"
					onsubmit={(e) => {
						e.preventDefault();
						void createAdmin();
					}}
				>
					{#if error}
						<Alert tone="danger">{error}</Alert>
					{/if}
					<Input
						label="Username"
						bind:value={username}
						autocomplete="username"
						required
						autocapitalize="off"
						spellcheck={false}
						error={show('username')}
						onblur={() => (touched = { ...touched, username: true })}
					/>
					<Input
						label="Password"
						type="password"
						bind:value={password}
						autocomplete="new-password"
						required
						hint="10–128 characters; avoid common passwords."
						error={show('password')}
						onblur={() => (touched = { ...touched, password: true })}
					/>
					<Input
						label="Confirm password"
						type="password"
						bind:value={confirm}
						autocomplete="new-password"
						required
						error={show('confirm')}
						onblur={() => (touched = { ...touched, confirm: true })}
					/>
					<Button variant="primary" type="submit" block size="lg" loading={submitting}>
						Create account
						<ArrowRight class="h-4 w-4" aria-hidden="true" />
					</Button>
				</form>
			{:else if step === 1}
				<h1 class="text-lg font-semibold text-fg" tabindex="-1">Server endpoint</h1>
				<p class="mt-1 text-sm text-fg-muted">
					The public hostname or IP that clients use to reach this server. You can change it later in
					Settings.
				</p>
				<form
					class="mt-6 flex flex-col gap-4"
					onsubmit={(e) => {
						e.preventDefault();
						void saveEndpoint();
					}}
				>
					{#if error}
						<Alert tone="danger">{error}</Alert>
					{/if}
					<Input
						label="Public endpoint"
						bind:value={endpoint}
						mono
						placeholder="vpn.example.com"
						hint="Hostname or IP only — the port comes from each interface."
						error={show('endpoint')}
						onblur={() => (touched = { ...touched, endpoint: true })}
					/>
					<Button variant="primary" type="submit" block size="lg" loading={submitting}>
						Continue
						<ArrowRight class="h-4 w-4" aria-hidden="true" />
					</Button>
					<Button variant="ghost" block onclick={() => (step = 2)} disabled={submitting}>Skip for now</Button>
				</form>
			{:else}
				<div class="flex flex-col items-center text-center">
					<div
						class="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-accent"
						aria-hidden="true"
					>
						<PartyPopper class="h-7 w-7" />
					</div>
					<h1 class="text-lg font-semibold text-fg" tabindex="-1">You're all set</h1>
					<p class="mt-1 text-sm text-fg-muted">
						Create your first WireGuard interface, then add peers and share their configs in one click.
					</p>
					<div class="mt-6 flex w-full flex-col gap-2">
						<Button variant="primary" size="lg" block onclick={() => finish('/interfaces?new=1')}>
							<Network class="h-4 w-4" aria-hidden="true" />
							Create your first interface
						</Button>
						<Button variant="ghost" block onclick={() => finish('/')}>Go to dashboard</Button>
					</div>
				</div>
			{/if}
		</div>
	</div>
</main>

<script lang="ts">
	import { api, toApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { validatePassword } from '$lib/utils/validation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import Input from '$lib/components/ui/Input.svelte';

	let current = $state('');
	let next = $state('');
	let confirm = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);
	let touched = $state<Record<string, boolean>>({});

	const errors = $derived({
		current: current ? null : 'Enter your current password',
		next: validatePassword(next, auth.user?.username ?? ''),
		confirm: confirm === next ? null : 'Passwords do not match'
	});
	const valid = $derived(Object.values(errors).every((e) => e === null));
	const show = (k: keyof typeof errors) => (touched[k] ? errors[k] : null);

	async function submit() {
		touched = { current: true, next: true, confirm: true };
		if (!valid || saving) return;
		saving = true;
		error = null;
		try {
			await api.auth.changePassword({ current_password: current, new_password: next });
			toast.success('Password changed', { description: 'Other sessions have been signed out.' });
			current = next = confirm = '';
			touched = {};
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			saving = false;
		}
	}
</script>

<Card title="Password" description="Changing your password signs out every other session.">
	<form
		class="flex max-w-md flex-col gap-4"
		onsubmit={(e) => {
			e.preventDefault();
			void submit();
		}}
	>
		{#if error}
			<Alert tone="danger">{error}</Alert>
		{/if}
		<Input label="Current password" type="password" autocomplete="current-password" bind:value={current} error={show('current')} onblur={() => (touched = { ...touched, current: true })} />
		<Input label="New password" type="password" autocomplete="new-password" bind:value={next} hint="10–128 characters." error={show('next')} onblur={() => (touched = { ...touched, next: true })} />
		<Input label="Confirm new password" type="password" autocomplete="new-password" bind:value={confirm} error={show('confirm')} onblur={() => (touched = { ...touched, confirm: true })} />
		<div>
			<Button variant="primary" type="submit" loading={saving}>Update password</Button>
		</div>
	</form>
</Card>

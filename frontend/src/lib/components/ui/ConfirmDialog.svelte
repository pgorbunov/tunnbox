<script lang="ts">
	import type { Snippet } from 'svelte';
	import Button from './Button.svelte';
	import Dialog from './Dialog.svelte';
	import Input from './Input.svelte';

	interface Props {
		open: boolean;
		title: string;
		message?: string;
		confirmLabel?: string;
		cancelLabel?: string;
		tone?: 'danger' | 'primary';
		/** When set, the user must type this exact text to confirm. */
		confirmText?: string;
		confirmTextLabel?: string;
		loading?: boolean;
		onconfirm: () => void | Promise<void>;
		children?: Snippet;
	}

	let {
		open = $bindable(false),
		title,
		message,
		confirmLabel = 'Confirm',
		cancelLabel = 'Cancel',
		tone = 'danger',
		confirmText,
		confirmTextLabel,
		loading = false,
		onconfirm,
		children
	}: Props = $props();

	let typed = $state('');
	const ready = $derived(!confirmText || typed.trim() === confirmText);

	$effect(() => {
		if (!open) typed = '';
	});

	async function confirm() {
		if (!ready || loading) return;
		await onconfirm();
	}
</script>

<Dialog bind:open {title} description={message} size="sm" locked={loading}>
	<form
		id="confirm-form"
		onsubmit={(e) => {
			e.preventDefault();
			void confirm();
		}}
		class="flex flex-col gap-4"
	>
		{#if children}
			<div class="text-sm text-fg-muted">{@render children()}</div>
		{/if}
		{#if confirmText}
			<Input
				label={confirmTextLabel ?? `Type "${confirmText}" to confirm`}
				bind:value={typed}
				mono
				autocomplete="off"
				spellcheck={false}
				placeholder={confirmText}
			/>
		{/if}
	</form>
	{#snippet footer()}
		<Button variant="ghost" onclick={() => (open = false)} disabled={loading}>{cancelLabel}</Button>
		<Button
			variant={tone === 'danger' ? 'danger' : 'primary'}
			type="submit"
			form="confirm-form"
			disabled={!ready}
			{loading}
		>
			{confirmLabel}
		</Button>
	{/snippet}
</Dialog>

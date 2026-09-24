<script lang="ts">
	import { Check, Copy } from 'lucide-svelte';
	import { copyText } from '$lib/utils/dom';
	import { toast } from '$lib/stores/toast.svelte';
	import Button from './Button.svelte';
	import IconButton from './IconButton.svelte';

	interface Props {
		text: string | (() => Promise<string> | string);
		label?: string;
		/** Icon-only (default) or a labelled button. */
		variant?: 'icon' | 'button';
		size?: 'sm' | 'md';
		buttonVariant?: 'primary' | 'secondary' | 'ghost' | 'outline';
		/** Message announced on success. */
		successMessage?: string;
	}

	let {
		text,
		label = 'Copy',
		variant = 'icon',
		size = 'sm',
		buttonVariant = 'secondary',
		successMessage
	}: Props = $props();

	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout> | null = null;

	async function copy() {
		const value = typeof text === 'function' ? await text() : text;
		const ok = await copyText(value);
		if (!ok) {
			toast.error('Could not copy to clipboard');
			return;
		}
		copied = true;
		if (successMessage) toast.success(successMessage);
		if (timer) clearTimeout(timer);
		timer = setTimeout(() => (copied = false), 1600);
	}
</script>

{#if variant === 'icon'}
	<IconButton label={copied ? 'Copied' : label} {size} onclick={copy} class={copied ? 'text-success' : ''}>
		{#if copied}
			<Check class="h-4 w-4" />
		{:else}
			<Copy class="h-4 w-4" />
		{/if}
	</IconButton>
{:else}
	<Button variant={buttonVariant} {size} onclick={copy}>
		{#if copied}
			<Check class="h-4 w-4 text-success" aria-hidden="true" />
			Copied
		{:else}
			<Copy class="h-4 w-4" aria-hidden="true" />
			{label}
		{/if}
	</Button>
{/if}
<span class="sr-only" aria-live="polite">{copied ? 'Copied to clipboard' : ''}</span>

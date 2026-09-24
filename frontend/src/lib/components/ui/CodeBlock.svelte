<script lang="ts">
	/**
	 * Monospace block with copy. When `maskSecrets` is on, lines containing
	 * PrivateKey / PresharedKey show bullets until "Reveal" is pressed (per block).
	 */
	import { Eye, EyeOff } from 'lucide-svelte';
	import Button from './Button.svelte';
	import CopyButton from './CopyButton.svelte';

	interface Props {
		code: string;
		label?: string;
		maxHeight?: string;
		class?: string;
		/** Mask secret lines until revealed (default true). */
		maskSecrets?: boolean;
	}

	let {
		code,
		label = 'Code',
		maxHeight = '24rem',
		class: className = '',
		maskSecrets = true
	}: Props = $props();

	const SECRET_RE = /^\s*(PrivateKey|PresharedKey)\s*=/i;
	let revealed = $state(false);

	const hasSecrets = $derived(maskSecrets && code.split('\n').some((l) => SECRET_RE.test(l)));
	const shown = $derived(
		hasSecrets && !revealed
			? code
					.split('\n')
					.map((l) => (SECRET_RE.test(l) ? `${l.slice(0, l.indexOf('=') + 1)} ••••••••••••••••` : l))
					.join('\n')
			: code
	);

	$effect(() => {
		// Re-mask whenever the content changes.
		void code;
		revealed = false;
	});
</script>

<div class={`relative rounded-md border border-border bg-bg-subtle ${className}`}>
	<div class="absolute top-1.5 right-1.5 z-10 flex items-center gap-1">
		{#if hasSecrets}
			<Button size="sm" variant="ghost" onclick={() => (revealed = !revealed)} aria-pressed={revealed}>
				{#if revealed}
					<EyeOff class="h-4 w-4" aria-hidden="true" />
					Hide
				{:else}
					<Eye class="h-4 w-4" aria-hidden="true" />
					Reveal
				{/if}
			</Button>
		{/if}
		<CopyButton text={code} label={`Copy ${label.toLowerCase()}`} />
	</div>
	<pre
		class="overflow-auto p-4 pr-32 font-mono text-[13px] leading-relaxed text-fg scrollbar-thin"
		style={`max-height:${maxHeight}`}
		aria-label={label}><code>{shown}</code></pre>
	{#if hasSecrets}
		<p class="sr-only" aria-live="polite">{revealed ? 'Secrets revealed' : 'Secret keys are hidden'}</p>
	{/if}
</div>

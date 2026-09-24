<script lang="ts">
	import CopyButton from './CopyButton.svelte';

	interface Props {
		code: string;
		label?: string;
		/** Mask lines containing these keys (e.g. PrivateKey) until revealed. */
		maxHeight?: string;
		class?: string;
	}

	let { code, label = 'Code', maxHeight = '24rem', class: className = '' }: Props = $props();
</script>

<div class={`relative rounded-md border border-border bg-bg-subtle ${className}`}>
	<div class="absolute right-1.5 top-1.5 z-10">
		<CopyButton text={code} label={`Copy ${label.toLowerCase()}`} />
	</div>
	<pre
		class="scrollbar-thin overflow-auto p-4 pr-12 font-mono text-[13px] leading-relaxed text-fg"
		style={`max-height:${maxHeight}`}
		aria-label={label}><code>{code}</code></pre>
</div>

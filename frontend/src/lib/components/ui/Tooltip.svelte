<script lang="ts">
	import type { Snippet } from 'svelte';
	import { uid } from '$lib/utils/dom';

	interface Props {
		text: string;
		side?: 'top' | 'bottom';
		class?: string;
		children: Snippet;
	}

	let { text, side = 'top', class: className = '', children }: Props = $props();
	const id = uid('tip');
	let open = $state(false);
</script>

<span
	class={`relative inline-flex ${className}`}
	onpointerenter={() => (open = true)}
	onpointerleave={() => (open = false)}
	onfocusin={() => (open = true)}
	onfocusout={() => (open = false)}
	aria-describedby={id}
>
	{@render children()}
	<span
		{id}
		role="tooltip"
		class={`pointer-events-none absolute left-1/2 z-40 w-max max-w-[16rem] -translate-x-1/2 rounded-sm bg-fg px-2 py-1 text-xs text-bg shadow-md transition-opacity duration-150
			${side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5'} ${open ? 'opacity-100' : 'opacity-0'}`}
	>
		{text}
	</span>
</span>

<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		description?: string;
		icon?: Snippet;
		/** Primary (and optional secondary) actions. */
		actions?: Snippet;
		compact?: boolean;
		class?: string;
	}

	let { title, description, icon, actions, compact = false, class: className = '' }: Props = $props();
</script>

<div class={`flex flex-col items-center justify-center text-center ${compact ? 'px-4 py-8' : 'px-6 py-14'} ${className}`}>
	{#if icon}
		<div class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-bg-subtle text-fg-subtle" aria-hidden="true">
			{@render icon()}
		</div>
	{/if}
	<h3 class="text-base font-semibold text-fg">{title}</h3>
	{#if description}
		<p class="mt-1 max-w-sm text-sm text-fg-muted">{description}</p>
	{/if}
	{#if actions}
		<div class="mt-5 flex flex-wrap items-center justify-center gap-2">{@render actions()}</div>
	{/if}
</div>

<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title?: string;
		description?: string;
		/** Extra content in the header's right slot. */
		actions?: Snippet;
		/** Remove body padding (for tables). */
		flush?: boolean;
		as?: 'div' | 'section' | 'article';
		class?: string;
		id?: string;
		children: Snippet;
		footer?: Snippet;
	}

	let { title, description, actions, flush = false, as = 'section', class: className = '', id, children, footer }: Props =
		$props();
</script>

<svelte:element this={as} {id} class={`rounded-lg border border-border bg-surface shadow-sm ${className}`}>
	{#if title || actions}
		<header class="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
			<div class="min-w-0">
				{#if title}
					<h2 class="text-sm font-semibold text-fg">{title}</h2>
				{/if}
				{#if description}
					<p class="mt-0.5 text-[13px] text-fg-subtle">{description}</p>
				{/if}
			</div>
			{#if actions}
				<div class="flex shrink-0 items-center gap-2">{@render actions()}</div>
			{/if}
		</header>
	{/if}
	<div class={flush ? '' : 'p-4 sm:p-5'}>
		{@render children()}
	</div>
	{#if footer}
		<footer class="border-t border-border px-4 py-3 sm:px-5">{@render footer()}</footer>
	{/if}
</svelte:element>

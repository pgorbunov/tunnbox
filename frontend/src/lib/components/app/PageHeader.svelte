<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		description?: string;
		/** Rendered before the title (e.g. status badge). */
		badge?: Snippet;
		actions?: Snippet;
		/** Extra row under the header (filters, tabs). */
		children?: Snippet;
		mono?: boolean;
	}

	let { title, description, badge, actions, children, mono = false }: Props = $props();
</script>

<div class="mb-6 flex flex-col gap-4">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div class="min-w-0">
			<div class="flex flex-wrap items-center gap-2.5">
				<h1
					class={`min-w-0 truncate text-xl font-semibold tracking-tight text-fg outline-none sm:text-2xl ${mono ? 'font-mono' : ''}`}
					tabindex="-1"
					data-page-heading
				>
					{title}
				</h1>
				{#if badge}
					{@render badge()}
				{/if}
			</div>
			{#if description}
				<p class="mt-1 text-sm text-fg-muted">{description}</p>
			{/if}
		</div>
		{#if actions}
			<div class="flex flex-wrap items-center gap-2">{@render actions()}</div>
		{/if}
	</div>
	{#if children}
		{@render children()}
	{/if}
</div>

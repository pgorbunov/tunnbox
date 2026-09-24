<script lang="ts">
	import type { Snippet } from 'svelte';
	let { children }: { children: Snippet } = $props();
</script>

<kbd
	class="inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-border bg-bg-subtle px-1.5 font-sans text-[11px] font-medium text-fg-muted shadow-[inset_0_-1px_0_var(--border-strong)]"
>
	{@render children()}
</kbd>

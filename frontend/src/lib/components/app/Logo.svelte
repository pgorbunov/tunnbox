<script lang="ts">
	let { size = 28, wordmark = true, class: className = '' }: { size?: number; wordmark?: boolean; class?: string } = $props();
</script>

<span class={`inline-flex items-center gap-2.5 ${className}`}>
	<img src="/logo.svg" alt="" width={size} height={size} class="shrink-0" aria-hidden="true" />
	{#if wordmark}
		<span class="text-[17px] font-semibold tracking-tight text-fg">Tunn<span class="text-accent">Box</span></span>
	{/if}
</span>

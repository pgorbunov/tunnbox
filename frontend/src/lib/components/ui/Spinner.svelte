<script lang="ts">
	let { size = 16, class: className = '', label = 'Loading' }: { size?: number; class?: string; label?: string } = $props();
</script>

<svg
	class={`animate-spin motion-reduce:animate-none shrink-0 ${className}`}
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	role="status"
	aria-label={label}
>
	<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-opacity="0.25" stroke-width="3" />
	<path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
</svg>

<script lang="ts">
	interface Props {
		/** Tailwind size classes, e.g. "h-4 w-32". */
		class?: string;
		rounded?: 'sm' | 'md' | 'lg' | 'full';
	}
	let { class: className = 'h-4 w-full', rounded = 'sm' }: Props = $props();
	const R = { sm: 'rounded-sm', md: 'rounded-md', lg: 'rounded-lg', full: 'rounded-full' } as const;
</script>

<div class={`skeleton ${R[rounded]} ${className}`} aria-hidden="true"></div>

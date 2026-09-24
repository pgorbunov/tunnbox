<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import Spinner from './Spinner.svelte';

	interface Props extends HTMLButtonAttributes {
		/** Accessible name (rendered as aria-label and native tooltip). */
		label: string;
		size?: 'sm' | 'md';
		variant?: 'ghost' | 'outline' | 'danger';
		loading?: boolean;
		active?: boolean;
		children: Snippet;
	}

	let {
		label,
		size = 'md',
		variant = 'ghost',
		loading = false,
		active = false,
		class: className = '',
		disabled,
		type = 'button',
		children,
		...rest
	}: Props = $props();

	const VARIANTS = {
		ghost: 'text-fg-muted hover:text-fg hover:bg-bg-subtle border-transparent',
		outline: 'text-fg-muted hover:text-fg bg-surface border-border hover:border-border-strong',
		danger: 'text-danger hover:bg-danger-soft border-transparent'
	} as const;
</script>

<button
	{type}
	class={`inline-flex shrink-0 items-center justify-center rounded-sm border transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50
		${size === 'sm' ? 'h-8 w-8' : 'h-10 w-10'} ${VARIANTS[variant]} ${active ? 'bg-bg-subtle text-fg' : ''} ${className}`}
	aria-label={label}
	title={label}
	aria-pressed={active || undefined}
	disabled={disabled || loading}
	{...rest}
>
	{#if loading}
		<Spinner size={16} />
	{:else}
		{@render children()}
	{/if}
</button>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAnchorAttributes, HTMLButtonAttributes } from 'svelte/elements';
	import Spinner from './Spinner.svelte';

	export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-soft' | 'outline';
	export type ButtonSize = 'sm' | 'md' | 'lg';

	interface Props extends Omit<HTMLButtonAttributes, 'type'> {
		variant?: ButtonVariant;
		size?: ButtonSize;
		loading?: boolean;
		block?: boolean;
		type?: 'button' | 'submit' | 'reset';
		href?: string;
		target?: HTMLAnchorAttributes['target'];
		children: Snippet;
	}

	let {
		variant = 'secondary',
		size = 'md',
		loading = false,
		block = false,
		type = 'button',
		href,
		target,
		disabled,
		class: className = '',
		children,
		...rest
	}: Props = $props();

	const VARIANTS: Record<ButtonVariant, string> = {
		primary: 'bg-accent text-accent-fg hover:bg-accent-hover border-transparent shadow-sm font-semibold',
		secondary: 'bg-surface text-fg border-border hover:bg-bg-subtle hover:border-border-strong shadow-sm',
		outline: 'bg-transparent text-fg border-border-strong hover:bg-bg-subtle',
		ghost: 'bg-transparent text-fg-muted border-transparent hover:bg-bg-subtle hover:text-fg',
		danger: 'bg-danger text-white border-transparent hover:opacity-90 shadow-sm font-semibold',
		'danger-soft': 'bg-danger-soft text-danger border-transparent hover:opacity-90'
	};
	const SIZES: Record<ButtonSize, string> = {
		sm: 'h-8 px-2.5 text-[13px] gap-1.5 rounded-sm',
		md: 'h-10 px-3.5 text-sm gap-2 rounded-md',
		lg: 'h-11 px-5 text-base gap-2 rounded-md'
	};

	const classes = $derived(
		[
			'inline-flex items-center justify-center whitespace-nowrap border font-medium select-none transition-colors duration-150',
			'disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2',
			VARIANTS[variant],
			SIZES[size],
			block ? 'w-full' : '',
			className
		].join(' ')
	);
</script>

{#if href}
	<a
		{href}
		{target}
		rel={target === '_blank' ? 'noopener noreferrer' : undefined}
		class={classes}
		aria-disabled={disabled || undefined}
	>
		{@render children()}
	</a>
{:else}
	<button {type} class={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
		{#if loading}
			<Spinner size={size === 'sm' ? 14 : 16} />
		{/if}
		{@render children()}
	</button>
{/if}

<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';
	import { uid } from '$lib/utils/dom';

	interface Props extends Omit<HTMLInputAttributes, 'value' | 'size'> {
		value?: string;
		label?: string;
		hint?: string;
		error?: string | null;
		mono?: boolean;
		size?: 'sm' | 'md';
		/** Optional leading/trailing adornments. */
		leading?: Snippet;
		trailing?: Snippet;
		/** Visually hide the label (still announced). */
		hideLabel?: boolean;
		ref?: HTMLInputElement | null;
	}

	let {
		value = $bindable(''),
		label,
		hint,
		error = null,
		mono = false,
		size = 'md',
		leading,
		trailing,
		hideLabel = false,
		id = uid('input'),
		class: className = '',
		ref = $bindable(null),
		...rest
	}: Props = $props();

	const hintId = `${id}-hint`;
	const errorId = `${id}-error`;
</script>

<div class={`flex flex-col gap-1.5 ${className}`}>
	{#if label}
		<label for={id} class={`text-sm font-medium text-fg ${hideLabel ? 'sr-only' : ''}`}>{label}</label>
	{/if}
	<div class="relative flex items-center">
		{#if leading}
			<span class="pointer-events-none absolute left-3 flex items-center text-fg-subtle">{@render leading()}</span>
		{/if}
		<input
			{id}
			bind:value
			bind:this={ref}
			class={`w-full rounded-md border bg-surface text-fg placeholder:text-fg-subtle shadow-sm transition-colors duration-150
				${size === 'sm' ? 'h-9 text-[13px]' : 'h-10 text-sm'}
				${leading ? 'pl-9' : 'pl-3'} ${trailing ? 'pr-10' : 'pr-3'}
				${mono ? 'font-mono' : ''}
				${error ? 'border-danger focus-visible:outline-danger' : 'border-border hover:border-border-strong'}
				disabled:opacity-60 disabled:bg-bg-subtle read-only:bg-bg-subtle`}
			aria-invalid={error ? true : undefined}
			aria-describedby={error ? errorId : hint ? hintId : undefined}
			{...rest}
		/>
		{#if trailing}
			<span class="absolute right-2 flex items-center">{@render trailing()}</span>
		{/if}
	</div>
	{#if error}
		<p id={errorId} class="text-[13px] text-danger" role="alert">{error}</p>
	{:else if hint}
		<p id={hintId} class="text-[13px] text-fg-subtle">{hint}</p>
	{/if}
</div>

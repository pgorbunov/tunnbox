<script lang="ts">
	import type { HTMLSelectAttributes } from 'svelte/elements';
	import { ChevronDown } from 'lucide-svelte';
	import { uid } from '$lib/utils/dom';

	export interface SelectOption {
		value: string;
		label: string;
		disabled?: boolean;
	}

	interface Props extends Omit<HTMLSelectAttributes, 'value' | 'size'> {
		value?: string;
		options: SelectOption[];
		label?: string;
		hint?: string;
		error?: string | null;
		size?: 'sm' | 'md';
		hideLabel?: boolean;
		placeholder?: string;
	}

	let {
		value = $bindable(''),
		options,
		label,
		hint,
		error = null,
		size = 'md',
		hideLabel = false,
		placeholder,
		id = uid('select'),
		class: className = '',
		...rest
	}: Props = $props();

	const hintId = $derived(`${id}-hint`);
	const errorId = $derived(`${id}-error`);
</script>

<div class={`flex flex-col gap-1.5 ${className}`}>
	{#if label}
		<label for={id} class={`text-sm font-medium text-fg ${hideLabel ? 'sr-only' : ''}`}>{label}</label>
	{/if}
	<div class="relative">
		<select
			{id}
			bind:value
			class={`w-full appearance-none rounded-md border bg-surface pl-3 pr-9 text-fg shadow-sm transition-colors duration-150
				${size === 'sm' ? 'h-9 text-[13px]' : 'h-10 text-sm'}
				${error ? 'border-danger' : 'border-border hover:border-border-strong'}
				disabled:opacity-60 disabled:bg-bg-subtle`}
			aria-invalid={error ? true : undefined}
			aria-describedby={error ? errorId : hint ? hintId : undefined}
			{...rest}
		>
			{#if placeholder}
				<option value="" disabled>{placeholder}</option>
			{/if}
			{#each options as opt (opt.value)}
				<option value={opt.value} disabled={opt.disabled}>{opt.label}</option>
			{/each}
		</select>
		<ChevronDown class="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" aria-hidden="true" />
	</div>
	{#if error}
		<p id={errorId} class="text-[13px] text-danger" role="alert">{error}</p>
	{:else if hint}
		<p id={hintId} class="text-[13px] text-fg-subtle">{hint}</p>
	{/if}
</div>

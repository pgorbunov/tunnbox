<script lang="ts">
	import type { HTMLTextareaAttributes } from 'svelte/elements';
	import { uid } from '$lib/utils/dom';

	interface Props extends Omit<HTMLTextareaAttributes, 'value'> {
		value?: string;
		label?: string;
		hint?: string;
		error?: string | null;
		mono?: boolean;
	}

	let {
		value = $bindable(''),
		label,
		hint,
		error = null,
		mono = false,
		id = uid('textarea'),
		rows = 3,
		class: className = '',
		...rest
	}: Props = $props();

	const hintId = $derived(`${id}-hint`);
	const errorId = $derived(`${id}-error`);
</script>

<div class={`flex flex-col gap-1.5 ${className}`}>
	{#if label}
		<label for={id} class="text-sm font-medium text-fg">{label}</label>
	{/if}
	<textarea
		{id}
		{rows}
		bind:value
		class={`w-full rounded-md border bg-surface px-3 py-2 text-sm text-fg placeholder:text-fg-subtle shadow-sm transition-colors duration-150 resize-y
			${mono ? 'font-mono text-[13px]' : ''}
			${error ? 'border-danger focus-visible:outline-danger' : 'border-border hover:border-border-strong'}
			disabled:opacity-60 disabled:bg-bg-subtle`}
		aria-invalid={error ? true : undefined}
		aria-describedby={error ? errorId : hint ? hintId : undefined}
		{...rest}
	></textarea>
	{#if error}
		<p id={errorId} class="text-[13px] text-danger" role="alert">{error}</p>
	{:else if hint}
		<p id={hintId} class="text-[13px] text-fg-subtle">{hint}</p>
	{/if}
</div>

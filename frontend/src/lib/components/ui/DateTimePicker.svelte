<script lang="ts">
	/**
	 * Native datetime-local wrapper. `value` is an ISO UTC string (or '' for none);
	 * the input displays and edits in the user's local time.
	 */
	import { fromDatetimeLocal, toDatetimeLocal } from '$lib/utils/format';
	import { uid } from '$lib/utils/dom';

	interface Props {
		value: string;
		label?: string;
		hint?: string;
		error?: string | null;
		min?: string;
		id?: string;
		disabled?: boolean;
		required?: boolean;
	}

	let {
		value = $bindable(''),
		label,
		hint,
		error = null,
		min,
		id = uid('dt'),
		disabled = false,
		required = false
	}: Props = $props();

	let local = $state(toDatetimeLocal(value));

	$effect(() => {
		const next = toDatetimeLocal(value);
		if (next !== local && fromDatetimeLocal(local) !== value) local = next;
	});

	function oninput(e: Event) {
		local = (e.currentTarget as HTMLInputElement).value;
		value = fromDatetimeLocal(local) ?? '';
	}

	const hintId = $derived(`${id}-hint`);
	const errorId = $derived(`${id}-error`);
</script>

<div class="flex flex-col gap-1.5">
	{#if label}
		<label for={id} class="text-sm font-medium text-fg">{label}</label>
	{/if}
	<input
		{id}
		type="datetime-local"
		value={local}
		{oninput}
		min={min ? toDatetimeLocal(min) : undefined}
		{disabled}
		{required}
		class={`h-10 w-full rounded-md border bg-surface px-3 text-sm text-fg shadow-sm transition-colors
			${error ? 'border-danger' : 'border-border hover:border-border-strong'} disabled:opacity-60`}
		aria-invalid={error ? true : undefined}
		aria-describedby={error ? errorId : hint ? hintId : undefined}
	/>
	{#if error}
		<p id={errorId} class="text-[13px] text-danger" role="alert">{error}</p>
	{:else if hint}
		<p id={hintId} class="text-[13px] text-fg-subtle">{hint}</p>
	{/if}
</div>

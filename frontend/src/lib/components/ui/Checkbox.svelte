<script lang="ts">
	import { Check, Minus } from 'lucide-svelte';
	import { uid } from '$lib/utils/dom';

	interface Props {
		checked: boolean;
		indeterminate?: boolean;
		label?: string;
		description?: string;
		disabled?: boolean;
		id?: string;
		/** Accessible name when no visible label. */
		ariaLabel?: string;
		onchange?: (checked: boolean) => void;
	}

	let {
		checked = $bindable(false),
		indeterminate = false,
		label,
		description,
		disabled = false,
		id = uid('checkbox'),
		ariaLabel,
		onchange
	}: Props = $props();
</script>

<label for={id} class={`inline-flex items-start gap-2.5 ${disabled ? 'opacity-50' : 'cursor-pointer'}`}>
	<span class="relative mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center">
		<input
			{id}
			type="checkbox"
			bind:checked
			{indeterminate}
			{disabled}
			aria-label={ariaLabel}
			onchange={() => onchange?.(checked)}
			class="peer absolute inset-0 h-5 w-5 cursor-pointer appearance-none rounded-sm border border-border-strong bg-surface transition-colors checked:border-accent checked:bg-accent indeterminate:border-accent indeterminate:bg-accent disabled:cursor-not-allowed"
		/>
		<span class="pointer-events-none relative hidden text-accent-fg peer-checked:block" aria-hidden="true">
			<Check class="h-3.5 w-3.5" strokeWidth={3} />
		</span>
		<span
			class="pointer-events-none relative hidden text-accent-fg peer-indeterminate:block"
			aria-hidden="true"
		>
			<Minus class="h-3.5 w-3.5" strokeWidth={3} />
		</span>
	</span>
	{#if label}
		<span class="min-w-0">
			<span class="block text-sm font-medium text-fg">{label}</span>
			{#if description}
				<span class="block text-[13px] text-fg-subtle">{description}</span>
			{/if}
		</span>
	{/if}
</label>

<script lang="ts">
	import { uid } from '$lib/utils/dom';

	interface Props {
		checked: boolean;
		label: string;
		/** Hide the visible label (still used for aria). */
		hideLabel?: boolean;
		description?: string;
		disabled?: boolean;
		loading?: boolean;
		size?: 'sm' | 'md';
		id?: string;
		onchange?: (checked: boolean) => void;
	}

	let {
		checked = $bindable(false),
		label,
		hideLabel = false,
		description,
		disabled = false,
		loading = false,
		size = 'md',
		id = uid('switch'),
		onchange
	}: Props = $props();

	function toggle() {
		if (disabled || loading) return;
		checked = !checked;
		onchange?.(checked);
	}

	const dims = $derived(size === 'sm' ? { track: 'h-5 w-9', knob: 'h-4 w-4', shift: 'translate-x-4' } : { track: 'h-6 w-11', knob: 'h-5 w-5', shift: 'translate-x-5' });
</script>

<div class="flex items-start gap-3">
	<button
		{id}
		type="button"
		role="switch"
		aria-checked={checked}
		aria-label={hideLabel ? label : undefined}
		aria-labelledby={hideLabel ? undefined : `${id}-label`}
		aria-busy={loading || undefined}
		disabled={disabled || loading}
		onclick={toggle}
		class={`relative inline-flex shrink-0 items-center rounded-full border-2 border-transparent transition-colors duration-200 disabled:opacity-50
			${dims.track} ${checked ? 'bg-accent' : 'bg-border-strong'}`}
	>
		<span
			class={`pointer-events-none inline-block rounded-full bg-white shadow-sm transition-transform duration-200 ${dims.knob} ${checked ? dims.shift : 'translate-x-0'}`}
			aria-hidden="true"
		></span>
	</button>
	{#if !hideLabel}
		<div class="min-w-0">
			<label id={`${id}-label`} for={id} class="block cursor-pointer text-sm font-medium text-fg">{label}</label>
			{#if description}
				<p class="text-[13px] text-fg-subtle">{description}</p>
			{/if}
		</div>
	{/if}
</div>

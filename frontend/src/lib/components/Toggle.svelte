<script lang="ts">
	interface Props {
		checked: boolean;
		disabled?: boolean;
		loading?: boolean;
		onchange?: (checked: boolean) => void;
	}

	let { checked = $bindable(), disabled = false, loading = false, onchange }: Props = $props();

	function handleClick(event: MouseEvent) {
		event.preventDefault();
		event.stopPropagation();
		if (disabled || loading) return;
		checked = !checked;
		onchange?.(checked);
	}
</script>

<button
	type="button"
	role="switch"
	aria-checked={checked}
	class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-slate-900
		{checked ? 'bg-emerald-600' : 'bg-slate-400 dark:bg-slate-600'}
		{disabled || loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}"
	{disabled}
	onclick={handleClick}
>
	<span
		class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200
			{checked ? 'translate-x-6' : 'translate-x-1'}"
	>
		{#if loading}
			<svg
				class="h-4 w-4 animate-spin text-slate-400"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
			>
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
				></circle>
				<path
					class="opacity-75"
					fill="currentColor"
					d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
				></path>
			</svg>
		{/if}
	</span>
</button>

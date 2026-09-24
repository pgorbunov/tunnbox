<script lang="ts">
	import { AlertTriangle, RefreshCw } from 'lucide-svelte';
	import Button from './Button.svelte';

	interface Props {
		title?: string;
		message: string;
		onretry?: () => void;
		retrying?: boolean;
		compact?: boolean;
	}

	let {
		title = 'Something went wrong',
		message,
		onretry,
		retrying = false,
		compact = false
	}: Props = $props();
</script>

<div
	class={`flex flex-col items-center justify-center text-center ${compact ? 'px-4 py-8' : 'px-6 py-14'}`}
	role="alert"
>
	<div
		class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-danger-soft text-danger"
		aria-hidden="true"
	>
		<AlertTriangle class="h-6 w-6" />
	</div>
	<h3 class="text-base font-semibold text-fg">{title}</h3>
	<p class="mt-1 max-w-sm text-sm text-fg-muted">{message}</p>
	{#if onretry}
		<div class="mt-5">
			<Button variant="secondary" onclick={onretry} loading={retrying}>
				<RefreshCw class="h-4 w-4" aria-hidden="true" />
				Try again
			</Button>
		</div>
	{/if}
</div>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-svelte';

	export type AlertTone = 'info' | 'success' | 'warning' | 'danger';

	interface Props {
		tone?: AlertTone;
		title?: string;
		class?: string;
		children?: Snippet;
		actions?: Snippet;
	}

	let { tone = 'info', title, class: className = '', children, actions }: Props = $props();

	const TONES: Record<AlertTone, { box: string; icon: typeof Info }> = {
		info: { box: 'bg-info-soft text-fg border-info/30', icon: Info },
		success: { box: 'bg-success-soft text-fg border-success/30', icon: CheckCircle2 },
		warning: { box: 'bg-warning-soft text-fg border-warning/30', icon: AlertTriangle },
		danger: { box: 'bg-danger-soft text-fg border-danger/30', icon: XCircle }
	};
	const ICON_COLOR: Record<AlertTone, string> = {
		info: 'text-info',
		success: 'text-success',
		warning: 'text-warning',
		danger: 'text-danger'
	};
	const Icon = $derived(TONES[tone].icon);
</script>

<div
	class={`flex gap-3 rounded-md border px-3.5 py-3 text-sm ${TONES[tone].box} ${className}`}
	role={tone === 'danger' ? 'alert' : 'status'}
>
	<Icon class={`mt-0.5 h-4 w-4 shrink-0 ${ICON_COLOR[tone]}`} aria-hidden="true" />
	<div class="min-w-0 flex-1">
		{#if title}
			<p class="font-semibold">{title}</p>
		{/if}
		{#if children}
			<div class={`${title ? 'mt-0.5' : ''} text-fg-muted [&_a]:underline`}>{@render children()}</div>
		{/if}
		{#if actions}
			<div class="mt-2 flex gap-2">{@render actions()}</div>
		{/if}
	</div>
</div>

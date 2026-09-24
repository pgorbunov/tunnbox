<script lang="ts">
	import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-svelte';
	import { toast, type ToastKind } from '$lib/stores/toast.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';

	const ICONS: Record<ToastKind, typeof Info> = {
		success: CheckCircle2,
		error: XCircle,
		info: Info,
		warning: AlertTriangle
	};
	const COLORS: Record<ToastKind, string> = {
		success: 'text-success',
		error: 'text-danger',
		info: 'text-info',
		warning: 'text-warning'
	};
</script>

<div
	class="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
	aria-live="polite"
	aria-relevant="additions"
	role="region"
	aria-label="Notifications"
>
	{#each toast.items as item (item.id)}
		{@const Icon = ICONS[item.kind]}
		<div
			class="anim-slide-up pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-md border border-border bg-surface-raised p-3 pr-2 shadow-lg"
			role={item.kind === 'error' ? 'alert' : 'status'}
			onpointerenter={() => toast.pause(item.id)}
			onpointerleave={() => toast.resume(item.id)}
		>
			<Icon class={`mt-0.5 h-5 w-5 shrink-0 ${COLORS[item.kind]}`} aria-hidden="true" />
			<div class="min-w-0 flex-1 text-sm">
				<p class="font-medium text-fg">{item.title}</p>
				{#if item.description}
					<p class="mt-0.5 break-words text-fg-muted">{item.description}</p>
				{/if}
				{#if item.action}
					<button
						type="button"
						class="mt-1.5 text-[13px] font-semibold text-accent hover:underline"
						onclick={() => {
							item.action?.onClick();
							toast.dismiss(item.id);
						}}
					>
						{item.action.label}
					</button>
				{/if}
			</div>
			<IconButton label="Dismiss" size="sm" onclick={() => toast.dismiss(item.id)}>
				<X class="h-4 w-4" />
			</IconButton>
		</div>
	{/each}
</div>

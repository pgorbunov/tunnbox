<script lang="ts">
	/** Side sheet (right on desktop, full-width on mobile) built on native <dialog>. */
	import type { Snippet } from 'svelte';
	import { X } from 'lucide-svelte';
	import { uid } from '$lib/utils/dom';
	import IconButton from './IconButton.svelte';

	interface Props {
		open: boolean;
		title: string;
		description?: string;
		side?: 'right' | 'left';
		width?: 'md' | 'lg';
		onclose?: () => void;
		children: Snippet;
		/** Rendered in the header next to the close button. */
		actions?: Snippet;
		footer?: Snippet;
	}

	let {
		open = $bindable(false),
		title,
		description,
		side = 'right',
		width = 'md',
		onclose,
		children,
		actions,
		footer
	}: Props = $props();

	const id = uid('drawer');
	let el: HTMLDialogElement | null = $state(null);
	let panel: HTMLDivElement | null = $state(null);

	$effect(() => {
		if (!el) return;
		if (open && !el.open) {
			el.showModal();
			document.body.style.overflow = 'hidden';
			requestAnimationFrame(() => panel?.focus());
		} else if (!open && el.open) {
			el.close();
		}
	});

	$effect(() => () => {
		document.body.style.overflow = '';
	});

	function handleNativeClose() {
		document.body.style.overflow = '';
		if (open) open = false;
		onclose?.();
	}
	function handleCancel(e: Event) {
		e.preventDefault();
		open = false;
	}
</script>

<dialog
	bind:this={el}
	onclose={handleNativeClose}
	oncancel={handleCancel}
	aria-labelledby={`${id}-title`}
	class="m-0 h-full max-h-none w-full max-w-none bg-transparent p-0 text-fg backdrop:bg-transparent"
>
	{#if open}
		<div class={`fixed inset-0 flex ${side === 'right' ? 'justify-end' : 'justify-start'}`}>
			<button
				type="button"
				class="anim-fade-in absolute inset-0 cursor-default bg-surface-overlay backdrop-blur-[2px]"
				aria-label="Close panel"
				tabindex="-1"
				onclick={() => (open = false)}
			></button>
			<div
				bind:this={panel}
				tabindex="-1"
				class={`relative flex h-full w-full flex-col bg-surface shadow-lg outline-none
					${side === 'right' ? 'anim-slide-in-right border-l' : 'anim-slide-in-left border-r'} border-border
					${width === 'lg' ? 'sm:max-w-2xl' : 'sm:max-w-xl'}`}
			>
				<header class="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
					<div class="min-w-0">
						<h2 id={`${id}-title`} class="truncate text-base font-semibold text-fg">{title}</h2>
						{#if description}
							<p class="mt-0.5 truncate text-sm text-fg-muted">{description}</p>
						{/if}
					</div>
					<div class="flex shrink-0 items-center gap-1">
						{#if actions}
							{@render actions()}
						{/if}
						<IconButton label="Close" size="sm" onclick={() => (open = false)}>
							<X class="h-4 w-4" />
						</IconButton>
					</div>
				</header>
				<div class="min-h-0 flex-1 overflow-y-auto px-5 py-4 scrollbar-thin">
					{@render children()}
				</div>
				{#if footer}
					<footer
						class="flex flex-wrap items-center justify-end gap-2 border-t border-border bg-bg-subtle/60 px-5 py-3"
					>
						{@render footer()}
					</footer>
				{/if}
			</div>
		</div>
	{/if}
</dialog>

<script lang="ts">
	/**
	 * Modal dialog built on the native <dialog> element: focus trap, Escape and
	 * focus restoration come from the platform. Backdrop click closes.
	 */
	import type { Snippet } from 'svelte';
	import { X } from 'lucide-svelte';
	import { focusFirst, uid } from '$lib/utils/dom';
	import IconButton from './IconButton.svelte';

	interface Props {
		open: boolean;
		title: string;
		description?: string;
		size?: 'sm' | 'md' | 'lg' | 'xl';
		/** Prevent closing via backdrop/Escape (e.g. while submitting). */
		locked?: boolean;
		hideTitle?: boolean;
		onclose?: () => void;
		children: Snippet;
		footer?: Snippet;
		/** Extra header content (e.g. tabs) rendered under the title. */
		header?: Snippet;
	}

	let {
		open = $bindable(false),
		title,
		description,
		size = 'md',
		locked = false,
		hideTitle = false,
		onclose,
		children,
		footer,
		header
	}: Props = $props();

	const id = uid('dialog');
	let el: HTMLDialogElement | null = $state(null);
	let body: HTMLDivElement | null = $state(null);

	const SIZES = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' } as const;

	$effect(() => {
		if (!el) return;
		if (open && !el.open) {
			el.showModal();
			document.body.style.overflow = 'hidden';
			requestAnimationFrame(() => {
				if (body) focusFirst(body);
			});
		} else if (!open && el.open) {
			el.close();
		}
	});

	$effect(() => () => {
		document.body.style.overflow = '';
	});

	function requestClose() {
		if (locked) return;
		open = false;
	}

	function handleNativeClose() {
		document.body.style.overflow = '';
		if (open) open = false;
		onclose?.();
	}

	function handleCancel(e: Event) {
		e.preventDefault();
		requestClose();
	}
</script>

<dialog
	bind:this={el}
	onclose={handleNativeClose}
	oncancel={handleCancel}
	aria-labelledby={`${id}-title`}
	aria-describedby={description ? `${id}-desc` : undefined}
	class="m-0 h-full max-h-none w-full max-w-none bg-transparent p-0 text-fg backdrop:bg-transparent"
>
	{#if open}
		<div class="fixed inset-0 flex items-end justify-center p-0 sm:items-center sm:p-6">
			<button
				type="button"
				class="anim-fade-in absolute inset-0 cursor-default bg-surface-overlay backdrop-blur-[2px]"
				aria-label="Close dialog"
				tabindex="-1"
				onclick={requestClose}
			></button>
			<div
				class={`anim-pop-in relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-lg border border-border bg-surface shadow-lg sm:rounded-lg ${SIZES[size]}`}
			>
				<header
					class={`flex items-start justify-between gap-4 px-5 pt-5 ${header ? 'pb-0' : 'pb-3'} ${hideTitle ? 'sr-only' : ''}`}
				>
					<div class="min-w-0">
						<h2 id={`${id}-title`} class="text-base font-semibold text-fg">{title}</h2>
						{#if description}
							<p id={`${id}-desc`} class="mt-1 text-sm text-fg-muted">{description}</p>
						{/if}
					</div>
					{#if !locked}
						<IconButton label="Close" size="sm" onclick={requestClose} class="-mt-1 -mr-2">
							<X class="h-4 w-4" />
						</IconButton>
					{/if}
				</header>
				{#if header}
					<div class="px-5 pt-3">{@render header()}</div>
				{/if}
				<div bind:this={body} class="min-h-0 flex-1 overflow-y-auto px-5 py-4 scrollbar-thin" tabindex="-1">
					{@render children()}
				</div>
				{#if footer}
					<footer
						class="flex flex-col-reverse gap-2 border-t border-border bg-bg-subtle/60 px-5 py-3 sm:flex-row sm:justify-end"
					>
						{@render footer()}
					</footer>
				{/if}
			</div>
		</div>
	{/if}
</dialog>

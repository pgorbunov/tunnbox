<script module lang="ts">
	import type { IconComponent } from '$lib/utils/icons';

	export interface MenuItem {
		label: string;
		icon?: IconComponent;
		onselect?: () => void;
		href?: string;
		danger?: boolean;
		disabled?: boolean;
		/** Renders a divider above this item. */
		separator?: boolean;
		hidden?: boolean;
	}
</script>

<script lang="ts">
	/** Accessible action menu: trigger snippet + item list. Arrow keys, Home/End, Escape. */
	import type { Snippet } from 'svelte';
	import { clickOutside, uid } from '$lib/utils/dom';

	interface Props {
		items: MenuItem[];
		label: string;
		align?: 'left' | 'right';
		/** Receives { open, toggle, props } to spread on the trigger button. */
		trigger: Snippet<[{ open: boolean; toggle: () => void; props: Record<string, unknown> }]>;
		class?: string;
	}

	let { items, label, align = 'right', trigger, class: className = '' }: Props = $props();

	const id = uid('menu');
	let open = $state(false);
	let activeIndex = $state(-1);
	let menuEl: HTMLDivElement | null = $state(null);
	let root: HTMLDivElement | null = $state(null);

	const visible = $derived(items.filter((i) => !i.hidden));

	function toggle() {
		open = !open;
		if (open) {
			activeIndex = visible.findIndex((i) => !i.disabled);
			requestAnimationFrame(() => focusItem(activeIndex));
		}
	}

	function close(restoreFocus = true) {
		if (!open) return;
		open = false;
		activeIndex = -1;
		if (restoreFocus) root?.querySelector<HTMLElement>('[aria-haspopup]')?.focus();
	}

	function focusItem(i: number) {
		const el = menuEl?.querySelectorAll<HTMLElement>('[role="menuitem"]')[i];
		el?.focus();
	}

	function move(delta: number) {
		if (!visible.length) return;
		let i = activeIndex;
		for (let n = 0; n < visible.length; n++) {
			i = (i + delta + visible.length) % visible.length;
			if (!visible[i].disabled) break;
		}
		activeIndex = i;
		focusItem(i);
	}

	function onkeydown(e: KeyboardEvent) {
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				if (!open) toggle();
				else move(1);
				break;
			case 'ArrowUp':
				e.preventDefault();
				if (open) move(-1);
				break;
			case 'Home':
				if (open) {
					e.preventDefault();
					activeIndex = -1;
					move(1);
				}
				break;
			case 'End':
				if (open) {
					e.preventDefault();
					activeIndex = 0;
					move(-1);
				}
				break;
			case 'Escape':
				if (open) {
					e.preventDefault();
					e.stopPropagation();
					close();
				}
				break;
			case 'Tab':
				close(false);
				break;
		}
	}

	function select(item: MenuItem) {
		if (item.disabled) return;
		close(false);
		item.onselect?.();
	}

	const triggerProps = $derived({
		'aria-haspopup': 'menu',
		'aria-expanded': open,
		'aria-controls': id
	});
</script>

<div bind:this={root} class={`relative inline-flex ${className}`} use:clickOutside={() => close(false)} onkeydown={onkeydown} role="presentation">
	{@render trigger({ open, toggle, props: triggerProps })}
	{#if open}
		<div
			bind:this={menuEl}
			{id}
			role="menu"
			aria-label={label}
			class={`anim-pop-in absolute top-full z-40 mt-1 min-w-[11rem] overflow-hidden rounded-md border border-border bg-surface-raised py-1 shadow-lg ${align === 'right' ? 'right-0' : 'left-0'}`}
		>
			{#each visible as item, i (item.label)}
				{#if item.separator && i > 0}
					<div class="my-1 h-px bg-border" role="separator"></div>
				{/if}
				{#if item.href}
					<a
						role="menuitem"
						href={item.href}
						tabindex={activeIndex === i ? 0 : -1}
						onclick={() => close(false)}
						class="flex h-9 w-full items-center gap-2.5 px-3 text-sm text-fg hover:bg-bg-subtle focus-visible:bg-bg-subtle focus-visible:outline-none"
					>
						{#if item.icon}
							{@const Icon = item.icon}
							<Icon class="h-4 w-4 text-fg-subtle" />
						{/if}
						{item.label}
					</a>
				{:else}
					<button
						type="button"
						role="menuitem"
						tabindex={activeIndex === i ? 0 : -1}
						disabled={item.disabled}
						onclick={() => select(item)}
						class={`flex h-9 w-full items-center gap-2.5 px-3 text-left text-sm focus-visible:outline-none disabled:opacity-50
							${item.danger ? 'text-danger hover:bg-danger-soft focus-visible:bg-danger-soft' : 'text-fg hover:bg-bg-subtle focus-visible:bg-bg-subtle'}`}
					>
						{#if item.icon}
							{@const Icon = item.icon}
							<Icon class={`h-4 w-4 ${item.danger ? 'text-danger' : 'text-fg-subtle'}`} />
						{/if}
						{item.label}
					</button>
				{/if}
			{/each}
		</div>
	{/if}
</div>

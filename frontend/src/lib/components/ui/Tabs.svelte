<script module lang="ts">
	import type { IconComponent } from '$lib/utils/icons';

	export interface TabItem<V extends string> {
		id: V;
		label: string;
		count?: number | null;
		icon?: IconComponent;
		hidden?: boolean;
	}
</script>

<script lang="ts" generics="T extends string">
	/**
	 * Tab strip (WAI-ARIA tabs pattern). The parent renders the panel with
	 * `role="tabpanel"`, `id="{idPrefix}-panel-{value}"` and `aria-labelledby="{idPrefix}-{value}"`.
	 */

	interface Props {
		tabs: TabItem<T>[];
		value: T;
		label: string;
		idPrefix?: string;
		variant?: 'underline' | 'pills';
		onchange?: (value: T) => void;
	}

	let { tabs, value = $bindable(), label, idPrefix = 'tab', variant = 'underline', onchange }: Props = $props();

	const visible = $derived(tabs.filter((t) => !t.hidden));
	let buttons: (HTMLButtonElement | null)[] = $state([]);

	function select(v: T) {
		if (v === value) return;
		value = v;
		onchange?.(v);
	}

	function onkeydown(e: KeyboardEvent, i: number) {
		const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
		if (!keys.includes(e.key)) return;
		e.preventDefault();
		let next = i;
		if (e.key === 'ArrowLeft') next = (i - 1 + visible.length) % visible.length;
		if (e.key === 'ArrowRight') next = (i + 1) % visible.length;
		if (e.key === 'Home') next = 0;
		if (e.key === 'End') next = visible.length - 1;
		select(visible[next].id);
		buttons[next]?.focus();
	}
</script>

<div
	role="tablist"
	aria-label={label}
	class={`scrollbar-thin flex overflow-x-auto ${variant === 'underline' ? 'gap-1 border-b border-border' : 'gap-1 rounded-md bg-bg-subtle p-1'}`}
>
	{#each visible as tab, i (tab.id)}
		{@const active = tab.id === value}
		<button
			type="button"
			role="tab"
			id={`${idPrefix}-${tab.id}`}
			aria-selected={active}
			aria-controls={`${idPrefix}-panel-${tab.id}`}
			tabindex={active ? 0 : -1}
			bind:this={buttons[i]}
			onclick={() => select(tab.id)}
			onkeydown={(e) => onkeydown(e, i)}
			class={`inline-flex shrink-0 items-center gap-2 whitespace-nowrap text-sm font-medium transition-colors duration-150
				${
					variant === 'underline'
						? `-mb-px h-10 border-b-2 px-3 ${active ? 'border-accent text-fg' : 'border-transparent text-fg-muted hover:border-border-strong hover:text-fg'}`
						: `h-8 rounded-sm px-3 ${active ? 'bg-surface text-fg shadow-sm' : 'text-fg-muted hover:text-fg'}`
				}`}
		>
			{#if tab.icon}
				{@const Icon = tab.icon}
				<Icon class="h-4 w-4" />
			{/if}
			{tab.label}
			{#if tab.count !== undefined && tab.count !== null}
				<span class={`tabular rounded-full px-1.5 text-[11px] ${active ? 'bg-accent-soft text-accent' : 'bg-bg-subtle text-fg-subtle'}`}>{tab.count}</span>
			{/if}
		</button>
	{/each}
</div>

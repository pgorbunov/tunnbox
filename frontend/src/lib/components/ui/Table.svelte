<script module lang="ts">
	export interface Column {
		key: string;
		label: string;
		sortable?: boolean;
		align?: 'left' | 'right' | 'center';
		/** Tailwind classes for the cell (e.g. width, hidden lg:table-cell). */
		class?: string;
		/** Visually hide the header label (e.g. for an actions column). */
		srOnly?: boolean;
	}
</script>

<script lang="ts" generics="T, K extends string | number">
	/**
	 * Data table: sortable headers, sticky header, optional row selection, and a
	 * card layout below 768px when a `card` snippet is provided.
	 */
	import type { Snippet } from 'svelte';
	import type { SvelteSet } from 'svelte/reactivity';
	import { MediaQuery } from 'svelte/reactivity';
	import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-svelte';
	import Checkbox from './Checkbox.svelte';
	import Skeleton from './Skeleton.svelte';

	interface Props {
		columns: Column[];
		rows: T[];
		rowKey: (row: T) => K;
		cell: Snippet<[T, Column]>;
		card?: Snippet<[T]>;
		caption: string;
		sortKey?: string;
		sortOrder?: 'asc' | 'desc';
		onsort?: (key: string, order: 'asc' | 'desc') => void;
		selectable?: boolean;
		selected?: SvelteSet<K>;
		onrowclick?: (row: T) => void;
		rowLabel?: (row: T) => string;
		loading?: boolean;
		skeletonRows?: number;
		empty?: Snippet;
		dense?: boolean;
		/** Reduce opacity while a background refresh is in flight. */
		refreshing?: boolean;
	}

	let {
		columns,
		rows,
		rowKey,
		cell,
		card,
		caption,
		sortKey,
		sortOrder = 'asc',
		onsort,
		selectable = false,
		selected,
		onrowclick,
		rowLabel,
		loading = false,
		skeletonRows = 5,
		empty,
		dense = false,
		refreshing = false
	}: Props = $props();

	const desktop = new MediaQuery('(min-width: 768px)');
	const useCards = $derived(!!card && !desktop.current);

	const allSelected = $derived(selectable && rows.length > 0 && rows.every((r) => selected?.has(rowKey(r))));
	const someSelected = $derived(selectable && !allSelected && rows.some((r) => selected?.has(rowKey(r))));

	function toggleAll() {
		if (!selected) return;
		if (allSelected) rows.forEach((r) => selected.delete(rowKey(r)));
		else rows.forEach((r) => selected.add(rowKey(r)));
	}

	function toggleRow(row: T) {
		if (!selected) return;
		const k = rowKey(row);
		if (selected.has(k)) selected.delete(k);
		else selected.add(k);
	}

	function sortBy(col: Column) {
		if (!col.sortable) return;
		const order = sortKey === col.key && sortOrder === 'asc' ? 'desc' : 'asc';
		onsort?.(col.key, order);
	}

	function onRowKey(e: KeyboardEvent, row: T) {
		if (e.key === 'Enter' || e.key === ' ') {
			if (e.target !== e.currentTarget) return;
			e.preventDefault();
			onrowclick?.(row);
		}
	}

	/** Ignore clicks that originate from interactive controls inside the row. */
	function onRowClick(e: MouseEvent, row: T) {
		const target = e.target as HTMLElement | null;
		if (target?.closest('input, button, a, label, [role="menu"], [data-no-row-click]')) return;
		onrowclick?.(row);
	}

	const ALIGN = { left: 'text-left', right: 'text-right', center: 'text-center' } as const;
</script>

{#if loading && rows.length === 0}
	<div class="divide-y divide-border" aria-busy="true" aria-label="Loading">
		{#each Array(skeletonRows) as _, i (i)}
			<div class="flex items-center gap-4 px-4 py-3">
				<Skeleton class="h-2.5 w-2.5" rounded="full" />
				<Skeleton class="h-4 w-32" />
				<Skeleton class="hidden h-4 w-28 sm:block" />
				<Skeleton class="hidden h-4 w-20 md:block" />
				<Skeleton class="ml-auto h-4 w-16" />
			</div>
		{/each}
	</div>
{:else if rows.length === 0}
	{#if empty}
		{@render empty()}
	{/if}
{:else if useCards}
	<ul
		class={`divide-y divide-border transition-opacity ${refreshing ? 'opacity-70' : ''}`}
		aria-label={caption}
	>
		{#each rows as row (rowKey(row))}
			<li class={`flex gap-3 px-4 py-3 ${selected?.has(rowKey(row)) ? 'bg-accent-soft/40' : ''}`}>
				{#if selectable}
					<div class="pt-0.5">
						<Checkbox
							checked={selected?.has(rowKey(row)) ?? false}
							ariaLabel={`Select ${rowLabel?.(row) ?? 'row'}`}
							onchange={() => toggleRow(row)}
						/>
					</div>
				{/if}
				<div class="min-w-0 flex-1">
					{@render card!(row)}
				</div>
			</li>
		{/each}
	</ul>
{:else}
	<div class={`w-full overflow-x-auto transition-opacity scrollbar-thin ${refreshing ? 'opacity-70' : ''}`}>
		<table class="w-full border-collapse text-sm">
			<caption class="sr-only">{caption}</caption>
			<thead class="sticky top-0 z-10 bg-surface">
				<tr class="border-b border-border">
					{#if selectable}
						<th scope="col" class="w-10 px-4 py-2">
							<Checkbox
								checked={allSelected}
								indeterminate={someSelected}
								ariaLabel="Select all rows"
								onchange={toggleAll}
							/>
						</th>
					{/if}
					{#each columns as col (col.key)}
						<th
							scope="col"
							aria-sort={col.sortable && sortKey === col.key
								? sortOrder === 'asc'
									? 'ascending'
									: 'descending'
								: undefined}
							class={`px-4 py-2 text-xs font-semibold tracking-wide whitespace-nowrap text-fg-subtle uppercase ${ALIGN[col.align ?? 'left']} ${col.class ?? ''}`}
						>
							{#if col.sortable}
								<button
									type="button"
									onclick={() => sortBy(col)}
									class={`inline-flex items-center gap-1 rounded-sm hover:text-fg ${sortKey === col.key ? 'text-fg' : ''}`}
								>
									{col.label}
									{#if sortKey === col.key}
										{#if sortOrder === 'asc'}<ArrowUp
												class="h-3.5 w-3.5"
												aria-hidden="true"
											/>{:else}<ArrowDown class="h-3.5 w-3.5" aria-hidden="true" />{/if}
									{:else}
										<ChevronsUpDown class="h-3.5 w-3.5 opacity-50" aria-hidden="true" />
									{/if}
								</button>
							{:else if col.srOnly}
								<span class="sr-only">{col.label}</span>
							{:else}
								{col.label}
							{/if}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody class="divide-y divide-border">
				{#each rows as row (rowKey(row))}
					{@const isSelected = selected?.has(rowKey(row)) ?? false}
					<tr
						class={`group transition-colors ${onrowclick ? 'cursor-pointer hover:bg-bg-subtle/70 focus-visible:bg-bg-subtle/70 focus-visible:outline-none' : ''} ${isSelected ? 'bg-accent-soft/40' : ''}`}
						tabindex={onrowclick ? 0 : undefined}
						aria-label={onrowclick ? rowLabel?.(row) : undefined}
						onclick={onrowclick ? (e) => onRowClick(e, row) : undefined}
						onkeydown={onrowclick ? (e) => onRowKey(e, row) : undefined}
					>
						{#if selectable}
							<td class="w-10 px-4 py-2">
								<Checkbox
									checked={isSelected}
									ariaLabel={`Select ${rowLabel?.(row) ?? 'row'}`}
									onchange={() => toggleRow(row)}
								/>
							</td>
						{/if}
						{#each columns as col (col.key)}
							<td
								class={`${dense ? 'h-9 py-1' : 'h-10 py-1.5'} px-4 align-middle ${ALIGN[col.align ?? 'left']} ${col.class ?? ''}`}
							>
								{@render cell(row, col)}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

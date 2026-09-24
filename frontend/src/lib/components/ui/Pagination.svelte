<script lang="ts">
	import { ChevronLeft, ChevronRight } from 'lucide-svelte';
	import IconButton from './IconButton.svelte';
	import Select from './Select.svelte';

	interface Props {
		page: number;
		pageSize: number;
		total: number;
		pageSizes?: number[];
		onchange?: (page: number, pageSize: number) => void;
	}

	let { page = $bindable(1), pageSize = $bindable(25), total, pageSizes = [10, 25, 50, 100], onchange }: Props = $props();

	const pages = $derived(Math.max(1, Math.ceil(total / pageSize)));
	const from = $derived(total === 0 ? 0 : (page - 1) * pageSize + 1);
	const to = $derived(Math.min(total, page * pageSize));

	function go(p: number) {
		page = Math.min(pages, Math.max(1, p));
		onchange?.(page, pageSize);
	}
	function changeSize(v: string) {
		pageSize = Number(v);
		page = 1;
		onchange?.(page, pageSize);
	}
</script>

<nav class="flex flex-wrap items-center justify-between gap-3 text-sm text-fg-muted" aria-label="Pagination">
	<p class="tabular">
		{#if total === 0}
			No results
		{:else}
			Showing <span class="font-medium text-fg">{from}–{to}</span> of <span class="font-medium text-fg">{total.toLocaleString()}</span>
		{/if}
	</p>
	<div class="flex items-center gap-2">
		<Select
			size="sm"
			label="Rows per page"
			hideLabel
			value={String(pageSize)}
			options={pageSizes.map((n) => ({ value: String(n), label: `${n} / page` }))}
			onchange={(e) => changeSize((e.currentTarget as HTMLSelectElement).value)}
		/>
		<IconButton label="Previous page" variant="outline" size="sm" disabled={page <= 1} onclick={() => go(page - 1)}>
			<ChevronLeft class="h-4 w-4" />
		</IconButton>
		<span class="tabular text-fg">{page} / {pages}</span>
		<IconButton label="Next page" variant="outline" size="sm" disabled={page >= pages} onclick={() => go(page + 1)}>
			<ChevronRight class="h-4 w-4" />
		</IconButton>
	</div>
</nav>

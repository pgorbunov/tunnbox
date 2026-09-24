<script lang="ts">
	/** Audit log: filters (action, username, text, date range), table, pagination, CSV export. */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ChevronDown, ChevronRight, Download, ScrollText, Search } from 'lucide-svelte';
	import { api, isAbortError, toApiError } from '$lib/api';
	import type { AuditEntry, AuditQuery } from '$lib/api/types';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatDateTime, fromDatetimeLocal, toDatetimeLocal } from '$lib/utils/format';
	import PageHeader from '$lib/components/app/PageHeader.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import Select from '$lib/components/ui/Select.svelte';
	import Table, { type Column } from '$lib/components/ui/Table.svelte';

	let actions = $state<string[]>([]);
	let action = $state('');
	let username = $state(page.url.searchParams.get('username') ?? '');
	let query = $state(page.url.searchParams.get('q') ?? '');
	let from = $state('');
	let to = $state('');
	let pageNo = $state(1);
	let pageSize = $state(25);

	let entries = $state<AuditEntry[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let exporting = $state(false);
	let expanded = $state<Set<number>>(new Set());
	let abort: AbortController | null = null;

	let debounced = $state({ username: username, q: query });
	let timer: ReturnType<typeof setTimeout> | null = null;
	$effect(() => {
		const u = username;
		const q = query;
		if (timer) clearTimeout(timer);
		timer = setTimeout(() => {
			debounced = { username: u.trim(), q: q.trim() };
			pageNo = 1;
		}, 300);
	});

	const filters = $derived<AuditQuery>({
		action: action || undefined,
		username: debounced.username || undefined,
		q: debounced.q || undefined,
		from: from || undefined,
		to: to || undefined
	});

	async function load() {
		abort?.abort();
		abort = new AbortController();
		const signal = abort.signal;
		loading = true;
		error = null;
		try {
			const res = await api.audit.list({ ...filters, page: pageNo, page_size: pageSize }, signal);
			if (signal.aborted) return;
			entries = res.items;
			total = res.total;
		} catch (err) {
			if (isAbortError(err)) return;
			error = toApiError(err).detail;
		} finally {
			if (!signal.aborted) loading = false;
		}
	}

	$effect(() => {
		void filters;
		void pageNo;
		void pageSize;
		void load();
	});

	$effect(() => {
		void api.audit
			.actions()
			.then((a) => (actions = a))
			.catch(() => (actions = []));
	});

	$effect(() => {
		const sp = new URLSearchParams();
		if (debounced.q) sp.set('q', debounced.q);
		if (debounced.username) sp.set('username', debounced.username);
		const s = sp.toString();
		const target = s ? `/audit?${s}` : '/audit';
		if (page.url.pathname + page.url.search !== target) void goto(target, { replaceState: true, noScroll: true, keepFocus: true });
	});

	async function exportCsv() {
		exporting = true;
		try {
			await api.audit.exportCsv(filters);
		} catch (err) {
			toast.error('Export failed', { description: toApiError(err).detail });
		} finally {
			exporting = false;
		}
	}

	function toggleExpanded(id: number) {
		const next = new Set(expanded);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		expanded = next;
	}

	function tone(a: string): 'neutral' | 'success' | 'warning' | 'danger' | 'info' {
		if (/failed|locked|deleted|revoked|disabled|down/.test(a)) return a.includes('failed') || a.includes('locked') || a.includes('deleted') ? 'danger' : 'warning';
		if (/created|enabled|up|login$|setup/.test(a)) return 'success';
		if (/updated|rotated|changed/.test(a)) return 'info';
		return 'neutral';
	}

	const columns: Column[] = [
		{ key: 'time', label: 'Time', class: 'w-44 whitespace-nowrap' },
		{ key: 'user', label: 'User', class: 'w-36' },
		{ key: 'action', label: 'Action' },
		{ key: 'target', label: 'Target', class: 'hidden lg:table-cell' },
		{ key: 'ip', label: 'IP', class: 'hidden xl:table-cell w-36' },
		{ key: 'details', label: 'Details', srOnly: true, align: 'right', class: 'w-12' }
	];

	const hasFilters = $derived(!!action || !!debounced.username || !!debounced.q || !!from || !!to);
	const actionOptions = $derived([{ value: '', label: 'All actions' }, ...actions.map((a) => ({ value: a, label: a }))]);
</script>

<svelte:head>
	<title>Audit log · TunnBox</title>
</svelte:head>

<PageHeader title="Audit log" description="Every change made through TunnBox, by whom and from where.">
	{#snippet actions()}
		<Button onclick={exportCsv} loading={exporting}>
			<Download class="h-4 w-4" aria-hidden="true" />
			Export CSV
		</Button>
	{/snippet}
	<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
		<Input label="Search" hideLabel bind:value={query} placeholder="Search target or details…" size="sm" data-hotkey-search type="search">
			{#snippet leading()}<Search class="h-4 w-4" />{/snippet}
		</Input>
		<Select label="Action" hideLabel size="sm" bind:value={action} options={actionOptions} onchange={() => (pageNo = 1)} />
		<Input label="Username" hideLabel bind:value={username} placeholder="Username" size="sm" autocomplete="off" />
		<div class="flex flex-col gap-1">
			<label for="audit-from" class="sr-only">From</label>
			<input id="audit-from" type="datetime-local" value={toDatetimeLocal(from)} oninput={(e) => { from = fromDatetimeLocal(e.currentTarget.value) ?? ''; pageNo = 1; }} class="h-9 w-full rounded-md border border-border bg-surface px-3 text-[13px] text-fg shadow-sm" aria-label="From date" />
		</div>
		<div class="flex flex-col gap-1">
			<label for="audit-to" class="sr-only">To</label>
			<input id="audit-to" type="datetime-local" value={toDatetimeLocal(to)} oninput={(e) => { to = fromDatetimeLocal(e.currentTarget.value) ?? ''; pageNo = 1; }} class="h-9 w-full rounded-md border border-border bg-surface px-3 text-[13px] text-fg shadow-sm" aria-label="To date" />
		</div>
	</div>
</PageHeader>

<Card flush>
	{#if error && entries.length === 0}
		<ErrorState message={error} onretry={load} />
	{:else}
		<Table {columns} rows={entries} rowKey={(e) => e.id} caption="Audit entries" {loading} refreshing={loading && entries.length > 0} skeletonRows={8} dense>
			{#snippet cell(e, col)}
				{#if col.key === 'time'}
					<span class="tabular text-[13px] text-fg-muted">{formatDateTime(e.created_at, { dateStyle: 'medium', timeStyle: 'medium' })}</span>
				{:else if col.key === 'user'}
					<span class="truncate font-medium text-fg">{e.username ?? 'system'}</span>
				{:else if col.key === 'action'}
					<Badge tone={tone(e.action)} size="sm"><span class="font-mono">{e.action}</span></Badge>
				{:else if col.key === 'target'}
					<span class="font-mono text-[13px] text-fg-muted">{e.target ?? '—'}</span>
				{:else if col.key === 'ip'}
					<span class="font-mono text-[13px] text-fg-subtle">{e.ip ?? '—'}</span>
				{:else if col.key === 'details'}
					{#if e.details && Object.keys(e.details).length}
						<button
							type="button"
							class="inline-flex h-8 w-8 items-center justify-center rounded-sm text-fg-subtle hover:bg-bg-subtle hover:text-fg"
							aria-expanded={expanded.has(e.id)}
							aria-label={expanded.has(e.id) ? 'Hide details' : 'Show details'}
							onclick={() => toggleExpanded(e.id)}
						>
							{#if expanded.has(e.id)}<ChevronDown class="h-4 w-4" />{:else}<ChevronRight class="h-4 w-4" />{/if}
						</button>
					{/if}
				{/if}
				{#if col.key === 'action' && expanded.has(e.id) && e.details}
					<pre class="mt-1.5 max-w-xl overflow-auto whitespace-pre-wrap break-all rounded-sm bg-bg-subtle p-2 font-mono text-[12px] text-fg-muted">{JSON.stringify(e.details, null, 2)}</pre>
				{/if}
			{/snippet}
			{#snippet card(e)}
				<div class="text-sm">
					<div class="flex flex-wrap items-center gap-2">
						<Badge tone={tone(e.action)} size="sm"><span class="font-mono">{e.action}</span></Badge>
						<span class="font-medium text-fg">{e.username ?? 'system'}</span>
					</div>
					<p class="mt-1 text-[12px] text-fg-subtle">{formatDateTime(e.created_at)}{#if e.ip} · {e.ip}{/if}</p>
					{#if e.target}<p class="mt-0.5 font-mono text-[12px] text-fg-muted">{e.target}</p>{/if}
					{#if e.details && Object.keys(e.details).length}
						<pre class="mt-1.5 overflow-auto whitespace-pre-wrap break-all rounded-sm bg-bg-subtle p-2 font-mono text-[11px] text-fg-muted">{JSON.stringify(e.details, null, 2)}</pre>
					{/if}
				</div>
			{/snippet}
			{#snippet empty()}
				{#if hasFilters}
					<EmptyState compact title="No entries match" description="Adjust the filters or widen the date range.">
						{#snippet actions()}
							<Button
								size="sm"
								onclick={() => {
									action = '';
									username = '';
									query = '';
									from = '';
									to = '';
								}}
							>
								Clear filters
							</Button>
						{/snippet}
					</EmptyState>
				{:else}
					<EmptyState title="No audit entries yet" description="Actions like sign-ins and configuration changes are recorded here.">
						{#snippet icon()}<ScrollText class="h-6 w-6" />{/snippet}
					</EmptyState>
				{/if}
			{/snippet}
		</Table>
		{#if total > 0}
			<div class="border-t border-border px-4 py-3">
				<Pagination bind:page={pageNo} bind:pageSize {total} />
			</div>
		{/if}
	{/if}
</Card>

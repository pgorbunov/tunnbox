<script lang="ts">
	/**
	 * Ctrl/Cmd+K palette: navigate, jump to an interface or peer by name, run
	 * quick actions (new peer / interface, toggle theme).
	 */
	import { goto } from '$app/navigation';
	import {
		LayoutDashboard,
		Moon,
		Network,
		Plus,
		ScrollText,
		Search,
		Settings,
		Sun,
		User,
		Users
	} from 'lucide-svelte';
	import type { IconComponent } from '$lib/utils/icons';
	import { api } from '$lib/api';
	import type { Interface, Peer } from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
	import { uid } from '$lib/utils/dom';
	import Kbd from '$lib/components/ui/Kbd.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import PeerStatusBadge from './PeerStatusBadge.svelte';

	let { open = $bindable(false) }: { open: boolean } = $props();

	interface Item {
		id: string;
		group: 'Pages' | 'Actions' | 'Interfaces' | 'Peers';
		label: string;
		hint?: string;
		icon: IconComponent;
		peer?: Peer;
		run: () => void;
	}

	const listId = uid('palette-list');
	let query = $state('');
	let active = $state(0);
	let interfaces = $state<Interface[]>([]);
	let peers = $state<Peer[]>([]);
	let searching = $state(false);
	let inputEl: HTMLInputElement | null = $state(null);
	let dialogEl: HTMLDialogElement | null = $state(null);
	let listEl: HTMLDivElement | null = $state(null);
	let debounce: ReturnType<typeof setTimeout> | null = null;
	let abort: AbortController | null = null;

	const pages: Item[] = [
		{ id: 'p-dash', group: 'Pages', label: 'Dashboard', icon: LayoutDashboard, run: () => void goto('/') },
		{ id: 'p-if', group: 'Pages', label: 'Interfaces', icon: Network, run: () => void goto('/interfaces') },
		{ id: 'p-peers', group: 'Pages', label: 'Peers', icon: Users, run: () => void goto('/peers') },
		{ id: 'p-audit', group: 'Pages', label: 'Audit log', icon: ScrollText, run: () => void goto('/audit') },
		{ id: 'p-settings', group: 'Pages', label: 'Settings', icon: Settings, run: () => void goto('/settings') }
	];

	const actions = $derived.by((): Item[] => {
		const out: Item[] = [];
		if (auth.can('operator')) {
			out.push({
				id: 'a-new-if',
				group: 'Actions',
				label: 'New interface',
				icon: Plus,
				run: () => void goto('/interfaces?new=1')
			});
			for (const i of interfaces) {
				out.push({
					id: `a-new-peer-${i.name}`,
					group: 'Actions',
					label: `New peer on ${i.name}`,
					icon: Plus,
					run: () => void goto(`/interfaces/${encodeURIComponent(i.name)}?new=peer`)
				});
			}
		}
		out.push({
			id: 'a-theme',
			group: 'Actions',
			label: themeStore.resolved === 'dark' ? 'Switch to light theme' : 'Switch to dark theme',
			icon: themeStore.resolved === 'dark' ? Sun : Moon,
			run: () => themeStore.toggle()
		});
		return out;
	});

	const ifaceItems = $derived<Item[]>(
		interfaces.map((i) => ({
			id: `i-${i.name}`,
			group: 'Interfaces',
			label: i.name,
			hint: `${i.address} · ${i.peer_count} peers`,
			icon: Network,
			run: () => void goto(`/interfaces/${encodeURIComponent(i.name)}`)
		}))
	);

	const peerItems = $derived<Item[]>(
		peers.map((p) => ({
			id: `peer-${p.id}`,
			group: 'Peers',
			label: p.name,
			hint: `${p.interface_name} · ${p.allowed_ips}`,
			icon: User,
			peer: p,
			run: () => void goto(`/interfaces/${encodeURIComponent(p.interface_name)}?peer=${p.id}`)
		}))
	);

	function matches(item: Item, q: string): boolean {
		if (!q) return true;
		const hay = `${item.label} ${item.hint ?? ''}`.toLowerCase();
		return q
			.toLowerCase()
			.split(/\s+/)
			.every((w) => hay.includes(w));
	}

	const results = $derived.by(() => {
		const q = query.trim();
		const all = [...pages, ...actions, ...ifaceItems, ...peerItems].filter((i) => matches(i, q));
		// When searching, peers/interfaces float above static pages.
		if (q) {
			const rank = { Peers: 0, Interfaces: 1, Actions: 2, Pages: 3 } as const;
			all.sort((a, b) => rank[a.group] - rank[b.group]);
		}
		return all.slice(0, 40);
	});

	const grouped = $derived.by(() => {
		const map = new Map<Item['group'], Item[]>();
		for (const r of results) {
			const arr = map.get(r.group) ?? [];
			arr.push(r);
			map.set(r.group, arr);
		}
		return [...map.entries()];
	});

	$effect(() => {
		if (!dialogEl) return;
		if (open && !dialogEl.open) {
			dialogEl.showModal();
			query = '';
			active = 0;
			peers = [];
			void loadInterfaces();
			requestAnimationFrame(() => inputEl?.focus());
		} else if (!open && dialogEl.open) {
			dialogEl.close();
		}
	});

	async function loadInterfaces() {
		try {
			interfaces = await api.interfaces.list();
		} catch {
			interfaces = [];
		}
	}

	$effect(() => {
		const q = query.trim();
		active = 0;
		if (debounce) clearTimeout(debounce);
		abort?.abort();
		if (q.length < 2) {
			peers = [];
			searching = false;
			return;
		}
		searching = true;
		debounce = setTimeout(async () => {
			abort = new AbortController();
			try {
				const page = await api.peers.search({ q, page_size: 8 }, abort.signal);
				peers = page.items;
			} catch {
				/* aborted or failed: keep the static results */
			} finally {
				searching = false;
			}
		}, 180);
	});

	function run(item: Item) {
		open = false;
		item.run();
	}

	function onkeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			active = Math.min(results.length - 1, active + 1);
			scrollActive();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			active = Math.max(0, active - 1);
			scrollActive();
		} else if (e.key === 'Enter') {
			e.preventDefault();
			const item = results[active];
			if (item) run(item);
		}
	}

	function scrollActive() {
		requestAnimationFrame(() => {
			listEl?.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' });
		});
	}

	function indexOf(item: Item) {
		return results.indexOf(item);
	}
</script>

<dialog
	bind:this={dialogEl}
	onclose={() => (open = false)}
	oncancel={(e) => {
		e.preventDefault();
		open = false;
	}}
	aria-label="Command palette"
	class="m-0 h-full max-h-none w-full max-w-none bg-transparent p-0 text-fg backdrop:bg-transparent"
>
	{#if open}
		<div class="fixed inset-0 flex items-start justify-center p-3 pt-[12vh] sm:p-6 sm:pt-[15vh]">
			<button
				type="button"
				class="anim-fade-in absolute inset-0 cursor-default bg-surface-overlay backdrop-blur-[2px]"
				aria-label="Close"
				tabindex="-1"
				onclick={() => (open = false)}
			></button>
			<div
				class="anim-pop-in relative flex max-h-[70vh] w-full max-w-xl flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-lg"
			>
				<div class="flex items-center gap-3 border-b border-border px-4">
					<Search class="h-5 w-5 shrink-0 text-fg-subtle" aria-hidden="true" />
					<input
						bind:this={inputEl}
						bind:value={query}
						type="text"
						role="combobox"
						aria-expanded="true"
						aria-controls={listId}
						aria-activedescendant={results[active] ? `${listId}-${results[active].id}` : undefined}
						aria-autocomplete="list"
						aria-label="Search pages, interfaces and peers"
						placeholder="Search pages, interfaces, peers…"
						autocomplete="off"
						spellcheck="false"
						class="h-12 w-full bg-transparent text-base text-fg outline-none placeholder:text-fg-subtle"
						{onkeydown}
					/>
					{#if searching}
						<Spinner size={16} class="text-fg-subtle" />
					{/if}
					<Kbd>Esc</Kbd>
				</div>
				<div
					bind:this={listEl}
					id={listId}
					role="listbox"
					aria-label="Results"
					class="min-h-0 flex-1 overflow-y-auto py-2 scrollbar-thin"
				>
					{#if results.length === 0}
						<p class="px-4 py-8 text-center text-sm text-fg-muted">No matches for “{query}”</p>
					{/if}
					{#each grouped as [group, items] (group)}
						<div role="group" aria-label={group}>
							<p class="px-4 pt-2 pb-1 text-[11px] font-semibold tracking-wide text-fg-subtle uppercase">
								{group}
							</p>
							{#each items as item (item.id)}
								{@const i = indexOf(item)}
								<div
									id={`${listId}-${item.id}`}
									role="option"
									aria-selected={i === active}
									class={`mx-2 flex cursor-pointer items-center gap-3 rounded-md px-2.5 py-2 text-sm ${i === active ? 'bg-bg-subtle text-fg' : 'text-fg-muted'}`}
									tabindex="-1"
									onpointermove={() => (active = i)}
									onclick={() => run(item)}
									onkeydown={(e) => {
										if (e.key === 'Enter') run(item);
									}}
								>
									<item.icon class="h-4 w-4 shrink-0 text-fg-subtle" />
									<span class="min-w-0 flex-1">
										<span class="block truncate font-medium text-fg">{item.label}</span>
										{#if item.hint}
											<span class="block truncate font-mono text-[12px] text-fg-subtle">{item.hint}</span>
										{/if}
									</span>
									{#if item.peer}
										<PeerStatusBadge status={item.peer.status} size="sm" />
									{/if}
								</div>
							{/each}
						</div>
					{/each}
				</div>
				<div
					class="hidden items-center gap-3 border-t border-border px-4 py-2 text-[11px] text-fg-subtle sm:flex"
				>
					<span class="flex items-center gap-1"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
					<span class="flex items-center gap-1"><Kbd>↵</Kbd> open</span>
					<span class="flex items-center gap-1"><Kbd>Esc</Kbd> close</span>
				</div>
			</div>
		</div>
	{/if}
</dialog>

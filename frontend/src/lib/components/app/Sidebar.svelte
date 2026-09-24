<script lang="ts">
	/**
	 * Navigation sidebar. Desktop: fixed column, collapsible to a 64px icon rail.
	 * Mobile (<768px): an off-canvas sheet rendered in a native <dialog>.
	 */
	import { page } from '$app/state';
	import { afterNavigate } from '$app/navigation';
	import {
		BookOpen,
		ChevronsLeft,
		ChevronsRight,
		LayoutDashboard,
		Network,
		ScrollText,
		Settings,
		Users,
		X
	} from 'lucide-svelte';
	import type { IconComponent } from '$lib/utils/icons';
	import { auth } from '$lib/stores/auth.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Logo from './Logo.svelte';

	interface Props {
		collapsed: boolean;
		mobileOpen: boolean;
		ontogglecollapse: () => void;
	}

	let { collapsed, mobileOpen = $bindable(false), ontogglecollapse }: Props = $props();

	interface NavItem {
		href: string;
		label: string;
		icon: IconComponent;
		minRole?: 'operator' | 'admin';
		external?: boolean;
	}

	const items: NavItem[] = [
		{ href: '/', label: 'Dashboard', icon: LayoutDashboard },
		{ href: '/interfaces', label: 'Interfaces', icon: Network },
		{ href: '/peers', label: 'Peers', icon: Users },
		{ href: '/audit', label: 'Audit log', icon: ScrollText, minRole: 'operator' },
		{ href: '/settings', label: 'Settings', icon: Settings }
	];

	const visibleItems = $derived(items.filter((i) => !i.minRole || auth.can(i.minRole)));

	function isActive(href: string): boolean {
		const path = page.url.pathname;
		if (href === '/') return path === '/';
		return path === href || path.startsWith(`${href}/`);
	}

	let sheet: HTMLDialogElement | null = $state(null);
	$effect(() => {
		if (!sheet) return;
		if (mobileOpen && !sheet.open) sheet.showModal();
		else if (!mobileOpen && sheet.open) sheet.close();
	});

	afterNavigate(() => {
		mobileOpen = false;
	});
</script>

{#snippet navList(rail: boolean)}
	<nav class="flex flex-1 flex-col gap-1 px-2 py-2" aria-label="Primary">
		{#each visibleItems as item (item.href)}
			{@const active = isActive(item.href)}
			<a
				href={item.href}
				aria-current={active ? 'page' : undefined}
				title={rail ? item.label : undefined}
				class={`group flex h-10 items-center gap-3 rounded-md px-2.5 text-sm font-medium transition-colors duration-150
					${rail ? 'justify-center' : ''}
					${active ? 'bg-accent-soft text-accent' : 'text-fg-muted hover:bg-bg-subtle hover:text-fg'}`}
			>
				<item.icon class={`h-5 w-5 shrink-0 ${active ? 'text-accent' : 'text-fg-subtle group-hover:text-fg'}`} />
				{#if !rail}
					<span class="truncate">{item.label}</span>
				{:else}
					<span class="sr-only">{item.label}</span>
				{/if}
			</a>
		{/each}
	</nav>
	<div class="mt-auto flex flex-col gap-1 px-2 py-2">
		<a
			href="/api/docs"
			target="_blank"
			rel="noopener noreferrer"
			title={rail ? 'API docs' : undefined}
			class={`flex h-10 items-center gap-3 rounded-md px-2.5 text-sm font-medium text-fg-muted transition-colors hover:bg-bg-subtle hover:text-fg ${rail ? 'justify-center' : ''}`}
		>
			<BookOpen class="h-5 w-5 shrink-0 text-fg-subtle" />
			{#if !rail}<span>API docs</span>{:else}<span class="sr-only">API docs</span>{/if}
		</a>
	</div>
{/snippet}

<!-- Desktop sidebar -->
<aside
	class={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-border bg-surface transition-[width] duration-200 md:flex ${collapsed ? 'w-16' : 'w-64'}`}
	aria-label="Sidebar"
>
	<div class={`flex h-14 items-center border-b border-border ${collapsed ? 'justify-center px-2' : 'px-4'}`}>
		<a href="/" class="rounded-sm" aria-label="TunnBox home">
			<Logo wordmark={!collapsed} />
		</a>
	</div>
	{@render navList(collapsed)}
	<div class="border-t border-border p-2">
		<IconButton
			label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
			onclick={ontogglecollapse}
			class={collapsed ? 'w-full' : 'w-full justify-start px-2.5 gap-3'}
		>
			{#if collapsed}
				<ChevronsRight class="h-5 w-5" />
			{:else}
				<ChevronsLeft class="h-5 w-5" />
				<span class="text-sm font-medium">Collapse</span>
			{/if}
		</IconButton>
	</div>
	{#if auth.version}
		<p class={`px-3 pb-2 text-[11px] text-fg-subtle ${collapsed ? 'sr-only' : ''}`}>v{auth.version}</p>
	{/if}
</aside>

<!-- Mobile sheet -->
<dialog
	bind:this={sheet}
	onclose={() => (mobileOpen = false)}
	oncancel={(e) => {
		e.preventDefault();
		mobileOpen = false;
	}}
	aria-label="Navigation"
	class="m-0 h-full max-h-none w-full max-w-none bg-transparent p-0 text-fg backdrop:bg-transparent md:hidden"
>
	{#if mobileOpen}
		<div class="fixed inset-0 flex">
			<button
				type="button"
				class="anim-fade-in absolute inset-0 cursor-default bg-surface-overlay"
				aria-label="Close navigation"
				tabindex="-1"
				onclick={() => (mobileOpen = false)}
			></button>
			<div class="anim-slide-in-left relative flex h-full w-72 max-w-[85vw] flex-col border-r border-border bg-surface shadow-lg">
				<div class="flex h-14 items-center justify-between border-b border-border px-4">
					<Logo />
					<IconButton label="Close navigation" size="sm" onclick={() => (mobileOpen = false)}>
						<X class="h-5 w-5" />
					</IconButton>
				</div>
				{@render navList(false)}
			</div>
		</div>
	{/if}
</dialog>

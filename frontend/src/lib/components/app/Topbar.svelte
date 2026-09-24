<script lang="ts">
	import { page } from '$app/state';
	import {
		ChevronRight,
		LogOut,
		Menu,
		Monitor,
		Moon,
		Search,
		ShieldCheck,
		Sun,
		User as UserIcon
	} from 'lucide-svelte';
	import { auth } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
	import DropdownMenu, { type MenuItem } from '$lib/components/ui/DropdownMenu.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Kbd from '$lib/components/ui/Kbd.svelte';
	import LiveIndicator from './LiveIndicator.svelte';

	interface Props {
		onopenmenu: () => void;
		onopenpalette: () => void;
	}
	let { onopenmenu, onopenpalette }: Props = $props();

	const LABELS: Record<string, string> = {
		'': 'Dashboard',
		interfaces: 'Interfaces',
		peers: 'Peers',
		audit: 'Audit log',
		settings: 'Settings'
	};

	const crumbs = $derived.by(() => {
		const segs = page.url.pathname.split('/').filter(Boolean);
		if (segs.length === 0) return [{ label: 'Dashboard', href: '/' }];
		const out: { label: string; href: string }[] = [];
		let path = '';
		for (const s of segs) {
			path += `/${s}`;
			out.push({ label: LABELS[s] ?? decodeURIComponent(s), href: path });
		}
		return out;
	});

	const themeItems: MenuItem[] = [
		{ label: 'Light', icon: Sun, onselect: () => themeStore.set('light') },
		{ label: 'Dark', icon: Moon, onselect: () => themeStore.set('dark') },
		{ label: 'System', icon: Monitor, onselect: () => themeStore.set('system') }
	];

	const userItems = $derived<MenuItem[]>([
		{ label: 'Security settings', icon: ShieldCheck, href: '/settings?tab=security' },
		{ label: 'Sign out', icon: LogOut, separator: true, onselect: () => void auth.logout() }
	]);

	const ThemeIcon = $derived(
		themeStore.theme === 'system' ? Monitor : themeStore.resolved === 'dark' ? Moon : Sun
	);
</script>

<header
	class="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border bg-bg/85 px-3 backdrop-blur sm:px-5"
>
	<IconButton label="Open navigation" class="md:hidden" onclick={onopenmenu}>
		<Menu class="h-5 w-5" />
	</IconButton>

	<nav aria-label="Breadcrumb" class="min-w-0 flex-1">
		<ol class="flex min-w-0 items-center gap-1 text-sm">
			{#each crumbs as c, i (c.href)}
				<li class="flex min-w-0 items-center gap-1">
					{#if i > 0}
						<ChevronRight class="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />
					{/if}
					{#if i === crumbs.length - 1}
						<span
							class={`truncate font-medium text-fg ${i > 0 ? 'font-mono text-[13px]' : ''}`}
							aria-current="page">{c.label}</span
						>
					{:else}
						<a href={c.href} class="truncate text-fg-muted hover:text-fg">{c.label}</a>
					{/if}
				</li>
			{/each}
		</ol>
	</nav>

	<div class="flex items-center gap-1 sm:gap-2">
		<button
			type="button"
			onclick={onopenpalette}
			class="hidden h-9 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-fg-subtle shadow-sm transition-colors hover:border-border-strong hover:text-fg md:inline-flex"
		>
			<Search class="h-4 w-4" aria-hidden="true" />
			<span>Search…</span>
			<span class="ml-4 flex items-center gap-0.5" aria-hidden="true"><Kbd>Ctrl</Kbd><Kbd>K</Kbd></span>
		</button>
		<IconButton label="Search" class="md:hidden" onclick={onopenpalette}>
			<Search class="h-5 w-5" />
		</IconButton>

		<LiveIndicator />

		<DropdownMenu items={themeItems} label="Theme">
			{#snippet trigger({ toggle, props })}
				<IconButton label="Change theme" onclick={toggle} {...props}>
					<ThemeIcon class="h-5 w-5" />
				</IconButton>
			{/snippet}
		</DropdownMenu>

		<DropdownMenu items={userItems} label="Account">
			{#snippet trigger({ toggle, props })}
				<button
					type="button"
					onclick={toggle}
					{...props}
					class="flex h-10 items-center gap-2 rounded-md px-1.5 text-sm hover:bg-bg-subtle sm:px-2"
					aria-label={`Account menu for ${auth.user?.username ?? 'user'}`}
				>
					<span class="flex h-7 w-7 items-center justify-center rounded-full bg-accent-soft text-accent">
						<UserIcon class="h-4 w-4" aria-hidden="true" />
					</span>
					<span class="hidden max-w-[10rem] truncate font-medium text-fg sm:inline"
						>{auth.user?.username}</span
					>
					<span class="hidden text-[11px] tracking-wide text-fg-subtle uppercase lg:inline"
						>{auth.user?.role}</span
					>
				</button>
			{/snippet}
		</DropdownMenu>
	</div>
</header>

<script lang="ts">
	import '../app.css';
	import '@fontsource-variable/inter';
	import '@fontsource/jetbrains-mono/400.css';
	import '@fontsource/jetbrains-mono/500.css';
	import '@fontsource/jetbrains-mono/600.css';
	import type { Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { auth } from '$lib/stores/auth.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import AppShell from '$lib/components/app/AppShell.svelte';
	import Logo from '$lib/components/app/Logo.svelte';
	import ToastRegion from '$lib/components/app/ToastRegion.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';

	let { children }: { children: Snippet } = $props();

	const PUBLIC_PREFIXES = ['/login', '/setup', '/share/'];
	const isPublic = $derived(
		PUBLIC_PREFIXES.some((p) => page.url.pathname === p || page.url.pathname.startsWith(p))
	);
	const isShare = $derived(page.url.pathname.startsWith('/share/'));

	themeStore.init();

	$effect(() => {
		void auth.bootstrap();
	});

	/** Same-origin, non-API path from `?next=`; anything else falls back to `/`. */
	function safeNext(raw: string | null): string {
		if (!raw) return '/';
		try {
			const u = new URL(raw, location.origin);
			if (u.origin !== location.origin) return '/';
			if (u.pathname === '/api' || u.pathname.startsWith('/api/')) return '/';
			if (u.pathname === '/login' || u.pathname === '/setup') return '/';
			return `${u.pathname}${u.search}${u.hash}`;
		} catch {
			return '/';
		}
	}

	function navigate(target: string) {
		void goto(target, { replaceState: true }).catch(() =>
			goto('/', { replaceState: true }).catch(() => undefined)
		);
	}

	// Route guarding: runs whenever auth status or the path changes.
	$effect(() => {
		const status = auth.status;
		const path = page.url.pathname;
		if (status === 'booting' || status === 'error' || isShare) return;
		if (status === 'setup') {
			if (path !== '/setup') navigate('/setup');
			return;
		}
		if (status === 'anon') {
			if (!isPublic) {
				const next = path !== '/' ? `?next=${encodeURIComponent(path + page.url.search)}` : '';
				navigate(`/login${next}`);
			} else if (path === '/setup') {
				navigate('/login');
			}
			return;
		}
		if (status === 'authed') {
			if (path === '/login' || (path === '/setup' && !auth.setupFlow)) {
				navigate(safeNext(page.url.searchParams.get('next')));
			}
		}
	});

	$effect(() => {
		if (auth.status === 'authed') void settingsStore.load().catch(() => undefined);
		else settingsStore.reset();
	});

	const showShell = $derived(auth.status === 'authed' && !isPublic);
	// While a redirect is pending, show the splash instead of flashing a page.
	const showBooting = $derived.by(() => {
		if (isShare) return false;
		const status = auth.status;
		const path = page.url.pathname;
		if (status === 'booting') return true;
		if (status === 'setup') return path !== '/setup';
		if (status === 'anon') return !isPublic || path === '/setup';
		return path === '/login' || (path === '/setup' && !auth.setupFlow);
	});
</script>

<svelte:head>
	<title>TunnBox</title>
</svelte:head>

{#if auth.status === 'error' && !isShare}
	<div class="flex min-h-dvh flex-col items-center justify-center gap-4 bg-bg px-4">
		<Logo size={40} />
		<ErrorState
			title="Server unreachable"
			message={auth.bootError ?? 'TunnBox could not reach its API. Check that the server is running.'}
			onretry={() => void auth.bootstrap()}
			retrying={false}
		/>
	</div>
{:else if showBooting}
	<div class="flex min-h-dvh flex-col items-center justify-center gap-6 bg-bg" aria-busy="true">
		<Logo size={40} />
		<Spinner size={22} class="text-fg-subtle" label="Loading TunnBox" />
	</div>
{:else if showShell}
	<AppShell>
		{@render children()}
	</AppShell>
{:else}
	{@render children()}
{/if}

<ToastRegion />

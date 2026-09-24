<script lang="ts">
	/** Sidebar + topbar + content area. Owns global hotkeys, palette and help dialogs. */
	import type { Snippet } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { registerHotkeys } from '$lib/utils/keyboard';
	import { focusMainHeading } from '$lib/utils/dom';
	import CommandPalette from './CommandPalette.svelte';
	import HelpDialog from './HelpDialog.svelte';
	import Sidebar from './Sidebar.svelte';
	import Topbar from './Topbar.svelte';

	let { children }: { children: Snippet } = $props();

	let mobileOpen = $state(false);
	let paletteOpen = $state(false);
	let helpOpen = $state(false);

	const collapsed = $derived(settingsStore.prefs.sidebarCollapsed);

	$effect(() =>
		registerHotkeys({
			openPalette: () => (paletteOpen = true),
			openHelp: () => (helpOpen = true)
		})
	);

	let firstNav = true;
	afterNavigate(() => {
		if (firstNav) {
			firstNav = false;
			return;
		}
		focusMainHeading();
	});
</script>

<a
	href="#main"
	class="sr-only z-50 rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
>
	Skip to content
</a>

<Sidebar {collapsed} bind:mobileOpen ontogglecollapse={() => settingsStore.toggleSidebar()} />

<div class={`flex min-h-dvh flex-col transition-[padding] duration-200 ${collapsed ? 'md:pl-16' : 'md:pl-64'}`}>
	<Topbar onopenmenu={() => (mobileOpen = true)} onopenpalette={() => (paletteOpen = true)} />
	<main id="main" class="mx-auto w-full max-w-[1280px] flex-1 px-4 py-6 sm:px-6 lg:px-8" tabindex="-1">
		{@render children()}
	</main>
</div>

<CommandPalette bind:open={paletteOpen} />
<HelpDialog bind:open={helpOpen} />

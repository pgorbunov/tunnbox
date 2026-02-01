<script lang="ts">
	import "../app.css";
	import "@fontsource/jetbrains-mono/400.css";
	import "@fontsource/jetbrains-mono/500.css";
	import "@fontsource/jetbrains-mono/600.css";
	import "@fontsource/jetbrains-mono/700.css";
	import { onMount } from "svelte";
	import { goto } from "$app/navigation";
	import { page } from "$app/stores";
	import { auth, isAuthenticated, isLoading } from "$lib/stores/auth";
	import { theme } from "$lib/stores/theme";
	import { api } from "$lib/api";
	import Sidebar from "$lib/components/Sidebar.svelte";
	import Toast from "$lib/components/Toast.svelte";

	let { children } = $props();

	let setupRequired = $state(false);
	let checkingSetup = $state(true);

	onMount(async () => {
		// Initialize theme
		theme.initialize();

		// Check if setup is required
		try {
			const result = await api.checkSetup();
			setupRequired = result.setup_required;
		} catch {
			// If check fails, proceed normally
		}
		checkingSetup = false;

		// Initialize auth
		await auth.initialize();
	});

	$effect(() => {
		if (checkingSetup || $isLoading) return;

		const isLoginPage = $page.url.pathname === "/login";
		const isSetupPage = $page.url.pathname === "/setup";

		if (setupRequired && !isSetupPage) {
			goto("/setup");
		} else if (
			!setupRequired &&
			!$isAuthenticated &&
			!isLoginPage &&
			!isSetupPage
		) {
			goto("/login");
		} else if ($isAuthenticated && (isLoginPage || isSetupPage)) {
			goto("/");
		}
	});

	const showSidebar = $derived(
		$isAuthenticated &&
			!$page.url.pathname.startsWith("/login") &&
			!$page.url.pathname.startsWith("/setup"),
	);
</script>

{#if checkingSetup || $isLoading}
	<div class="min-h-screen flex items-center justify-center">
		<div class="flex flex-col items-center gap-4">
			<div
				class="h-10 w-10 border-4 border-slate-700 border-t-emerald-500 rounded-full animate-spin"
			></div>
			<p class="text-slate-400">Loading...</p>
		</div>
	</div>
{:else}
	<div class="min-h-screen bg-white dark:bg-slate-950">
		{#if showSidebar}
			<Sidebar />
			<main class="lg:pl-64 min-h-screen">
				<div class="p-6 pt-20 lg:p-8 lg:pt-8">
					{@render children()}
				</div>
			</main>
		{:else}
			{@render children()}
		{/if}
	</div>
	<Toast />
{/if}

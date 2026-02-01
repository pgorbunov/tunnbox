<script lang="ts">
	import { page } from "$app/stores";
	import { auth, user } from "$lib/stores/auth";
	import {
		LayoutDashboard,
		Network,
		Settings,
		LogOut,
		Menu,
		X,
		FileText,
	} from "lucide-svelte";

	let mobileMenuOpen = $state(false);

	const navItems = [
		{ href: "/", label: "Dashboard", icon: LayoutDashboard },
		{ href: "/interfaces", label: "Interfaces", icon: Network },
		{ href: "/settings", label: "Settings", icon: Settings },
		{
			href: "/api/docs",
			label: "API Docs",
			icon: FileText,
			external: true,
		},
	];

	async function handleLogout() {
		await auth.logout();
	}
</script>

<!-- Mobile menu button -->
<button
	type="button"
	class="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700"
	onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
>
	{#if mobileMenuOpen}
		<X class="h-6 w-6" />
	{:else}
		<Menu class="h-6 w-6" />
	{/if}
</button>

<!-- Backdrop -->
{#if mobileMenuOpen}
	<div
		class="lg:hidden fixed inset-0 z-30 bg-black/50"
		onclick={() => (mobileMenuOpen = false)}
		onkeydown={(e) => e.key === "Escape" && (mobileMenuOpen = false)}
		role="button"
		tabindex="0"
	></div>
{/if}

<!-- Sidebar -->
<aside
	class="fixed inset-y-0 left-0 z-40 w-64 bg-slate-50 dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transform transition-transform duration-200 ease-in-out
		{mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0"
>
	<div class="flex flex-col h-full">
		<!-- Logo -->
		<div
			class="flex items-center gap-3 pl-20 pr-6 lg:px-6 py-5 border-b border-slate-200 dark:border-slate-800"
		>
			<!-- <div class="p-2 rounded-lg bg-emerald-600/10">
				<Shield class="h-6 w-6 text-emerald-500" />
			</div> -->
			<img
				src="/logo.svg"
				alt="TunnBox Logo"
				class="h-10 w-10 object-contain"
			/>
			<div>
				<h1
					class="text-lg font-semibold text-slate-900 dark:text-white"
				>
					TunnBox
				</h1>
				<p class="text-xs text-slate-500 dark:text-slate-500">
					VPN Management
				</p>
			</div>
		</div>

		<!-- Navigation -->
		<nav class="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
			{#each navItems as item}
				{@const isActive =
					$page.url.pathname === item.href ||
					(item.href !== "/" &&
						$page.url.pathname.startsWith(item.href))}
				{#if item.external}
					<a
						href={item.href}
						target="_blank"
						rel="noopener noreferrer"
						class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200"
						onclick={(e) => {
							mobileMenuOpen = false;
						}}
					>
						<item.icon class="h-5 w-5" />
						<span class="font-medium">{item.label}</span>
					</a>
				{:else}
					<a
						href={item.href}
						class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors
							{isActive
							? 'bg-emerald-600/10 text-emerald-600 dark:text-emerald-500'
							: 'text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200'}"
						onclick={(e) => {
							mobileMenuOpen = false;
						}}
					>
						<item.icon class="h-5 w-5" />
						<span class="font-medium">{item.label}</span>
					</a>
				{/if}
			{/each}
		</nav>

		<!-- User section -->
		<div class="px-4 py-4 border-t border-slate-200 dark:border-slate-800">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<div
						class="h-9 w-9 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-slate-700 dark:text-slate-300 font-medium"
					>
						{$user?.username?.charAt(0).toUpperCase() || "U"}
					</div>
					<div>
						<p
							class="text-sm font-medium text-slate-900 dark:text-slate-200"
						>
							{$user?.username || "User"}
						</p>
						<p class="text-xs text-slate-500 dark:text-slate-500">
							{$user?.is_admin ? "Administrator" : "User"}
						</p>
					</div>
				</div>
				<button
					type="button"
					class="p-2 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200 transition-colors"
					onclick={handleLogout}
					title="Logout"
				>
					<LogOut class="h-5 w-5" />
				</button>
			</div>
		</div>
	</div>
</aside>

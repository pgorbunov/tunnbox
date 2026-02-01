<script lang="ts">
	import { auth } from "$lib/stores/auth";
	import Button from "$lib/components/Button.svelte";

	let username = $state("");
	let password = $state("");
	let loading = $state(false);
	let error = $state("");

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = "";

		if (!username.trim() || !password) {
			error = "Please enter username and password";
			return;
		}

		loading = true;
		try {
			await auth.login(username.trim(), password);
		} catch (e) {
			error = e instanceof Error ? e.message : "Login failed";
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Login - TunnBox</title>
</svelte:head>

<div class="min-h-screen flex items-center justify-center p-4">
	<div class="w-full max-w-sm">
		<div class="text-center mb-8">
			<!-- <div class="inline-flex p-3 rounded-xl bg-emerald-600/10 mb-4">
				<Shield class="h-10 w-10 text-emerald-500" />
			</div> -->
			<img
				src="/logo.svg"
				alt="TunnBox Logo"
				class="h-24 w-24 object-contain mx-auto mb-4"
			/>
			<h1 class="text-2xl font-bold text-white">TunnBox</h1>
			<p class="text-slate-400 mt-2">Sign in to manage your VPN</p>
		</div>

		<div class="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
			<form onsubmit={handleSubmit} class="space-y-4">
				{#if error}
					<div
						class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm"
					>
						{error}
					</div>
				{/if}

				<div>
					<label
						for="username"
						class="block text-sm font-medium text-slate-300 mb-1.5"
					>
						Username
					</label>
					<input
						type="text"
						id="username"
						bind:value={username}
						autocomplete="username"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
					/>
				</div>

				<div>
					<label
						for="password"
						class="block text-sm font-medium text-slate-300 mb-1.5"
					>
						Password
					</label>
					<input
						type="password"
						id="password"
						bind:value={password}
						autocomplete="current-password"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
					/>
				</div>

				<Button type="submit" {loading} class="w-full">Sign In</Button>
			</form>
		</div>
	</div>
</div>

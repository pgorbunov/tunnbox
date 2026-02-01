<script lang="ts">
	import { goto } from "$app/navigation";
	import { api } from "$lib/api";
	import Button from "$lib/components/Button.svelte";
	import { Shield } from "lucide-svelte";

	let username = $state("admin");
	let password = $state("");
	let confirmPassword = $state("");
	let loading = $state(false);
	let error = $state("");

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = "";

		if (!username.trim()) {
			error = "Username is required";
			return;
		}

		if (password.length < 8) {
			error = "Password must be at least 8 characters";
			return;
		}

		if (password !== confirmPassword) {
			error = "Passwords do not match";
			return;
		}

		loading = true;
		try {
			await api.setup(username.trim(), password);
			window.location.href = "/login";
		} catch (e) {
			error = e instanceof Error ? e.message : "Setup failed";
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Setup - Tunnbox</title>
</svelte:head>

<div class="min-h-screen flex items-center justify-center p-4">
	<div class="w-full max-w-sm">
		<div class="text-center mb-8">
			<div class="inline-flex p-3 rounded-xl bg-emerald-600/10 mb-4">
				<Shield class="h-10 w-10 text-emerald-500" />
			</div>
			<h1 class="text-2xl font-bold text-white">Welcome to Tunnbox</h1>
			<p class="text-slate-400 mt-2">
				Create your admin account to get started
			</p>
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
						Admin Username
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
						autocomplete="new-password"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
					/>
					<p class="mt-1 text-xs text-slate-500">
						Minimum 8 characters
					</p>
				</div>

				<div>
					<label
						for="confirm_password"
						class="block text-sm font-medium text-slate-300 mb-1.5"
					>
						Confirm Password
					</label>
					<input
						type="password"
						id="confirm_password"
						bind:value={confirmPassword}
						autocomplete="new-password"
						class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
					/>
				</div>

				<Button type="submit" {loading} class="w-full"
					>Create Account</Button
				>
			</form>
		</div>
	</div>
</div>

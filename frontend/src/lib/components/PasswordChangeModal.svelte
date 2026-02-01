<script lang="ts">
	import Modal from './Modal.svelte';
	import Button from './Button.svelte';
	import { Eye, EyeOff } from 'lucide-svelte';

	interface Props {
		open: boolean;
		onClose: () => void;
		onSuccess?: () => void;
	}

	let { open = $bindable(), onClose, onSuccess }: Props = $props();

	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let showCurrentPassword = $state(false);
	let showNewPassword = $state(false);
	let showConfirmPassword = $state(false);
	let loading = $state(false);
	let error = $state('');

	function resetForm() {
		currentPassword = '';
		newPassword = '';
		confirmPassword = '';
		error = '';
		showCurrentPassword = false;
		showNewPassword = false;
		showConfirmPassword = false;
	}

	async function handleSubmit() {
		error = '';

		// Frontend validation
		if (!currentPassword || !newPassword || !confirmPassword) {
			error = 'All fields are required';
			return;
		}

		if (newPassword !== confirmPassword) {
			error = 'New passwords do not match';
			return;
		}

		if (newPassword.length < 8) {
			error = 'Password must be at least 8 characters long';
			return;
		}

		if (currentPassword === newPassword) {
			error = 'New password must be different from current password';
			return;
		}

		loading = true;

		try {
			const response = await fetch('/api/auth/password', {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${localStorage.getItem('access_token')}`
				},
				body: JSON.stringify({
					current_password: currentPassword,
					new_password: newPassword
				})
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to change password');
			}

			// Success
			resetForm();
			open = false;
			onSuccess?.();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to change password';
		} finally {
			loading = false;
		}
	}

	function handleClose() {
		if (!loading) {
			resetForm();
			onClose();
		}
	}
</script>

<Modal {open} onClose={handleClose} title="Change Password">
	<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
		{#if error}
			<div class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
				{error}
			</div>
		{/if}

		<!-- Current Password -->
		<div>
			<label for="current-password" class="block text-sm font-medium text-slate-200 mb-2">
				Current Password
			</label>
			<div class="relative">
				<input
					id="current-password"
					type={showCurrentPassword ? 'text' : 'password'}
					bind:value={currentPassword}
					disabled={loading}
					class="w-full px-3 py-2 pr-10 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent disabled:opacity-50"
					placeholder="Enter current password"
					autocomplete="current-password"
				/>
				<button
					type="button"
					onclick={() => showCurrentPassword =!showCurrentPassword}
					class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-200"
					tabindex="-1"
				>
					{#if showCurrentPassword}
						<EyeOff class="h-4 w-4" />
					{:else}
						<Eye class="h-4 w-4" />
					{/if}
				</button>
			</div>
		</div>

		<!-- New Password -->
		<div>
			<label for="new-password" class="block text-sm font-medium text-slate-200 mb-2">
				New Password
			</label>
			<div class="relative">
				<input
					id="new-password"
					type={showNewPassword ? 'text' : 'password'}
					bind:value={newPassword}
					disabled={loading}
					class="w-full px-3 py-2 pr-10 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent disabled:opacity-50"
					placeholder="Enter new password (min 8 characters)"
					autocomplete="new-password"
				/>
				<button
					type="button"
					onclick={() => showNewPassword = !showNewPassword}
					class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-200"
					tabindex="-1"
				>
					{#if showNewPassword}
						<EyeOff class="h-4 w-4" />
					{:else}
						<Eye class="h-4 w-4" />
					{/if}
				</button>
			</div>
		</div>

		<!-- Confirm Password -->
		<div>
			<label for="confirm-password" class="block text-sm font-medium text-slate-200 mb-2">
				Confirm New Password
			</label>
			<div class="relative">
				<input
					id="confirm-password"
					type={showConfirmPassword ? 'text' : 'password'}
					bind:value={confirmPassword}
					disabled={loading}
					class="w-full px-3 py-2 pr-10 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent disabled:opacity-50"
					placeholder="Confirm new password"
					autocomplete="new-password"
				/>
				<button
					type="button"
					onclick={() => showConfirmPassword = !showConfirmPassword}
					class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-200"
					tabindex="-1"
				>
					{#if showConfirmPassword}
						<EyeOff class="h-4 w-4" />
					{:else}
						<Eye class="h-4 w-4" />
					{/if}
				</button>
			</div>
		</div>

		<!-- Actions -->
		<div class="flex items-center gap-3 pt-2">
			<Button type="submit" {loading} class="flex-1">
				Change Password
			</Button>
			<Button type="button" variant="secondary" onclick={handleClose} disabled={loading}>
				Cancel
			</Button>
		</div>
	</form>
</Modal>

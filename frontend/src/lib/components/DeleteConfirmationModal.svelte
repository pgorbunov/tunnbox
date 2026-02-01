<script lang="ts">
	import Button from "./Button.svelte";
	import { AlertTriangle, X } from "lucide-svelte";

	interface Props {
		title: string;
		message: string;
		itemName?: string;
		onConfirm: () => void;
		onCancel: () => void;
		loading?: boolean;
	}

	let {
		title,
		message,
		itemName = "",
		onConfirm,
		onCancel,
		loading = false,
	}: Props = $props();
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
	onclick={onCancel}
	onkeydown={(e) => e.key === "Escape" && onCancel()}
>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="w-[calc(100vw-2rem)] max-w-md bg-slate-800 rounded-xl border border-slate-700 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
	>
		<div
			class="flex items-center justify-between p-5 border-b border-slate-700"
		>
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-lg bg-rose-500/10">
					<AlertTriangle class="h-5 w-5 text-rose-500" />
				</div>
				<h2 class="text-lg font-semibold text-white">{title}</h2>
			</div>
			<button
				type="button"
				class="p-1.5 rounded-lg text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
				onclick={onCancel}
			>
				<X class="h-5 w-5" />
			</button>
		</div>

		<div class="p-5 space-y-4">
			<p class="text-slate-300">
				{message}
			</p>

			{#if itemName}
				<div
					class="p-3 rounded-lg bg-slate-900 border border-slate-700"
				>
					<p class="text-sm text-slate-400 mb-1">Item to delete:</p>
					<p class="text-white font-semibold">{itemName}</p>
				</div>
			{/if}

			<p class="text-sm text-slate-400">This action cannot be undone.</p>

			<div class="flex justify-end gap-3 pt-4">
				<Button
					variant="secondary"
					onclick={onCancel}
					disabled={loading}>Cancel</Button
				>
				<Button variant="danger" onclick={onConfirm} {loading}
					>Delete</Button
				>
			</div>
		</div>
	</div>
</div>

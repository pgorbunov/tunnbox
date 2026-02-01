<script lang="ts">
	import { X } from "lucide-svelte";
	import type { Snippet } from "svelte";

	interface Props {
		open: boolean;
		title: string;
		onClose: () => void;
		children?: Snippet;
	}

	let { open, title, onClose, children }: Props = $props();

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleEscape(e: KeyboardEvent) {
		if (e.key === "Escape") {
			onClose();
		}
	}
</script>

{#if open}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
		onclick={handleBackdropClick}
		onkeydown={handleEscape}
		role="button"
		tabindex="-1"
	>
		<!-- Modal -->
		<div
			class="bg-slate-800 rounded-xl border border-slate-700 shadow-2xl max-w-md w-[calc(100vw-2rem)] max-h-[90vh] overflow-y-auto"
			role="dialog"
			aria-modal="true"
			aria-labelledby="modal-title"
		>
			<!-- Header -->
			<div
				class="flex items-center justify-between p-6 border-b border-slate-700"
			>
				<h2 id="modal-title" class="text-xl font-semibold text-white">
					{title}
				</h2>
				<button
					type="button"
					onclick={onClose}
					class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
					aria-label="Close modal"
				>
					<X class="h-5 w-5" />
				</button>
			</div>

			<!-- Content -->
			<div class="p-6">
				{#if children}
					{@render children()}
				{/if}
			</div>
		</div>
	</div>
{/if}

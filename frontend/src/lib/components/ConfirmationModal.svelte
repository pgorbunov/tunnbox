<script lang="ts">
	import { X, AlertTriangle, AlertCircle } from "lucide-svelte";
	import Button from "./Button.svelte";

	interface Props {
		open: boolean;
		title: string;
		message: string;
		variant?: "danger" | "warning" | "info";
		confirmText?: string;
		cancelText?: string;
		onConfirm: () => void | Promise<void>;
		onCancel: () => void;
	}

	let {
		open,
		title,
		message,
		variant = "warning",
		confirmText = "Confirm",
		cancelText = "Cancel",
		onConfirm,
		onCancel,
	}: Props = $props();

	let loading = $state(false);

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget && !loading) {
			onCancel();
		}
	}

	function handleEscape(e: KeyboardEvent) {
		if (e.key === "Escape" && !loading) {
			onCancel();
		}
	}

	async function handleConfirm() {
		try {
			loading = true;
			await onConfirm();
		} finally {
			loading = false;
		}
	}

	const iconClass = $derived(
		variant === "danger"
			? "text-rose-500 bg-rose-500/10"
			: variant === "warning"
				? "text-amber-500 bg-amber-500/10"
				: "text-blue-500 bg-blue-500/10",
	);

	const confirmVariant = $derived(
		variant === "danger" ? "danger" : "primary",
	);
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
			class="bg-slate-800 rounded-xl border border-slate-700 shadow-2xl max-w-md w-[calc(100vw-2rem)]"
			role="dialog"
			aria-modal="true"
			aria-labelledby="modal-title"
			aria-describedby="modal-description"
		>
			<!-- Header with Icon -->
			<div class="p-6">
				<div class="flex items-start gap-4">
					<!-- Icon -->
					<div class="flex-shrink-0 p-3 rounded-full {iconClass}">
						{#if variant === "danger"}
							<AlertCircle class="h-6 w-6" />
						{:else}
							<AlertTriangle class="h-6 w-6" />
						{/if}
					</div>

					<!-- Content -->
					<div class="flex-1 mt-1">
						<h2
							id="modal-title"
							class="text-lg font-semibold text-white mb-2"
						>
							{title}
						</h2>
						<p
							id="modal-description"
							class="text-sm text-slate-400 leading-relaxed"
						>
							{message}
						</p>
					</div>

					<!-- Close button -->
					<button
						type="button"
						onclick={onCancel}
						disabled={loading}
						class="flex-shrink-0 p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						aria-label="Close modal"
					>
						<X class="h-5 w-5" />
					</button>
				</div>
			</div>

			<!-- Actions -->
			<div class="flex items-center justify-end gap-3 px-6 pb-6">
				<Button
					variant="secondary"
					onclick={onCancel}
					disabled={loading}
				>
					{cancelText}
				</Button>
				<Button
					variant={confirmVariant}
					onclick={handleConfirm}
					{loading}
				>
					{confirmText}
				</Button>
			</div>
		</div>
	</div>
{/if}

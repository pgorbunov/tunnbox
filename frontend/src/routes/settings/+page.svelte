<script lang="ts">
	import { onMount } from "svelte";
	import { beforeNavigate } from "$app/navigation";
	import { user } from "$lib/stores/auth";
	import { theme, type Theme } from "$lib/stores/theme";
	import {
		api,
		type ServerSettings,
		type SystemInfo,
		type DataRetentionSettings,
	} from "$lib/api";
	import { toast } from "$lib/stores/toast";
	import Button from "$lib/components/Button.svelte";
	import PasswordChangeModal from "$lib/components/PasswordChangeModal.svelte";
	import CollapsibleSection from "$lib/components/CollapsibleSection.svelte";
	import ConfirmationModal from "$lib/components/ConfirmationModal.svelte";
	import {
		Shield,
		Server,
		Key,
		Edit,
		Save,
		X,
		Info,
		HelpCircle,
		ExternalLink,
		RefreshCw,
		AlertTriangle,
		Palette,
		Sun,
		Moon,
		Monitor,
		Download,
		Clock,
	} from "lucide-svelte";

	let passwordModalOpen = $state(false);
	let unsavedChangesModalOpen = $state(false);
	let pendingNavigation: (() => void) | null = null;

	// Server settings state
	let settings = $state<ServerSettings | null>(null);
	let loading = $state(true);

	// System info state
	let systemInfo = $state<SystemInfo | null>(null);
	let systemInfoLoading = $state(false);

	// Editing state
	let editingEndpoint = $state(false);
	let editingDns = $state(false);
	let endpointValue = $state("");
	let dnsValue = $state("");
	let originalEndpointValue = $state("");
	let originalDnsValue = $state("");
	let endpointError = $state("");
	let dnsError = $state("");
	let saving = $state(false);

	// Track unsaved changes
	let hasUnsavedChanges = $derived(
		(editingEndpoint && endpointValue !== originalEndpointValue) ||
			(editingDns && dnsValue !== originalDnsValue),
	);

	onMount(async () => {
		await loadSettings();
		await loadSystemInfo();

		// Browser navigation warning
		const handleBeforeUnload = (e: BeforeUnloadEvent) => {
			if (hasUnsavedChanges) {
				e.preventDefault();
				e.returnValue = "";
			}
		};
		window.addEventListener("beforeunload", handleBeforeUnload);

		return () => {
			window.removeEventListener("beforeunload", handleBeforeUnload);
		};
	});

	// Svelte navigation guard
	beforeNavigate((navigation) => {
		if (hasUnsavedChanges) {
			navigation.cancel();
			unsavedChangesModalOpen = true;
			pendingNavigation = () => navigation.complete();
		}
	});

	async function loadSettings() {
		try {
			loading = true;
			settings = await api.getSettings();
			endpointValue = settings.public_endpoint;
			dnsValue = settings.wg_default_dns;
			originalEndpointValue = settings.public_endpoint;
			originalDnsValue = settings.wg_default_dns;
		} catch (e) {
			toast.error(
				e instanceof Error ? e.message : "Failed to load settings",
			);
		} finally {
			loading = false;
		}
	}

	async function loadSystemInfo() {
		try {
			systemInfoLoading = true;
			systemInfo = await api.getSystemInfo();
		} catch (e) {
			toast.error(
				e instanceof Error
					? e.message
					: "Failed to load system information",
			);
		} finally {
			systemInfoLoading = false;
		}
	}

	function showPasswordModal() {
		passwordModalOpen = true;
	}

	function handlePasswordSuccess() {
		toast.success("Password changed successfully!");
	}

	// Endpoint editing
	function startEditEndpoint() {
		endpointValue = settings?.public_endpoint || "";
		originalEndpointValue = endpointValue;
		endpointError = "";
		editingEndpoint = true;
	}

	function cancelEditEndpoint() {
		endpointValue = originalEndpointValue;
		editingEndpoint = false;
		endpointError = "";
	}

	async function saveEndpoint() {
		endpointError = "";

		// Validate endpoint format - should NOT include port
		if (endpointValue && endpointValue.includes(":")) {
			endpointError =
				"Public endpoint should not include port. Port is set per-interface.";
			return;
		}

		try {
			saving = true;
			const updated = await api.updateSettings({
				public_endpoint: endpointValue,
			});
			settings = updated;
			originalEndpointValue = endpointValue;
			editingEndpoint = false;
			toast.success("Endpoint updated successfully");
		} catch (e) {
			endpointError =
				e instanceof Error ? e.message : "Failed to update endpoint";
		} finally {
			saving = false;
		}
	}

	// DNS editing
	function startEditDns() {
		dnsValue = settings?.wg_default_dns || "";
		originalDnsValue = dnsValue;
		dnsError = "";
		editingDns = true;
	}

	function cancelEditDns() {
		dnsValue = originalDnsValue;
		editingDns = false;
		dnsError = "";
	}

	async function saveDns() {
		dnsError = "";

		// Validate DNS format (basic IP validation)
		if (dnsValue) {
			const servers = dnsValue.split(",").map((s) => s.trim());
			for (const server of servers) {
				const parts = server.split(".");
				if (parts.length !== 4) {
					dnsError = "Invalid DNS format. Expected IPv4 address(es)";
					return;
				}
				for (const part of parts) {
					const num = parseInt(part);
					if (isNaN(num) || num < 0 || num > 255) {
						dnsError = "Invalid DNS format. Octets must be 0-255";
						return;
					}
				}
			}
		}

		try {
			saving = true;
			const updated = await api.updateSettings({
				wg_default_dns: dnsValue,
			});
			settings = updated;
			originalDnsValue = dnsValue;
			editingDns = false;
			toast.success("DNS updated successfully");
		} catch (e) {
			dnsError = e instanceof Error ? e.message : "Failed to update DNS";
		} finally {
			saving = false;
		}
	}

	// Unsaved changes handlers
	function handleDiscardChanges() {
		if (editingEndpoint) {
			cancelEditEndpoint();
		}
		if (editingDns) {
			cancelEditDns();
		}
		unsavedChangesModalOpen = false;
		if (pendingNavigation) {
			pendingNavigation();
			pendingNavigation = null;
		}
	}

	function handleCancelNavigation() {
		unsavedChangesModalOpen = false;
		pendingNavigation = null;
	}

	// Theme handling
	function selectTheme(newTheme: Theme) {
		theme.set(newTheme);
		toast.success(
			`Theme changed to ${newTheme === "auto" ? "system default" : newTheme}`,
		);
	}

	// Privacy & Data section state
	let autoRefreshInterval = $state(10);
	let timezone = $state("UTC");
	let editingTimezone = $state(false);
	let savingTimezone = $state(false);
	let timezoneValue = $state("UTC");
	let originalTimezoneValue = $state("UTC");

	let retentionEnabled = $state(false);
	let retentionDays = $state(90);
	let editingRetention = $state(false);
	let savingRetention = $state(false);
	let retentionEnabledValue = $state(false);
	let retentionDaysValue = $state(90);
	let originalRetentionEnabled = $state(false);
	let originalRetentionDays = $state(90);

	let exportingData = $state(false);

	const timezones = [
		"UTC",
		"America/New_York",
		"America/Los_Angeles",
		"America/Chicago",
		"America/Denver",
		"Europe/London",
		"Europe/Paris",
		"Europe/Berlin",
		"Asia/Tokyo",
		"Asia/Shanghai",
		"Australia/Sydney",
	];

	onMount(async () => {
		// Load auto-refresh from localStorage
		const savedInterval = localStorage.getItem("autoRefreshInterval");
		if (savedInterval) {
			autoRefreshInterval = parseInt(savedInterval);
		}

		// Load timezone and retention settings
		await loadPrivacySettings();
	});

	async function loadPrivacySettings() {
		try {
			const [timezoneRes, retentionRes] = await Promise.all([
				api.getTimezone(),
				api.getRetentionSettings(),
			]);

			timezone = timezoneRes.timezone;
			timezoneValue = timezoneRes.timezone;
			originalTimezoneValue = timezoneRes.timezone;

			retentionEnabled = retentionRes.enabled;
			retentionDays = retentionRes.logs_retention_days;
			retentionEnabledValue = retentionRes.enabled;
			retentionDaysValue = retentionRes.logs_retention_days;
			originalRetentionEnabled = retentionRes.enabled;
			originalRetentionDays = retentionRes.logs_retention_days;
		} catch (e) {
			console.error("Failed to load privacy settings:", e);
		}
	}

	function handleAutoRefreshChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		autoRefreshInterval = parseInt(target.value);
		localStorage.setItem("autoRefreshInterval", target.value);

		console.log(
			"[Settings] Auto-refresh interval changed to:",
			target.value,
		);

		// Dispatch custom event to notify dashboard
		window.dispatchEvent(
			new CustomEvent("autoRefreshIntervalChanged", {
				detail: { interval: parseInt(target.value) },
			}),
		);

		toast.success("Auto-refresh interval updated");
	}

	// Timezone editing
	function startEditTimezone() {
		timezoneValue = timezone;
		originalTimezoneValue = timezone;
		editingTimezone = true;
	}

	function cancelEditTimezone() {
		timezoneValue = originalTimezoneValue;
		editingTimezone = false;
	}

	async function saveTimezone() {
		try {
			savingTimezone = true;
			const updated = await api.updateTimezone(timezoneValue);
			timezone = updated.timezone;
			originalTimezoneValue = updated.timezone;
			editingTimezone = false;
			toast.success("Timezone preference updated");
		} catch (e) {
			toast.error(
				e instanceof Error ? e.message : "Failed to update timezone",
			);
		} finally {
			savingTimezone = false;
		}
	}

	// Retention editing
	function startEditRetention() {
		retentionEnabledValue = retentionEnabled;
		retentionDaysValue = retentionDays;
		originalRetentionEnabled = retentionEnabled;
		originalRetentionDays = retentionDays;
		editingRetention = true;
	}

	function cancelEditRetention() {
		retentionEnabledValue = originalRetentionEnabled;
		retentionDaysValue = originalRetentionDays;
		editingRetention = false;
	}

	async function saveRetention() {
		try {
			savingRetention = true;
			const updated = await api.updateRetentionSettings({
				enabled: retentionEnabledValue,
				logs_retention_days: retentionDaysValue,
			});
			retentionEnabled = updated.enabled;
			retentionDays = updated.logs_retention_days;
			originalRetentionEnabled = updated.enabled;
			originalRetentionDays = updated.logs_retention_days;
			editingRetention = false;
			toast.success("Data retention settings updated");
		} catch (e) {
			toast.error(
				e instanceof Error
					? e.message
					: "Failed to update retention settings",
			);
		} finally {
			savingRetention = false;
		}
	}

	async function exportData() {
		try {
			exportingData = true;
			const blob = await api.exportAllData();

			// Create download link
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			const timestamp = new Date()
				.toISOString()
				.replace(/[:.]/g, "-")
				.split("T")[0];
			a.download = `tunnbox_export_${timestamp}.json`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);

			toast.success("Data exported successfully");
		} catch (e) {
			toast.error(
				e instanceof Error ? e.message : "Failed to export data",
			);
		} finally {
			exportingData = false;
		}
	}
</script>

<svelte:head>
	<title>Settings - Tunnbox</title>
</svelte:head>

<PasswordChangeModal
	bind:open={passwordModalOpen}
	onClose={() => (passwordModalOpen = false)}
	onSuccess={handlePasswordSuccess}
/>

<ConfirmationModal
	open={unsavedChangesModalOpen}
	title="Unsaved Changes"
	message="You have unsaved changes. Are you sure you want to leave? Your changes will be lost."
	confirmText="Discard Changes"
	cancelText="Stay on Page"
	variant="warning"
	icon={AlertTriangle}
	onConfirm={handleDiscardChanges}
	onCancel={handleCancelNavigation}
/>

<div class="max-w-3xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-slate-900 dark:text-white">
			Settings
		</h1>
		<p class="text-slate-600 dark:text-slate-400 mt-1">
			Manage your Tunnbox configuration
		</p>
	</div>

	<div class="space-y-6">
		<!-- Account Settings -->
		<CollapsibleSection
			id="account"
			title="Account"
			icon={Shield}
			iconColor="bg-emerald-600/10 text-emerald-500"
		>
			<div class="space-y-4">
				<div
					class="flex items-center justify-between py-3 border-b border-slate-200 dark:border-slate-700/50"
				>
					<div>
						<p
							class="font-medium text-slate-800 dark:text-slate-200"
						>
							Username
						</p>
						<p class="text-sm text-slate-600 dark:text-slate-400">
							{$user?.username}
						</p>
					</div>
				</div>

				<div
					class="flex items-center justify-between py-3 border-b border-slate-200 dark:border-slate-700/50"
				>
					<div>
						<p
							class="font-medium text-slate-800 dark:text-slate-200"
						>
							Role
						</p>
						<p class="text-sm text-slate-600 dark:text-slate-400">
							{$user?.is_admin ? "Administrator" : "User"}
						</p>
					</div>
				</div>

				<div class="flex items-center justify-between py-3">
					<div>
						<p
							class="font-medium text-slate-800 dark:text-slate-200"
						>
							Password
						</p>
						<p class="text-sm text-slate-600 dark:text-slate-400">
							Change your account password
						</p>
					</div>
					<Button
						variant="secondary"
						size="sm"
						onclick={showPasswordModal}>Change Password</Button
					>
				</div>
			</div>
		</CollapsibleSection>

		<!-- Server Settings -->
		<CollapsibleSection
			id="server"
			title="Server"
			icon={Server}
			iconColor="bg-blue-600/10 text-blue-500"
		>
			<p class="text-sm text-slate-600 dark:text-slate-400 mb-4">
				These are defaults for newly created interfaces. You can
				customize them per interface after creation.
			</p>

			{#if loading}
				<div class="flex items-center justify-center py-8">
					<div
						class="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"
					></div>
				</div>
			{:else if settings}
				<div class="space-y-4">
					<!-- Public Endpoint -->
					<div
						class="py-3 border-b border-slate-200 dark:border-slate-700/50"
					>
						<div class="flex items-start justify-between gap-4">
							<div class="flex-1">
								<div class="flex items-center gap-2 mb-1">
									<p
										class="font-medium text-slate-800 dark:text-slate-200"
									>
										Public Endpoint
									</p>
									{#if editingEndpoint && endpointValue !== originalEndpointValue}
										<span
											class="px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded"
										>
											Modified
										</span>
									{/if}
									<div class="group relative">
										<HelpCircle
											class="h-4 w-4 text-slate-500 cursor-help"
										/>
										<div
											class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-300 shadow-xl z-10"
										>
											Public hostname or IP address of
											your WireGuard server (without
											port). Each interface uses its
											configured port automatically.
											Example: vpn.example.com or
											192.168.1.100
										</div>
									</div>
								</div>
								<p
									class="text-sm text-slate-600 dark:text-slate-400"
								>
									Public-facing hostname or IP (port added per
									interface)
								</p>

								{#if editingEndpoint}
									<div class="mt-3">
										<input
											type="text"
											bind:value={endpointValue}
											placeholder="e.g., vpn.example.com"
											class="w-full px-3 py-2 bg-white dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 font-mono text-sm {endpointValue !==
											originalEndpointValue
												? 'border-amber-500/50 focus:ring-amber-500 focus:border-amber-500'
												: 'border-slate-300 dark:border-slate-700 focus:ring-blue-500 focus:border-transparent'}"
										/>
										{#if endpointError}
											<p
												class="mt-1 text-sm text-rose-400"
											>
												{endpointError}
											</p>
										{/if}
									</div>
								{:else}
									<p
										class="mt-2 text-sm text-slate-700 dark:text-slate-300 font-mono"
									>
										{settings.public_endpoint ||
											"(not set)"}
									</p>
								{/if}
							</div>

							<div class="flex items-center gap-2">
								{#if editingEndpoint}
									<Button
										variant="secondary"
										size="sm"
										onclick={cancelEditEndpoint}
										disabled={saving}
									>
										<X class="h-4 w-4" />
									</Button>
									<Button
										size="sm"
										onclick={saveEndpoint}
										loading={saving}
									>
										<Save class="h-4 w-4" />
									</Button>
								{:else}
									<Button
										variant="secondary"
										size="sm"
										onclick={startEditEndpoint}
									>
										<Edit class="h-4 w-4 mr-1" />
										Edit
									</Button>
								{/if}
							</div>
						</div>
					</div>

					<!-- Default DNS -->
					<div
						class="py-3 border-b border-slate-200 dark:border-slate-700/50"
					>
						<div class="flex items-start justify-between gap-4">
							<div class="flex-1">
								<div class="flex items-center gap-2 mb-1">
									<p
										class="font-medium text-slate-800 dark:text-slate-200"
									>
										Default DNS for New Interfaces
									</p>
									{#if editingDns && dnsValue !== originalDnsValue}
										<span
											class="px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded"
										>
											Modified
										</span>
									{/if}
									<div class="group relative">
										<HelpCircle
											class="h-4 w-4 text-slate-500 cursor-help"
										/>
										<div
											class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-300 shadow-xl z-10"
										>
											Default DNS server for new
											interfaces. Can be single IP or
											comma-separated list (e.g., 1.1.1.1,
											8.8.8.8). You can customize per
											interface after creation.
										</div>
									</div>
								</div>
								<p
									class="text-sm text-slate-600 dark:text-slate-400"
								>
									Default DNS server for client configurations
								</p>

								{#if editingDns}
									<div class="mt-3">
										<input
											type="text"
											bind:value={dnsValue}
											placeholder="e.g., 1.1.1.1, 8.8.8.8"
											class="w-full px-3 py-2 bg-white dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 font-mono text-sm {dnsValue !==
											originalDnsValue
												? 'border-amber-500/50 focus:ring-amber-500 focus:border-amber-500'
												: 'border-slate-300 dark:border-slate-700 focus:ring-blue-500 focus:border-transparent'}"
										/>
										{#if dnsError}
											<p
												class="mt-1 text-sm text-rose-400"
											>
												{dnsError}
											</p>
										{/if}
									</div>
								{:else}
									<p
										class="mt-2 text-sm text-slate-700 dark:text-slate-300 font-mono"
									>
										{settings.wg_default_dns}
									</p>
								{/if}
							</div>

							<div class="flex items-center gap-2">
								{#if editingDns}
									<Button
										variant="secondary"
										size="sm"
										onclick={cancelEditDns}
										disabled={saving}
									>
										<X class="h-4 w-4" />
									</Button>
									<Button
										size="sm"
										onclick={saveDns}
										loading={saving}
									>
										<Save class="h-4 w-4" />
									</Button>
								{:else}
									<Button
										variant="secondary"
										size="sm"
										onclick={startEditDns}
									>
										<Edit class="h-4 w-4 mr-1" />
										Edit
									</Button>
								{/if}
							</div>
						</div>
					</div>

					<!-- Config Path (Read-only) -->
					<div class="py-3">
						<div class="flex items-start justify-between gap-4">
							<div class="flex-1">
								<div class="flex items-center gap-2 mb-1">
									<p
										class="font-medium text-slate-800 dark:text-slate-200"
									>
										Config Path
									</p>
									<div class="group relative">
										<Info
											class="h-4 w-4 text-slate-500 cursor-help"
										/>
										<div
											class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-300 shadow-xl z-10"
										>
											System-managed directory for
											WireGuard configuration files. This
											setting cannot be changed at
											runtime.
										</div>
									</div>
								</div>
								<p
									class="text-sm text-slate-600 dark:text-slate-400"
								>
									WireGuard configuration directory
								</p>
								<p
									class="mt-2 text-sm text-slate-500 dark:text-slate-500 font-mono"
								>
									{settings.wg_config_path}
								</p>
							</div>
							<span
								class="text-xs text-slate-500 dark:text-slate-500 bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded"
							>
								Read-only
							</span>
						</div>
					</div>
				</div>
			{/if}
		</CollapsibleSection>

		<!-- Appearance -->
		<CollapsibleSection
			id="appearance"
			title="Appearance"
			icon={Palette}
			iconColor="bg-violet-600/10 text-violet-500"
		>
			<div class="space-y-4">
				<div>
					<p
						class="font-medium text-slate-800 dark:text-slate-200 mb-1"
					>
						Theme
					</p>
					<p class="text-sm text-slate-600 dark:text-slate-400 mb-4">
						Choose your preferred color scheme
					</p>

					<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
						<!-- Light Theme -->
						<button
							onclick={() => selectTheme("light")}
							class="flex items-center gap-3 p-4 rounded-lg border-2 transition-all {$theme ===
							'light'
								? 'border-emerald-500 bg-emerald-500/10'
								: 'border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 hover:border-slate-400 dark:hover:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800'}"
						>
							<div
								class="flex items-center justify-center h-10 w-10 rounded-lg bg-slate-100 text-slate-900"
							>
								<Sun class="h-5 w-5" />
							</div>
							<div class="flex-1 text-left">
								<p
									class="font-medium text-slate-800 dark:text-slate-200"
								>
									Light
								</p>
								<p
									class="text-xs text-slate-600 dark:text-slate-400"
								>
									Bright theme
								</p>
							</div>
							{#if $theme === "light"}
								<div
									class="h-2 w-2 rounded-full bg-emerald-500"
								></div>
							{/if}
						</button>

						<!-- Dark Theme -->
						<button
							onclick={() => selectTheme("dark")}
							class="flex items-center gap-3 p-4 rounded-lg border-2 transition-all {$theme ===
							'dark'
								? 'border-emerald-500 bg-emerald-500/10'
								: 'border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 hover:border-slate-400 dark:hover:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800'}"
						>
							<div
								class="flex items-center justify-center h-10 w-10 rounded-lg bg-slate-900 text-slate-100"
							>
								<Moon class="h-5 w-5" />
							</div>
							<div class="flex-1 text-left">
								<p
									class="font-medium text-slate-800 dark:text-slate-200"
								>
									Dark
								</p>
								<p
									class="text-xs text-slate-600 dark:text-slate-400"
								>
									Easy on eyes
								</p>
							</div>
							{#if $theme === "dark"}
								<div
									class="h-2 w-2 rounded-full bg-emerald-500"
								></div>
							{/if}
						</button>

						<!-- Auto Theme -->
						<button
							onclick={() => selectTheme("auto")}
							class="flex items-center gap-3 p-4 rounded-lg border-2 transition-all {$theme ===
							'auto'
								? 'border-emerald-500 bg-emerald-500/10'
								: 'border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 hover:border-slate-400 dark:hover:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800'}"
						>
							<div
								class="flex items-center justify-center h-10 w-10 rounded-lg bg-gradient-to-br from-slate-100 to-slate-900 text-slate-100"
							>
								<Monitor class="h-5 w-5" />
							</div>
							<div class="flex-1 text-left">
								<p
									class="font-medium text-slate-800 dark:text-slate-200"
								>
									Auto
								</p>
								<p
									class="text-xs text-slate-600 dark:text-slate-400"
								>
									System default
								</p>
							</div>
							{#if $theme === "auto"}
								<div
									class="h-2 w-2 rounded-full bg-emerald-500"
								></div>
							{/if}
						</button>
					</div>
				</div>
			</div>
		</CollapsibleSection>

		<!-- Data & Privacy -->
		<CollapsibleSection
			id="privacy"
			title="Data & Privacy"
			icon={Shield}
			iconColor="bg-green-600/10 text-green-500"
		>
			<div class="space-y-6">
				<!-- Auto-refresh Interval -->
				<div
					class="py-3 border-b border-slate-200 dark:border-slate-700/50"
				>
					<div class="flex items-start justify-between gap-4">
						<div class="flex-1">
							<div class="flex items-center gap-2 mb-1">
								<p
									class="font-medium text-slate-800 dark:text-slate-200"
								>
									Auto-refresh Interval
								</p>
								<div class="group relative">
									<HelpCircle
										class="h-4 w-4 text-slate-500 cursor-help"
									/>
									<div
										class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-300 shadow-xl z-10"
									>
										How often the dashboard should
										automatically refresh to show the latest
										peer statistics. Set to "Off" to disable
										automatic refreshing.
									</div>
								</div>
							</div>
							<p
								class="text-sm text-slate-600 dark:text-slate-400"
							>
								Dashboard refresh frequency
							</p>

							<div class="mt-3">
								<select
									bind:value={autoRefreshInterval}
									onchange={handleAutoRefreshChange}
									class="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
								>
									<option value={0}>Off</option>
									<option value={5}>5 seconds</option>
									<option value={10}>10 seconds</option>
									<option value={30}>30 seconds</option>
									<option value={60}>60 seconds</option>
								</select>
							</div>
						</div>
					</div>
				</div>

				<!-- Timezone Preference -->
				<div
					class="py-3 border-b border-slate-200 dark:border-slate-700/50"
				>
					<div class="flex items-start justify-between gap-4">
						<div class="flex-1">
							<div class="flex items-center gap-2 mb-1">
								<p
									class="font-medium text-slate-800 dark:text-slate-200"
								>
									Timezone Preference
								</p>
								{#if editingTimezone && timezoneValue !== originalTimezoneValue}
									<span
										class="px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded"
									>
										Modified
									</span>
								{/if}
								<div class="group relative">
									<HelpCircle
										class="h-4 w-4 text-slate-500 cursor-help"
									/>
									<div
										class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-300 shadow-xl z-10"
									>
										Your preferred timezone for displaying
										timestamps. Note: Timezone formatting is
										not yet implemented, but your preference
										will be saved.
									</div>
								</div>
							</div>
							<p
								class="text-sm text-slate-600 dark:text-slate-400"
							>
								Display timezone for timestamps
							</p>

							{#if editingTimezone}
								<div class="mt-3 space-y-2">
									<select
										bind:value={timezoneValue}
										class="w-full px-3 py-2 bg-white dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 {timezoneValue !==
										originalTimezoneValue
											? 'border-amber-500/50 focus:ring-amber-500 focus:border-amber-500'
											: 'border-slate-300 dark:border-slate-700 focus:ring-blue-500 focus:border-transparent'}"
									>
										{#each timezones as tz}
											<option value={tz}>{tz}</option>
										{/each}
									</select>
									<p
										class="text-xs text-slate-500 dark:text-slate-500 italic"
									>
										Note: Timezone formatting not yet
										implemented
									</p>
								</div>
							{:else}
								<div class="mt-2 space-y-1">
									<p
										class="text-sm text-slate-700 dark:text-slate-300 font-mono"
									>
										{timezone}
									</p>
									<p
										class="text-xs text-slate-500 dark:text-slate-500 italic"
									>
										Note: Timezone formatting not yet
										implemented
									</p>
								</div>
							{/if}
						</div>

						<div class="flex items-center gap-2">
							{#if editingTimezone}
								<Button
									variant="secondary"
									size="sm"
									onclick={cancelEditTimezone}
									disabled={savingTimezone}
								>
									<X class="h-4 w-4" />
								</Button>
								<Button
									size="sm"
									onclick={saveTimezone}
									loading={savingTimezone}
								>
									<Save class="h-4 w-4" />
								</Button>
							{:else}
								<Button
									variant="secondary"
									size="sm"
									onclick={startEditTimezone}
								>
									<Edit class="h-4 w-4 mr-1" />
									Edit
								</Button>
							{/if}
						</div>
					</div>
				</div>

				<!-- Data Retention Policy -->
				<div
					class="py-3 border-b border-slate-200 dark:border-slate-700/50"
				>
					<div class="flex items-start justify-between gap-4">
						<div class="flex-1">
							<div class="flex items-center gap-2 mb-1">
								<p
									class="font-medium text-slate-800 dark:text-slate-200"
								>
									Data Retention Policy
								</p>
								{#if editingRetention && (retentionEnabledValue !== originalRetentionEnabled || retentionDaysValue !== originalRetentionDays)}
									<span
										class="px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded"
									>
										Modified
									</span>
								{/if}
								<div class="group relative">
									<HelpCircle
										class="h-4 w-4 text-slate-500 cursor-help"
									/>
									<div
										class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-300 shadow-xl z-10"
									>
										Configure how long audit logs should be
										retained. Note: Automatic cleanup is not
										yet implemented, but your retention
										policy will be saved.
									</div>
								</div>
							</div>
							<p
								class="text-sm text-slate-600 dark:text-slate-400"
							>
								Audit log retention settings
							</p>

							{#if editingRetention}
								<div class="mt-3 space-y-3">
									<label class="flex items-center gap-3">
										<input
											type="checkbox"
											bind:checked={retentionEnabledValue}
											class="h-4 w-4 rounded border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-0"
										/>
										<span
											class="text-sm text-slate-700 dark:text-slate-300"
											>Enable data retention policy</span
										>
									</label>

									{#if retentionEnabledValue}
										<div class="flex items-center gap-3">
											<label
												class="text-sm text-slate-700 dark:text-slate-300"
												>Retain logs for:</label
											>
											<input
												type="number"
												bind:value={retentionDaysValue}
												min="1"
												max="365"
												class="w-24 px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
											/>
											<span
												class="text-sm text-slate-600 dark:text-slate-400"
												>days</span
											>
										</div>
									{/if}

									<p
										class="text-xs text-slate-500 dark:text-slate-500 italic"
									>
										Note: Automatic cleanup not yet
										implemented
									</p>
								</div>
							{:else}
								<div class="mt-2 space-y-1">
									<p
										class="text-sm text-slate-700 dark:text-slate-300"
									>
										{retentionEnabled
											? `Enabled - ${retentionDays} days`
											: "Disabled"}
									</p>
									<p
										class="text-xs text-slate-500 dark:text-slate-500 italic"
									>
										Note: Automatic cleanup not yet
										implemented
									</p>
								</div>
							{/if}
						</div>

						<div class="flex items-center gap-2">
							{#if editingRetention}
								<Button
									variant="secondary"
									size="sm"
									onclick={cancelEditRetention}
									disabled={savingRetention}
								>
									<X class="h-4 w-4" />
								</Button>
								<Button
									size="sm"
									onclick={saveRetention}
									loading={savingRetention}
								>
									<Save class="h-4 w-4" />
								</Button>
							{:else}
								<Button
									variant="secondary"
									size="sm"
									onclick={startEditRetention}
								>
									<Edit class="h-4 w-4 mr-1" />
									Edit
								</Button>
							{/if}
						</div>
					</div>
				</div>

				<!-- Export Data -->
				<div class="py-3">
					<div class="flex items-start justify-between gap-4">
						<div class="flex-1">
							<div class="flex items-center gap-2 mb-1">
								<p
									class="font-medium text-slate-800 dark:text-slate-200"
								>
									Export All Data
								</p>
								<div class="group relative">
									<HelpCircle
										class="h-4 w-4 text-slate-500 cursor-help"
									/>
									<div
										class="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-300 shadow-xl z-10"
									>
										Download all non-sensitive data
										including users, peer metadata, audit
										logs, and settings. Sensitive data like
										passwords and private keys are excluded
										for security.
									</div>
								</div>
							</div>
							<p
								class="text-sm text-slate-600 dark:text-slate-400"
							>
								Download all non-sensitive data as JSON
							</p>
						</div>

						<Button
							variant="secondary"
							size="sm"
							onclick={exportData}
							loading={exportingData}
						>
							<Download class="h-4 w-4 mr-1" />
							Export Data
						</Button>
					</div>
				</div>
			</div>
		</CollapsibleSection>

		<!-- About -->
		<CollapsibleSection
			id="about"
			title="About"
			icon={Key}
			iconColor="bg-purple-600/10 text-purple-500"
			defaultExpanded={false}
		>
			{#if systemInfoLoading}
				<div class="flex items-center justify-center py-8">
					<div
						class="animate-spin h-8 w-8 border-4 border-purple-500 border-t-transparent rounded-full"
					></div>
				</div>
			{:else if systemInfo}
				<div class="space-y-6">
					<!-- Description -->
					<div
						class="pb-4 border-b border-slate-200 dark:border-slate-700/50"
					>
						<p
							class="text-sm text-slate-600 dark:text-slate-400 leading-relaxed"
						>
							A modern web interface for managing WireGuard VPN
							servers. Built with FastAPI and SvelteKit.
						</p>
					</div>

					<!-- Version Information -->
					<div>
						<h3
							class="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3"
						>
							Version Information
						</h3>
						<div class="space-y-2">
							<div class="flex items-center justify-between py-2">
								<span
									class="text-sm text-slate-600 dark:text-slate-400"
									>Frontend</span
								>
								<span
									class="text-sm text-slate-800 dark:text-slate-200 font-mono"
									>{systemInfo.frontend_version}</span
								>
							</div>
							<div class="flex items-center justify-between py-2">
								<span
									class="text-sm text-slate-600 dark:text-slate-400"
									>Backend</span
								>
								<span
									class="text-sm text-slate-800 dark:text-slate-200 font-mono"
									>{systemInfo.backend_version}</span
								>
							</div>
							{#if systemInfo.wireguard_version}
								<div
									class="flex items-center justify-between py-2"
								>
									<span
										class="text-sm text-slate-600 dark:text-slate-400"
										>WireGuard</span
									>
									<span
										class="text-sm text-slate-800 dark:text-slate-200 font-mono"
										>{systemInfo.wireguard_version}</span
									>
								</div>
							{/if}
							{#if systemInfo.docker_version}
								<div
									class="flex items-center justify-between py-2"
								>
									<span
										class="text-sm text-slate-600 dark:text-slate-400"
										>Docker</span
									>
									<span
										class="text-sm text-slate-800 dark:text-slate-200 font-mono"
										>{systemInfo.docker_version}</span
									>
								</div>
							{/if}
						</div>
					</div>

					<!-- System Information -->
					<div
						class="pt-4 border-t border-slate-200 dark:border-slate-700/50"
					>
						<h3
							class="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3"
						>
							System Information
						</h3>
						<div class="space-y-2">
							<div class="flex items-center justify-between py-2">
								<span
									class="text-sm text-slate-600 dark:text-slate-400"
									>Operating System</span
								>
								<span
									class="text-sm text-slate-800 dark:text-slate-200"
									>{systemInfo.os_name}
									{systemInfo.os_version}</span
								>
							</div>
							<div class="flex items-center justify-between py-2">
								<span
									class="text-sm text-slate-600 dark:text-slate-400"
									>Python Version</span
								>
								<span
									class="text-sm text-slate-800 dark:text-slate-200 font-mono"
									>{systemInfo.python_version}</span
								>
							</div>
							<div class="flex items-center justify-between py-2">
								<span
									class="text-sm text-slate-600 dark:text-slate-400"
									>Database</span
								>
								<span
									class="text-sm text-slate-800 dark:text-slate-200"
									>{systemInfo.database_type}</span
								>
							</div>
						</div>
					</div>

					<!-- Links -->
					<div
						class="pt-4 border-t border-slate-200 dark:border-slate-700/50"
					>
						<h3
							class="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3"
						>
							Resources
						</h3>
						<div class="space-y-2">
							<a
								href={systemInfo.github_url}
								target="_blank"
								rel="noopener noreferrer"
								class="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/30 transition-colors group"
							>
								<span
									class="text-sm text-slate-600 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200"
									>GitHub Repository</span
								>
								<ExternalLink
									class="h-4 w-4 text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300"
								/>
							</a>
							<a
								href={systemInfo.documentation_url}
								target="_blank"
								rel="noopener noreferrer"
								class="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/30 transition-colors group"
							>
								<span
									class="text-sm text-slate-600 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200"
									>Documentation</span
								>
								<ExternalLink
									class="h-4 w-4 text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300"
								/>
							</a>
						</div>
					</div>

					<!-- License -->
					<div
						class="pt-4 border-t border-slate-200 dark:border-slate-700/50"
					>
						<div class="flex items-center justify-between">
							<span
								class="text-sm text-slate-600 dark:text-slate-400"
								>License</span
							>
							<span
								class="text-sm text-slate-800 dark:text-slate-200"
								>{systemInfo.license}</span
							>
						</div>
					</div>
				</div>
			{/if}
		</CollapsibleSection>
	</div>
</div>

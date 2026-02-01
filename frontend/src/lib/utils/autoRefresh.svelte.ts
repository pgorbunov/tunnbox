import { onMount, onDestroy } from 'svelte';

/**
 * Get the auto-refresh interval from localStorage in milliseconds.
 * Returns 0 if auto-refresh is disabled.
 */
function getAutoRefreshIntervalMs(): number {
	const saved = localStorage.getItem('autoRefreshInterval');
	const seconds = saved ? parseInt(saved) : 10;
	return seconds > 0 ? seconds * 1000 : 0;
}

/**
 * Auto-refresh utility that efficiently polls data at an interval
 * controlled by the user's autoRefreshInterval setting.
 * Automatically pauses when the page is not visible to save resources.
 *
 * @param callback - Function to call on each refresh
 * @returns Object with manual refresh and current refreshing state
 */
export function useAutoRefresh(callback: () => Promise<void>) {
	let intervalId: number | null = null;
	let isRefreshing = $state(false);
	let isPageVisible = $state(true);
	let currentIntervalMs = $state(0);

	async function refresh() {
		if (isRefreshing) return; // Prevent concurrent refreshes

		isRefreshing = true;
		try {
			await callback();
		} catch (error) {
			console.error('Auto-refresh error:', error);
		} finally {
			isRefreshing = false;
		}
	}

	function startPolling() {
		stopPolling();
		currentIntervalMs = getAutoRefreshIntervalMs();

		if (currentIntervalMs > 0) {
			intervalId = window.setInterval(() => {
				if (isPageVisible) {
					refresh();
				}
			}, currentIntervalMs);
		}
	}

	function stopPolling() {
		if (intervalId !== null) {
			clearInterval(intervalId);
			intervalId = null;
		}
	}

	function handleVisibilityChange() {
		isPageVisible = !document.hidden;

		// Refresh immediately when page becomes visible
		if (isPageVisible && intervalId !== null) {
			refresh();
		}
	}

	function handleIntervalChange() {
		startPolling();
	}

	onMount(() => {
		startPolling();
		document.addEventListener('visibilitychange', handleVisibilityChange);
		window.addEventListener('autoRefreshIntervalChanged', handleIntervalChange);
	});

	onDestroy(() => {
		stopPolling();
		document.removeEventListener('visibilitychange', handleVisibilityChange);
		window.removeEventListener('autoRefreshIntervalChanged', handleIntervalChange);
	});

	return {
		get refreshing() {
			return isRefreshing;
		},
		get intervalSeconds() {
			return currentIntervalMs / 1000;
		},
		manualRefresh: refresh
	};
}

import { onMount, onDestroy } from 'svelte';

/**
 * Auto-refresh utility that efficiently polls data at a specified interval.
 * Automatically pauses when the page is not visible to save resources.
 *
 * @param callback - Function to call on each refresh
 * @param interval - Refresh interval in milliseconds (default: 5000ms)
 * @returns Object with manual refresh and current refreshing state
 */
export function useAutoRefresh(callback: () => Promise<void>, interval: number = 5000) {
	let intervalId: number | null = null;
	let isRefreshing = $state(false);
	let isPageVisible = $state(true);

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
		if (intervalId !== null) return;
		intervalId = window.setInterval(() => {
			if (isPageVisible) {
				refresh();
			}
		}, interval);
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

	onMount(() => {
		// Start polling
		startPolling();

		// Listen for visibility changes
		document.addEventListener('visibilitychange', handleVisibilityChange);
	});

	onDestroy(() => {
		stopPolling();
		document.removeEventListener('visibilitychange', handleVisibilityChange);
	});

	return {
		get refreshing() {
			return isRefreshing;
		},
		manualRefresh: refresh
	};
}

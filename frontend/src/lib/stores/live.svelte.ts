/**
 * Bridges the current page's poller to the topbar LiveIndicator. A page calls
 * `liveStatus.bind(poller)` inside an effect and returns the cleanup.
 */
import type { Poller } from '$lib/utils/poll.svelte';

let current = $state<Poller | null>(null);

export const liveStatus = {
	get active() {
		return current !== null;
	},
	get refreshing() {
		return current?.refreshing ?? false;
	},
	get lastUpdated() {
		return current?.lastUpdated ?? null;
	},
	get error() {
		return current?.error ?? null;
	},
	refresh() {
		void current?.refresh();
	},
	bind(poller: Poller): () => void {
		current = poller;
		return () => {
			if (current === poller) current = null;
		};
	}
};

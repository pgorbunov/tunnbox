import { writable } from 'svelte/store';
import { api, type Interface, type Peer } from '$lib/api';

interface InterfacesState {
	interfaces: Interface[];
	loading: boolean;
	error: string | null;
}

function createInterfacesStore() {
	const { subscribe, set, update } = writable<InterfacesState>({
		interfaces: [],
		loading: false,
		error: null
	});

	return {
		subscribe,

		async load(silent: boolean = false) {
			if (!silent) {
				update((state) => ({ ...state, loading: true, error: null }));
			}
			try {
				const interfaces = await api.getInterfaces();
				set({ interfaces, loading: false, error: null });
			} catch (error) {
				const message = error instanceof Error ? error.message : 'Failed to load interfaces';
				update((state) => ({ ...state, loading: false, error: message }));
			}
		},

		async toggle(name: string, up: boolean) {
			try {
				if (up) {
					await api.bringInterfaceUp(name);
				} else {
					await api.bringInterfaceDown(name);
				}
				// Refresh the interface state
				const updatedInterface = await api.getInterface(name);
				update((state) => ({
					...state,
					interfaces: state.interfaces.map((iface) =>
						iface.name === name ? updatedInterface : iface
					)
				}));
			} catch (error) {
				throw error;
			}
		},

		updateInterface(iface: Interface) {
			update((state) => ({
				...state,
				interfaces: state.interfaces.map((i) => (i.name === iface.name ? iface : i))
			}));
		},

		addInterface(iface: Interface) {
			update((state) => ({
				...state,
				interfaces: [...state.interfaces, iface]
			}));
		},

		removeInterface(name: string) {
			update((state) => ({
				...state,
				interfaces: state.interfaces.filter((i) => i.name !== name)
			}));
		}
	};
}

export const interfaces = createInterfacesStore();

// Peers store for a specific interface
interface PeersState {
	peers: Peer[];
	loading: boolean;
	error: string | null;
}

function createPeersStore() {
	const { subscribe, set, update } = writable<PeersState>({
		peers: [],
		loading: false,
		error: null
	});

	return {
		subscribe,

		async load(interfaceName: string, silent: boolean = false) {
			if (!silent) {
				update((state) => ({ ...state, loading: true, error: null }));
			}
			try {
				const peers = await api.getPeers(interfaceName);
				set({ peers, loading: false, error: null });
			} catch (error) {
				const message = error instanceof Error ? error.message : 'Failed to load peers';
				update((state) => ({ ...state, loading: false, error: message }));
			}
		},

		addPeer(peer: Peer) {
			update((state) => ({
				...state,
				peers: [...state.peers, peer]
			}));
		},

		updatePeer(publicKey: string, updatedPeer: Peer) {
			update((state) => ({
				...state,
				peers: state.peers.map((p) => (p.public_key === publicKey ? updatedPeer : p))
			}));
		},

		removePeer(publicKey: string) {
			update((state) => ({
				...state,
				peers: state.peers.filter((p) => p.public_key !== publicKey)
			}));
		},

		clear() {
			set({ peers: [], loading: false, error: null });
		}
	};
}

export const peers = createPeersStore();

import { writable, derived } from 'svelte/store';
import { api } from '$lib/api';

interface User {
	id: number;
	username: string;
	is_admin: boolean;
}

interface AuthState {
	user: User | null;
	loading: boolean;
	initialized: boolean;
}

function createAuthStore() {
	const { subscribe, set, update } = writable<AuthState>({
		user: null,
		loading: true,
		initialized: false
	});

	return {
		subscribe,

		async initialize() {
			const token = api.getAccessToken();
			if (!token) {
				set({ user: null, loading: false, initialized: true });
				return;
			}

			try {
				const user = await api.getCurrentUser();
				set({ user, loading: false, initialized: true });
			} catch {
				api.setAccessToken(null);
				set({ user: null, loading: false, initialized: true });
			}
		},

		async login(username: string, password: string) {
			update((state) => ({ ...state, loading: true }));
			try {
				await api.login(username, password);
				const user = await api.getCurrentUser();

				// Also set token in cookie for Swagger UI access
				const token = api.getAccessToken();
				if (token) {
					document.cookie = `access_token=${token}; path=/; SameSite=Strict`;
				}

				set({ user, loading: false, initialized: true });
			} catch (error) {
				update((state) => ({ ...state, loading: false }));
				throw error;
			}
		},

		async logout() {
			try {
				await api.logout();
			} finally {
				// Clear cookie
				document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT;';
				set({ user: null, loading: false, initialized: true });
			}
		},

		setUser(user: User | null) {
			update((state) => ({ ...state, user }));
		}
	};
}

export const auth = createAuthStore();
export const isAuthenticated = derived(auth, ($auth) => $auth.user !== null);
export const isLoading = derived(auth, ($auth) => $auth.loading);
export const user = derived(auth, ($auth) => $auth.user);

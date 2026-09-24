/**
 * Runes-based auth state. The access token itself lives in `api/client.ts`;
 * this store only knows who is signed in and where the app is in its lifecycle.
 */
import { goto } from '$app/navigation';
import { api, ApiError } from '$lib/api';
import {
	clearAccessToken,
	refreshSession,
	setAccessToken,
	setRefreshedHandler,
	setUnauthorizedHandler
} from '$lib/api/client';
import type { LoginResponse, LoginSuccess, Role, User } from '$lib/api/types';

export type AuthStatus = 'booting' | 'anon' | 'authed' | 'setup';

const ROLE_RANK: Record<Role, number> = { viewer: 0, operator: 1, admin: 2 };

let status = $state<AuthStatus>('booting');
let user = $state<User | null>(null);
let version = $state<string>('');

function applyLogin(res: LoginSuccess) {
	setAccessToken(res.access_token, res.expires_in);
	user = res.user;
	status = 'authed';
}

function redirectToLogin() {
	const path = window.location.pathname + window.location.search;
	const next = path && path !== '/' && !path.startsWith('/login') ? `?next=${encodeURIComponent(path)}` : '';
	void goto(`/login${next}`, { replaceState: true });
}

setUnauthorizedHandler(() => {
	if (status === 'authed') {
		user = null;
		status = 'anon';
		redirectToLogin();
	}
});

setRefreshedHandler((r) => {
	user = r.user;
});

export const auth = {
	get status() {
		return status;
	},
	get user() {
		return user;
	},
	get version() {
		return version;
	},
	get isAuthed() {
		return status === 'authed';
	},
	get role(): Role | null {
		return user?.role ?? null;
	},
	/** True when the current user has at least the given role. */
	can(min: Role): boolean {
		return user !== null && ROLE_RANK[user.role] >= ROLE_RANK[min];
	},

	/** Called once from the root layout. Resolves when status is settled. */
	async bootstrap(): Promise<void> {
		try {
			const s = await api.auth.status();
			version = s.version;
			if (s.setup_required) {
				status = 'setup';
				return;
			}
		} catch {
			// If the status endpoint is unreachable we still try to refresh; the
			// pages will surface a proper error state.
		}
		const refreshed = await refreshSession();
		if (refreshed) {
			user = refreshed.user;
			status = 'authed';
		} else {
			user = null;
			status = 'anon';
		}
	},

	async login(username: string, password: string): Promise<LoginResponse> {
		const res = await api.auth.login({ username, password });
		if ('mfa_required' in res) return res;
		applyLogin(res);
		return res;
	},

	async loginMfa(mfaToken: string, code: string): Promise<LoginSuccess> {
		const res = await api.auth.loginMfa({ mfa_token: mfaToken, code });
		applyLogin(res);
		return res;
	},

	async setup(username: string, password: string): Promise<LoginSuccess> {
		const res = await api.auth.setup({ username, password });
		applyLogin(res);
		return res;
	},

	async logout(): Promise<void> {
		try {
			await api.auth.logout();
		} catch (err) {
			// A failed logout (e.g. session already gone) still clears local state.
			if (!(err instanceof ApiError)) throw err;
		} finally {
			clearAccessToken();
			user = null;
			status = 'anon';
			void goto('/login', { replaceState: true });
		}
	},

	/** Patch the cached user (e.g. after enabling MFA). */
	setUser(u: User) {
		user = u;
	}
};

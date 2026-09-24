/**
 * Runes-based auth state. The access token itself lives in `api/client.ts`;
 * this store only knows who is signed in and where the app is in its lifecycle.
 */
import { goto } from '$app/navigation';
import { api, ApiError, toApiError } from '$lib/api';
import {
	adoptTokenFromTabs,
	announceLogout,
	announceToken,
	beginLogout,
	refreshSession,
	setAccessToken,
	setRefreshedHandler,
	setRemoteLogoutHandler,
	setUnauthorizedHandler
} from '$lib/api/client';
import type { LoginResponse, LoginSuccess, Role, User } from '$lib/api/types';

/** `error` = the server could not be reached during boot; the layout offers a retry. */
export type AuthStatus = 'booting' | 'anon' | 'authed' | 'setup' | 'error';

const ROLE_RANK: Record<Role, number> = { viewer: 0, operator: 1, admin: 2 };

let status = $state<AuthStatus>('booting');
let user = $state<User | null>(null);
let version = $state<string>('');
let bootError = $state<string | null>(null);
// True while the first-run wizard continues after the admin was created.
let setupFlow = $state(false);

function applyLogin(res: LoginSuccess) {
	setAccessToken(res.access_token, res.expires_in, res.user);
	announceToken(res.access_token, res.expires_in, res.user);
	user = res.user;
	status = 'authed';
}

function redirectToLogin() {
	const path = window.location.pathname + window.location.search;
	const next = path && path !== '/' && !path.startsWith('/login') ? `?next=${encodeURIComponent(path)}` : '';
	void goto(`/login${next}`, { replaceState: true }).catch(() => undefined);
}

function dropSession() {
	if (status === 'authed') {
		user = null;
		status = 'anon';
		redirectToLogin();
	}
}

setUnauthorizedHandler(dropSession);
setRemoteLogoutHandler(dropSession);

setRefreshedHandler((r) => {
	user = r.user;
	if (status === 'anon') status = 'authed';
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
	get bootError() {
		return bootError;
	},
	get isAuthed() {
		return status === 'authed';
	},
	get setupFlow() {
		return setupFlow;
	},
	finishSetupFlow() {
		setupFlow = false;
	},
	get role(): Role | null {
		return user?.role ?? null;
	},
	/** True when the current user has at least the given role. */
	can(min: Role): boolean {
		return user !== null && ROLE_RANK[user.role] >= ROLE_RANK[min];
	},

	/**
	 * Called from the root layout (and again from its retry button). Moves to
	 * `anon` only when the server actually rejected the refresh; a transient
	 * failure becomes `error` so the user is not bounced to the login page.
	 */
	async bootstrap(): Promise<void> {
		status = 'booting';
		bootError = null;
		let statusFailed = false;
		try {
			const s = await api.auth.status();
			version = s.version;
			if (s.setup_required) {
				status = 'setup';
				return;
			}
		} catch {
			statusFailed = true;
		}
		try {
			// Prefer a token another open tab already holds; otherwise refresh (under a cross-tab lock).
			const refreshed = (await adoptTokenFromTabs()) ?? (await refreshSession());
			if (refreshed) {
				user = refreshed.user;
				status = 'authed';
			} else {
				user = null;
				status = 'anon';
			}
		} catch (err) {
			const e = toApiError(err);
			bootError =
				statusFailed || e.isNetwork ? e.detail : `The server returned an error (${e.status}). ${e.detail}`;
			status = 'error';
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
		setupFlow = true;
		applyLogin(res);
		return res;
	},

	async logout(): Promise<void> {
		// Bump the epoch first so a refresh racing with the logout cannot re-install a token.
		beginLogout();
		try {
			await api.auth.logout();
		} catch (err) {
			// A failed logout (e.g. session already gone) still clears local state.
			if (!(err instanceof ApiError)) throw err;
		} finally {
			announceLogout();
			user = null;
			status = 'anon';
			void goto('/login', { replaceState: true }).catch(() => undefined);
		}
	},

	/** Patch the cached user (e.g. after enabling MFA). */
	setUser(u: User) {
		user = u;
	}
};

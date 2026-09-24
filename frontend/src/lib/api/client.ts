/**
 * Fetch wrapper for the TunnBox API.
 *
 * - Access token is held in a module-level variable only (never persisted).
 * - `/auth/refresh` is single-flight per tab AND serialised across tabs with the
 *   Web Locks API (the backend revokes a session on refresh-token reuse, so two
 *   tabs must never refresh concurrently). The winning tab broadcasts the new
 *   token over a BroadcastChannel so other tabs adopt it instead of refreshing.
 * - Before each authenticated request, refresh if the token expires within 30s.
 * - On 401 from an authenticated request: refresh once, retry once, then hand
 *   over to the `onUnauthorized` handler (set by the auth store).
 * - Only a 401/403 refresh response means "session gone" (resolves `null`).
 *   5xx / 429 / network failures throw an `ApiError` and leave auth state alone.
 * - Errors surface as `ApiError` with the server's `detail`, never raw fetch errors.
 */
import type { ErrorBody, RefreshResponse, User } from './types';

export const API_BASE = '/api';

export class ApiError extends Error {
	readonly status: number;
	readonly detail: string;
	readonly code: string | undefined;
	readonly retryAfter: number | undefined;

	constructor(status: number, detail: string, code?: string, retryAfter?: number) {
		super(detail);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
		this.code = code;
		this.retryAfter = retryAfter;
	}

	get isNetwork(): boolean {
		return this.status === 0;
	}
}

export function isAbortError(err: unknown): boolean {
	return err instanceof DOMException && err.name === 'AbortError';
}

export function toApiError(err: unknown): ApiError {
	if (err instanceof ApiError) return err;
	if (err instanceof Error) return new ApiError(0, err.message || 'Network error');
	return new ApiError(0, 'Unexpected error');
}

const NETWORK_MESSAGE = 'Could not reach the server. Check your connection.';

// ---- token state --------------------------------------------------------

let accessToken: string | null = null;
let accessExpiresAt = 0; // epoch ms
let lastUser: User | null = null;
let refreshInFlight: Promise<RefreshResponse | null> | null = null;
let unauthorizedHandler: (() => void) | null = null;
let refreshedHandler: ((r: RefreshResponse) => void) | null = null;
let remoteLogoutHandler: (() => void) | null = null;

/**
 * Logout epoch: bumped by `logout()` (locally or from another tab). A refresh that
 * resolves from an older epoch must not install its token or user.
 */
let epoch = 0;

const REFRESH_SKEW_MS = 30_000;
const LOCK_NAME = 'tunnbox-refresh';
const CHANNEL_NAME = 'tunnbox-auth';

type AuthMessage =
	{ type: 'token'; token: string; expiresAt: number; user: User } | { type: 'logout' } | { type: 'request' };

let adoptResolver: ((r: RefreshResponse) => void) | null = null;

const channel: BroadcastChannel | null =
	typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel(CHANNEL_NAME) : null;

if (channel) {
	channel.onmessage = (e: MessageEvent<AuthMessage>) => {
		const msg = e.data;
		if (!msg || typeof msg !== 'object') return;
		if (msg.type === 'token') {
			if (typeof msg.token !== 'string' || !Number.isFinite(msg.expiresAt)) return;
			accessToken = msg.token;
			accessExpiresAt = msg.expiresAt;
			lastUser = msg.user;
			const payload: RefreshResponse = {
				access_token: msg.token,
				expires_in: Math.max(0, Math.round((msg.expiresAt - Date.now()) / 1000)),
				user: msg.user
			};
			adoptResolver?.(payload);
			refreshedHandler?.(payload);
		} else if (msg.type === 'request') {
			// A tab that just opened asks whether anyone holds a fresh token.
			if (tokenIsFresh() && accessToken && lastUser)
				broadcast({ type: 'token', token: accessToken, expiresAt: accessExpiresAt, user: lastUser });
		} else if (msg.type === 'logout') {
			epoch += 1;
			clearAccessToken();
			remoteLogoutHandler?.();
		}
	};
}

function broadcast(msg: AuthMessage) {
	try {
		channel?.postMessage(msg);
	} catch {
		/* channel closed */
	}
}

export function setAccessToken(token: string, expiresInSeconds: number, user?: User): void {
	accessToken = token;
	accessExpiresAt = Date.now() + expiresInSeconds * 1000;
	if (user) lastUser = user;
}

export function clearAccessToken(): void {
	accessToken = null;
	accessExpiresAt = 0;
	lastUser = null;
}

export function hasAccessToken(): boolean {
	return accessToken !== null;
}

/**
 * Start a logout: bump the epoch so any refresh still in flight cannot install a
 * token afterwards, while keeping the current token for the logout request itself.
 */
export function beginLogout(): void {
	epoch += 1;
}

/** Finish a logout: drop the token here and tell every other tab to do the same. */
export function announceLogout(): void {
	epoch += 1;
	clearAccessToken();
	broadcast({ type: 'logout' });
}

/**
 * On boot, ask other tabs for their token before hitting `/auth/refresh`.
 * Resolves with the adopted payload, or `null` if nobody answered in time.
 */
export function adoptTokenFromTabs(timeoutMs = 150): Promise<RefreshResponse | null> {
	if (!channel) return Promise.resolve(null);
	return new Promise((resolve) => {
		const timer = setTimeout(() => {
			adoptResolver = null;
			resolve(null);
		}, timeoutMs);
		adoptResolver = (r) => {
			clearTimeout(timer);
			adoptResolver = null;
			resolve(r);
		};
		broadcast({ type: 'request' });
	});
}

/** Share a freshly issued token (login/setup) with other tabs. */
export function announceToken(token: string, expiresInSeconds: number, user: User): void {
	broadcast({ type: 'token', token, expiresAt: Date.now() + expiresInSeconds * 1000, user });
}

/** Called when a request cannot be authenticated even after a refresh. */
export function setUnauthorizedHandler(fn: (() => void) | null): void {
	unauthorizedHandler = fn;
}

/** Called after every successful refresh, including tokens adopted from other tabs. */
export function setRefreshedHandler(fn: ((r: RefreshResponse) => void) | null): void {
	refreshedHandler = fn;
}

/** Called when another tab logged out. */
export function setRemoteLogoutHandler(fn: (() => void) | null): void {
	remoteLogoutHandler = fn;
}

const CREDENTIALED_PATHS = ['/auth/refresh', '/auth/logout', '/auth/login', '/auth/setup'];

function needsCredentials(path: string): boolean {
	return CREDENTIALED_PATHS.some((p) => path === p || path.startsWith(p));
}

function tokenIsFresh(): boolean {
	return accessToken !== null && Date.now() < accessExpiresAt - REFRESH_SKEW_MS;
}

async function doRefresh(startEpoch: number): Promise<RefreshResponse | null> {
	// Another tab may have refreshed while we waited for the lock; adopt its token.
	if (tokenIsFresh() && accessToken && lastUser) {
		return {
			access_token: accessToken,
			expires_in: Math.round((accessExpiresAt - Date.now()) / 1000),
			user: lastUser
		};
	}
	let res: Response;
	try {
		res = await fetch(`${API_BASE}/auth/refresh`, {
			method: 'POST',
			credentials: 'include',
			headers: { Accept: 'application/json' }
		});
	} catch {
		throw new ApiError(0, NETWORK_MESSAGE);
	}
	if (res.status === 401 || res.status === 403) {
		if (epoch === startEpoch) clearAccessToken();
		return null;
	}
	if (!res.ok) throw await parseError(res);
	const data = (await res.json()) as RefreshResponse;
	if (epoch !== startEpoch) return null; // logged out meanwhile: discard
	setAccessToken(data.access_token, data.expires_in, data.user);
	broadcast({ type: 'token', token: data.access_token, expiresAt: accessExpiresAt, user: data.user });
	refreshedHandler?.(data);
	return data;
}

/**
 * Single-flight refresh. Resolves with the new token payload, `null` when the
 * session is gone (401/403), and throws an `ApiError` for anything else.
 */
export function refreshSession(): Promise<RefreshResponse | null> {
	if (refreshInFlight) return refreshInFlight;
	const startEpoch = epoch;
	const run = () => doRefresh(startEpoch);
	const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined;
	const pending: Promise<RefreshResponse | null> = locks
		? (locks.request(LOCK_NAME, run) as unknown as Promise<RefreshResponse | null>)
		: run();
	const tracked = pending.finally(() => {
		if (refreshInFlight === tracked) refreshInFlight = null;
	});
	refreshInFlight = tracked;
	return tracked;
}

// ---- request -----------------------------------------------------------

export type QueryValue = string | number | boolean | null | undefined;
export type Query = Record<string, QueryValue>;

export interface RequestOptions {
	method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
	body?: unknown;
	query?: Query;
	signal?: AbortSignal;
	/** Attach the bearer token and run the refresh/retry cycle. Default true. */
	auth?: boolean;
	/** Override the Accept header (e.g. `text/plain`). */
	accept?: string;
}

export function buildQuery(query?: Query): string {
	if (!query) return '';
	const params = new URLSearchParams();
	for (const [k, v] of Object.entries(query)) {
		if (v === undefined || v === null || v === '') continue;
		params.set(k, String(v));
	}
	const s = params.toString();
	return s ? `?${s}` : '';
}

async function parseError(res: Response): Promise<ApiError> {
	let detail = res.statusText || `Request failed (${res.status})`;
	let code: string | undefined;
	try {
		const body = (await res.json()) as Partial<ErrorBody> | { detail?: unknown };
		if (body && typeof body.detail === 'string') detail = body.detail;
		else if (body && Array.isArray(body.detail)) {
			// FastAPI validation error shape
			const first = body.detail[0] as { msg?: string; loc?: unknown[] } | undefined;
			if (first?.msg) detail = first.loc ? `${String(first.loc.at(-1))}: ${first.msg}` : first.msg;
		}
		if (body && 'code' in body && typeof body.code === 'string') code = body.code;
	} catch {
		/* non-JSON body */
	}
	const ra = res.headers.get('Retry-After');
	const retryAfter = ra ? Number(ra) : undefined;
	return new ApiError(res.status, detail, code, Number.isFinite(retryAfter) ? retryAfter : undefined);
}

async function rawFetch(path: string, opts: RequestOptions, token: string | null): Promise<Response> {
	const headers: Record<string, string> = { Accept: opts.accept ?? 'application/json' };
	if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
	if (token && opts.auth !== false) headers['Authorization'] = `Bearer ${token}`;
	try {
		return await fetch(`${API_BASE}${path}${buildQuery(opts.query)}`, {
			method: opts.method ?? 'GET',
			headers,
			body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
			signal: opts.signal,
			credentials: needsCredentials(path) ? 'include' : 'same-origin'
		});
	} catch (err) {
		if (isAbortError(err)) throw err;
		throw new ApiError(0, NETWORK_MESSAGE);
	}
}

/**
 * Perform a request and return the raw `Response` (status already checked).
 * Throws `ApiError` on non-2xx.
 */
export async function requestRaw(path: string, opts: RequestOptions = {}): Promise<Response> {
	const useAuth = opts.auth !== false;

	if (useAuth && accessToken && !tokenIsFresh()) {
		// Pre-emptive refresh. A transient failure here is not fatal: fall
		// through with the current token and let the real request decide.
		try {
			await refreshSession();
		} catch {
			/* handled by the 401 path below if the token really is stale */
		}
	}

	let res = await rawFetch(path, opts, useAuth ? accessToken : null);

	if (res.status === 401 && useAuth) {
		const refreshed = await refreshSession();
		if (refreshed) res = await rawFetch(path, opts, accessToken);
		if (res.status === 401) {
			clearAccessToken();
			unauthorizedHandler?.();
			throw await parseError(res);
		}
	}

	if (!res.ok) throw await parseError(res);
	return res;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
	const res = await requestRaw(path, opts);
	if (res.status === 204 || res.headers.get('content-length') === '0') return undefined as T;
	const ct = res.headers.get('content-type') ?? '';
	if (!ct.includes('json')) return undefined as T;
	return (await res.json()) as T;
}

export const get = <T>(path: string, query?: Query, signal?: AbortSignal) =>
	request<T>(path, { method: 'GET', query, signal });
export const post = <T>(path: string, body?: unknown, signal?: AbortSignal) =>
	request<T>(path, { method: 'POST', body, signal });
export const patch = <T>(path: string, body?: unknown, signal?: AbortSignal) =>
	request<T>(path, { method: 'PATCH', body, signal });
export const del = <T = void>(path: string, signal?: AbortSignal) =>
	request<T>(path, { method: 'DELETE', signal });

export async function getText(path: string, query?: Query, signal?: AbortSignal): Promise<string> {
	const res = await requestRaw(path, { query, signal, accept: 'text/plain' });
	return res.text();
}

export async function getBlob(path: string, query?: Query, signal?: AbortSignal): Promise<Blob> {
	const res = await requestRaw(path, { query, signal, accept: '*/*' });
	return res.blob();
}

/** Extract a filename from Content-Disposition, if the server set one. */
export function filenameFromResponse(res: Response, fallback: string): string {
	const cd = res.headers.get('content-disposition') ?? '';
	const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
	return m ? decodeURIComponent(m[1]) : fallback;
}

/** Fetch with bearer auth and trigger a browser download via a blob URL. */
export async function downloadFile(path: string, fallbackName: string, query?: Query): Promise<void> {
	const res = await requestRaw(path, { query, accept: '*/*' });
	const blob = await res.blob();
	const name = filenameFromResponse(res, fallbackName);
	const url = URL.createObjectURL(blob);
	try {
		const a = document.createElement('a');
		a.href = url;
		a.download = name;
		a.rel = 'noopener';
		a.style.display = 'none';
		document.body.appendChild(a);
		a.click();
		a.remove();
	} finally {
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}
}

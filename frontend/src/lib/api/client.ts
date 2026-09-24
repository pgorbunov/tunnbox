/**
 * Fetch wrapper for the TunnBox API.
 *
 * - Access token is held in a module-level variable only (never persisted).
 * - `/auth/refresh` is single-flight: concurrent callers share one promise.
 * - Before each authenticated request, refresh if the token expires within 30s.
 * - On 401 from an authenticated request: refresh once, retry once, then hand
 *   over to the `onUnauthorized` handler (set by the auth store).
 * - Errors surface as `ApiError` with the server's `detail`, never raw fetch errors.
 */
import type { ErrorBody, RefreshResponse } from './types';

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

// ---- token state --------------------------------------------------------

let accessToken: string | null = null;
let accessExpiresAt = 0; // epoch ms
let refreshInFlight: Promise<RefreshResponse | null> | null = null;
let unauthorizedHandler: (() => void) | null = null;
let refreshedHandler: ((r: RefreshResponse) => void) | null = null;

const REFRESH_SKEW_MS = 30_000;

export function setAccessToken(token: string, expiresInSeconds: number): void {
	accessToken = token;
	accessExpiresAt = Date.now() + expiresInSeconds * 1000;
}

export function clearAccessToken(): void {
	accessToken = null;
	accessExpiresAt = 0;
}

export function hasAccessToken(): boolean {
	return accessToken !== null;
}

/** Called when a request cannot be authenticated even after a refresh. */
export function setUnauthorizedHandler(fn: (() => void) | null): void {
	unauthorizedHandler = fn;
}

/** Called after every successful refresh (auth store keeps `user` fresh). */
export function setRefreshedHandler(fn: ((r: RefreshResponse) => void) | null): void {
	refreshedHandler = fn;
}

const CREDENTIALED_PATHS = ['/auth/refresh', '/auth/logout', '/auth/login', '/auth/setup'];

function needsCredentials(path: string): boolean {
	return CREDENTIALED_PATHS.some((p) => path === p || path.startsWith(p));
}

/**
 * Single-flight refresh. Resolves with the new token payload, or `null` when the
 * session is gone (401/403) — callers decide what to do with that.
 */
export function refreshSession(): Promise<RefreshResponse | null> {
	if (refreshInFlight) return refreshInFlight;
	refreshInFlight = (async () => {
		try {
			const res = await fetch(`${API_BASE}/auth/refresh`, {
				method: 'POST',
				credentials: 'include',
				headers: { Accept: 'application/json' }
			});
			if (!res.ok) {
				clearAccessToken();
				return null;
			}
			const data = (await res.json()) as RefreshResponse;
			setAccessToken(data.access_token, data.expires_in);
			refreshedHandler?.(data);
			return data;
		} catch {
			// Network failure: keep whatever token we had; the caller will surface the error.
			return null;
		} finally {
			refreshInFlight = null;
		}
	})();
	return refreshInFlight;
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
	return fetch(`${API_BASE}${path}${buildQuery(opts.query)}`, {
		method: opts.method ?? 'GET',
		headers,
		body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
		signal: opts.signal,
		credentials: needsCredentials(path) ? 'include' : 'same-origin'
	});
}

/**
 * Perform a request and return the raw `Response` (status already checked).
 * Throws `ApiError` on non-2xx.
 */
export async function requestRaw(path: string, opts: RequestOptions = {}): Promise<Response> {
	const useAuth = opts.auth !== false;

	if (useAuth && accessToken && Date.now() > accessExpiresAt - REFRESH_SKEW_MS) {
		await refreshSession();
	}

	let res: Response;
	try {
		res = await rawFetch(path, opts, useAuth ? accessToken : null);
	} catch (err) {
		if (isAbortError(err)) throw err;
		throw new ApiError(0, 'Could not reach the server. Check your connection.');
	}

	if (res.status === 401 && useAuth) {
		const refreshed = await refreshSession();
		if (refreshed) {
			try {
				res = await rawFetch(path, opts, accessToken);
			} catch (err) {
				if (isAbortError(err)) throw err;
				throw new ApiError(0, 'Could not reach the server. Check your connection.');
			}
		}
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

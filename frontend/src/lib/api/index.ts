/**
 * Typed endpoint functions, grouped by domain. Paths follow SPEC §2.7 exactly.
 */
import { del, downloadFile, get, getBlob, getText, patch, post, request } from './client';
import type {
	ApiKey,
	ApiKeyCreated,
	ApiKeyCreateRequest,
	AuditEntry,
	AuditQuery,
	AuthStatus,
	BulkRequest,
	BulkResponse,
	GlobalPeerQuery,
	Health,
	Interface,
	InterfaceCreateRequest,
	InterfaceUpdateRequest,
	LoginMfaRequest,
	LoginRequest,
	LoginResponse,
	LoginSuccess,
	MfaSetupResponse,
	NextIpResponse,
	Overview,
	Page,
	PasswordChangeRequest,
	Peer,
	PeerCreateRequest,
	PeerListQuery,
	PeerUpdateRequest,
	RecoveryCodesResponse,
	Session,
	Settings,
	SettingsUpdateRequest,
	SetupRequest,
	ShareCreated,
	ShareCreateRequest,
	SharePayload,
	StatsRange,
	StatsResponse,
	SystemInfo,
	User,
	UserCreateRequest,
	UserUpdateRequest
} from './types';

export { ApiError, isAbortError, toApiError } from './client';
export type * from './types';

const enc = encodeURIComponent;

export const auth = {
	status: (signal?: AbortSignal) => request<AuthStatus>('/auth/status', { auth: false, signal }),
	setup: (body: SetupRequest) => request<LoginSuccess>('/auth/setup', { method: 'POST', body, auth: false }),
	login: (body: LoginRequest) => request<LoginResponse>('/auth/login', { method: 'POST', body, auth: false }),
	loginMfa: (body: LoginMfaRequest) =>
		request<LoginSuccess>('/auth/login/mfa', { method: 'POST', body, auth: false }),
	logout: () => request<void>('/auth/logout', { method: 'POST' }),
	me: (signal?: AbortSignal) => get<User>('/auth/me', undefined, signal),
	changePassword: (body: PasswordChangeRequest) => patch<void>('/auth/me/password', body),
	sessions: (signal?: AbortSignal) => get<Session[]>('/auth/sessions', undefined, signal),
	revokeSession: (id: string) => del(`/auth/sessions/${enc(id)}`),
	revokeOtherSessions: () => del('/auth/sessions')
};

export const mfa = {
	setup: () => post<MfaSetupResponse>('/mfa/setup'),
	enable: (code: string) => post<RecoveryCodesResponse>('/mfa/enable', { code }),
	disable: (password: string, code: string) => post<void>('/mfa/disable', { password, code }),
	regenerateRecoveryCodes: (password: string) =>
		post<RecoveryCodesResponse>('/mfa/recovery-codes', { password })
};

export const apiKeys = {
	list: (all = false, signal?: AbortSignal) => get<ApiKey[]>('/api-keys', all ? { all: true } : undefined, signal),
	create: (body: ApiKeyCreateRequest) => post<ApiKeyCreated>('/api-keys', body),
	revoke: (id: number) => del(`/api-keys/${id}`)
};

export const users = {
	list: (signal?: AbortSignal) => get<User[]>('/users', undefined, signal),
	create: (body: UserCreateRequest) => post<User>('/users', body),
	update: (id: number, body: UserUpdateRequest) => patch<User>(`/users/${id}`, body),
	remove: (id: number) => del(`/users/${id}`),
	resetMfa: (id: number) => post<void>(`/users/${id}/mfa/reset`)
};

export const interfaces = {
	list: (signal?: AbortSignal) => get<Interface[]>('/interfaces', undefined, signal),
	create: (body: InterfaceCreateRequest) => post<Interface>('/interfaces', body),
	get: (name: string, signal?: AbortSignal) => get<Interface>(`/interfaces/${enc(name)}`, undefined, signal),
	update: (name: string, body: InterfaceUpdateRequest) => patch<Interface>(`/interfaces/${enc(name)}`, body),
	remove: (name: string) => del(`/interfaces/${enc(name)}`),
	up: (name: string) => post<Interface>(`/interfaces/${enc(name)}/up`),
	down: (name: string) => post<Interface>(`/interfaces/${enc(name)}/down`),
	config: (name: string) => getText(`/interfaces/${enc(name)}/config`),
	downloadConfig: (name: string) => downloadFile(`/interfaces/${enc(name)}/config`, `${name}.conf`),
	stats: (name: string, range: StatsRange, signal?: AbortSignal) =>
		get<StatsResponse>(`/interfaces/${enc(name)}/stats`, { range }, signal),
	peers: (name: string, query: PeerListQuery = {}, signal?: AbortSignal) =>
		get<Peer[]>(`/interfaces/${enc(name)}/peers`, { ...query }, signal),
	createPeer: (name: string, body: PeerCreateRequest) => post<Peer>(`/interfaces/${enc(name)}/peers`, body),
	nextIp: (name: string, signal?: AbortSignal) =>
		get<NextIpResponse>(`/interfaces/${enc(name)}/next-ip`, undefined, signal)
};

export const peers = {
	search: (query: GlobalPeerQuery = {}, signal?: AbortSignal) => get<Page<Peer>>('/peers', { ...query }, signal),
	get: (id: number, signal?: AbortSignal) => get<Peer>(`/peers/${id}`, undefined, signal),
	update: (id: number, body: PeerUpdateRequest) => patch<Peer>(`/peers/${id}`, body),
	remove: (id: number) => del(`/peers/${id}`),
	enable: (id: number) => post<Peer>(`/peers/${id}/enable`),
	disable: (id: number) => post<Peer>(`/peers/${id}/disable`),
	rotateKeys: (id: number) => post<Peer>(`/peers/${id}/rotate-keys`),
	config: (id: number, allowedIps?: string, signal?: AbortSignal) =>
		getText(`/peers/${id}/config`, allowedIps ? { allowed_ips: allowedIps } : undefined, signal),
	downloadConfig: (id: number, name: string, allowedIps?: string) =>
		downloadFile(`/peers/${id}/config`, `${name}.conf`, allowedIps ? { allowed_ips: allowedIps } : undefined),
	qr: (id: number, allowedIps?: string, signal?: AbortSignal) =>
		getBlob(`/peers/${id}/qr`, allowedIps ? { allowed_ips: allowedIps } : undefined, signal),
	share: (id: number, body: ShareCreateRequest = {}) => post<ShareCreated>(`/peers/${id}/share`, body),
	stats: (id: number, range: StatsRange, signal?: AbortSignal) =>
		get<StatsResponse>(`/peers/${id}/stats`, { range }, signal),
	bulk: (body: BulkRequest) => post<BulkResponse>('/peers/bulk', body)
};

export const share = {
	get: (token: string, signal?: AbortSignal) =>
		request<SharePayload>(`/share/${enc(token)}`, { auth: false, signal })
};

export const stats = {
	overview: (range: StatsRange = '24h', signal?: AbortSignal) =>
		get<Overview>('/stats/overview', { range }, signal)
};

export const audit = {
	list: (query: AuditQuery = {}, signal?: AbortSignal) => get<Page<AuditEntry>>('/audit', { ...query }, signal),
	actions: (signal?: AbortSignal) => get<string[]>('/audit/actions', undefined, signal),
	exportCsv: (query: AuditQuery = {}) => downloadFile('/audit/export.csv', 'audit.csv', { ...query })
};

export const settings = {
	get: (signal?: AbortSignal) => get<Settings>('/settings', undefined, signal),
	update: (body: SettingsUpdateRequest) => patch<Settings>('/settings', body)
};

export const system = {
	health: (signal?: AbortSignal) => request<Health>('/system/health', { auth: false, signal }),
	info: (signal?: AbortSignal) => get<SystemInfo>('/system/info', undefined, signal),
	downloadBackup: () => downloadFile('/system/backup', 'tunnbox-backup.tar.gz'),
	downloadExport: () => downloadFile('/system/export', 'tunnbox-export.json')
};

export const api = { auth, mfa, apiKeys, users, interfaces, peers, share, stats, audit, settings, system };
export default api;

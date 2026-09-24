/**
 * API types — mirror of SPEC §2.7. Field names and shapes are the binding contract.
 */

export type Role = 'admin' | 'operator' | 'viewer';

export interface User {
	id: number;
	username: string;
	role: Role;
	is_active: boolean;
	totp_enabled: boolean;
	last_login_at: string | null;
	created_at: string;
}

export interface Interface {
	id: number;
	name: string;
	public_key: string;
	address: string;
	listen_port: number;
	dns: string | null;
	mtu: number | null;
	post_up: string | null;
	post_down: string | null;
	public_endpoint: string | null;
	enabled: boolean;
	is_active: boolean;
	peer_count: number;
	online_peer_count: number;
	rx_total: number;
	tx_total: number;
	created_at: string;
	updated_at: string;
}

export type PeerStatus = 'online' | 'offline' | 'disabled' | 'expired';

export interface Peer {
	id: number;
	interface_id: number;
	interface_name: string;
	name: string;
	public_key: string;
	allowed_ips: string;
	client_allowed_ips: string;
	client_dns: string | null;
	persistent_keepalive: number;
	enabled: boolean;
	expires_at: string | null;
	notes: string | null;
	has_private_key: boolean;
	has_preshared_key: boolean;
	endpoint: string | null;
	latest_handshake_at: string | null;
	is_online: boolean;
	rx_total: number;
	tx_total: number;
	created_at: string;
	updated_at: string;
	status: PeerStatus;
}

export interface Session {
	id: string;
	ip: string | null;
	user_agent: string | null;
	created_at: string;
	last_used_at: string;
	expires_at: string;
	current: boolean;
}

export interface ApiKey {
	id: number;
	name: string;
	prefix: string;
	scopes: string[];
	expires_at: string | null;
	last_used_at: string | null;
	created_at: string;
	revoked_at: string | null;
}

export type ApiKeyScope = 'read' | 'peers:write' | 'interfaces:write' | 'admin';

export interface AuditEntry {
	id: number;
	user_id: number | null;
	username: string | null;
	action: string;
	target: string | null;
	details: Record<string, unknown> | null;
	ip: string | null;
	created_at: string;
}

export interface Page<T> {
	items: T[];
	total: number;
	page: number;
	page_size: number;
}

// ---- Auth --------------------------------------------------------------

export interface AuthStatus {
	setup_required: boolean;
	version: string;
}

export interface LoginSuccess {
	access_token: string;
	token_type: 'bearer';
	expires_in: number;
	user: User;
}

export interface MfaRequired {
	mfa_required: true;
	mfa_token: string;
}

export type LoginResponse = LoginSuccess | MfaRequired;

export interface RefreshResponse {
	access_token: string;
	expires_in: number;
	user: User;
}

export interface SetupRequest {
	username: string;
	password: string;
}

export interface LoginRequest {
	username: string;
	password: string;
}

export interface LoginMfaRequest {
	mfa_token: string;
	code: string;
}

export interface PasswordChangeRequest {
	current_password: string;
	new_password: string;
}

// ---- MFA ---------------------------------------------------------------

export interface MfaSetupRequest {
	password: string;
}

export interface MfaEnableRequest {
	code: string;
	password: string;
}

export interface MfaSetupResponse {
	secret: string;
	otpauth_uri: string;
	qr_svg: string;
}

export interface RecoveryCodesResponse {
	recovery_codes: string[];
}

// ---- API keys ----------------------------------------------------------

export interface ApiKeyCreateRequest {
	name: string;
	scopes: string[];
	expires_at?: string | null;
}

export type ApiKeyCreated = ApiKey & { key: string };

// ---- Users -------------------------------------------------------------

export interface UserCreateRequest {
	username: string;
	password: string;
	role: Role;
}

export interface UserUpdateRequest {
	role?: Role;
	is_active?: boolean;
	password?: string;
}

// ---- Interfaces --------------------------------------------------------

export interface InterfaceCreateRequest {
	name: string;
	address: string;
	listen_port: number;
	dns?: string | null;
	mtu?: number | null;
	post_up?: string | null;
	post_down?: string | null;
	public_endpoint?: string | null;
	enabled?: boolean;
}

export interface InterfaceUpdateRequest {
	address?: string;
	listen_port?: number;
	dns?: string | null;
	mtu?: number | null;
	post_up?: string | null;
	post_down?: string | null;
	public_endpoint?: string | null;
	enabled?: boolean;
}

export type StatsRange = '1h' | '6h' | '24h' | '7d' | '30d';

export interface StatsPoint {
	ts: string;
	rx: number;
	tx: number;
	online: boolean;
}

export interface StatsResponse {
	range: StatsRange;
	bucket_seconds: number;
	points: StatsPoint[];
	rx_total: number;
	tx_total: number;
}

// ---- Peers -------------------------------------------------------------

export type PeerSort = 'name' | 'handshake' | 'rx' | 'tx' | 'created';
export type SortOrder = 'asc' | 'desc';

export interface PeerListQuery {
	q?: string;
	status?: PeerStatus | '';
	sort?: PeerSort;
	order?: SortOrder;
}

export interface GlobalPeerQuery {
	q?: string;
	interface?: string;
	status?: PeerStatus | '';
	page?: number;
	page_size?: number;
}

export interface PeerCreateRequest {
	name: string;
	allowed_ips?: 'auto' | string;
	client_allowed_ips?: string;
	client_dns?: string | null;
	persistent_keepalive?: number;
	expires_at?: string | null;
	notes?: string | null;
	enabled?: boolean;
}

export interface PeerUpdateRequest {
	name?: string;
	allowed_ips?: string;
	client_allowed_ips?: string;
	client_dns?: string | null;
	persistent_keepalive?: number;
	expires_at?: string | null;
	notes?: string | null;
	enabled?: boolean;
}

export interface NextIpResponse {
	allowed_ips: string;
}

export interface ShareCreateRequest {
	expires_in_hours?: number;
	max_uses?: number;
}

export interface ShareCreated {
	url_path: string;
	token: string;
	expires_at: string;
	max_uses: number;
}

export type BulkAction = 'enable' | 'disable' | 'delete';

export interface BulkRequest {
	ids: number[];
	action: BulkAction;
}

export interface BulkResponse {
	affected: number;
}

// ---- Share (public) ----------------------------------------------------

export interface SharePayload {
	peer_name: string;
	interface_name: string;
	expires_at: string;
	remaining_uses: number;
	config: string;
	qr_png_base64: string;
}

// ---- Stats / dashboard -------------------------------------------------

export interface OverviewSeriesPoint {
	ts: string;
	rx: number;
	tx: number;
}

export interface TopPeer {
	peer_id: number;
	name: string;
	interface_name: string;
	rx: number;
	tx: number;
}

export interface Overview {
	interfaces_total: number;
	interfaces_active: number;
	peers_total: number;
	peers_online: number;
	peers_disabled: number;
	peers_expiring_7d: number;
	rx_total: number;
	tx_total: number;
	series: OverviewSeriesPoint[];
	top_peers: TopPeer[];
	recent_activity: AuditEntry[];
}

// ---- Audit -------------------------------------------------------------

export interface AuditQuery {
	page?: number;
	page_size?: number;
	action?: string;
	username?: string;
	q?: string;
	from?: string;
	to?: string;
}

// ---- Settings ----------------------------------------------------------

export interface Settings {
	public_endpoint: string;
	default_dns: string;
	default_mtu: number | null;
	default_keepalive: number;
	default_client_allowed_ips: string;
	audit_retention_days: number;
	stats_retention_days: number;
	ui_refresh_seconds: number;
	custom_scripts_allowed: boolean;
}

export type SettingsUpdateRequest = Partial<Omit<Settings, 'custom_scripts_allowed'>>;

// ---- System ------------------------------------------------------------

export interface Health {
	status: 'ok';
}

export interface SystemInfo {
	version: string;
	backend_mode: 'real' | 'mock';
	wireguard_version: string | null;
	kernel_module: boolean;
	python_version: string;
	os: string;
	uptime_seconds: number;
	database_size_bytes: number;
	config_path: string;
	hostname: string;
}

// ---- Errors ------------------------------------------------------------

export interface ErrorBody {
	detail: string;
	code?: string;
}

const API_BASE = '/api';

interface ApiError {
	detail: string;
}

class ApiClient {
	private accessToken: string | null = null;

	setAccessToken(token: string | null) {
		this.accessToken = token;
		if (token) {
			localStorage.setItem('access_token', token);
		} else {
			localStorage.removeItem('access_token');
		}
	}

	getAccessToken(): string | null {
		if (!this.accessToken) {
			this.accessToken = localStorage.getItem('access_token');
		}
		return this.accessToken;
	}

	private async request<T>(
		endpoint: string,
		options: RequestInit = {}
	): Promise<T> {
		const url = `${API_BASE}${endpoint}`;
		const headers: HeadersInit = {
			'Content-Type': 'application/json',
			...options.headers
		};

		const token = this.getAccessToken();
		if (token) {
			(headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
		}

		const response = await fetch(url, {
			...options,
			headers,
			credentials: 'include'
		});

		if (response.status === 401) {
			// Try to refresh token
			const refreshed = await this.refreshToken();
			if (refreshed) {
				// Retry the request
				const newHeaders = { ...headers };
				(newHeaders as Record<string, string>)['Authorization'] = `Bearer ${this.accessToken}`;
				const retryResponse = await fetch(url, {
					...options,
					headers: newHeaders,
					credentials: 'include'
				});
				if (!retryResponse.ok) {
					const error: ApiError = await retryResponse.json().catch(() => ({ detail: 'Request failed' }));
					throw new Error(error.detail);
				}
				return retryResponse.json();
			}
			// Refresh failed, clear token
			this.setAccessToken(null);
			throw new Error('Session expired. Please login again.');
		}

		if (!response.ok) {
			const error: ApiError = await response.json().catch(() => ({ detail: 'Request failed' }));
			throw new Error(error.detail);
		}

		if (response.status === 204) {
			return undefined as T;
		}

		return response.json();
	}

	private async refreshToken(): Promise<boolean> {
		try {
			const response = await fetch(`${API_BASE}/auth/refresh`, {
				method: 'POST',
				credentials: 'include'
			});
			if (response.ok) {
				const data = await response.json();
				this.setAccessToken(data.access_token);
				return true;
			}
		} catch {
			// Refresh failed
		}
		return false;
	}

	// Auth endpoints
	async login(username: string, password: string) {
		const formData = new URLSearchParams();
		formData.append('username', username);
		formData.append('password', password);

		const response = await fetch(`${API_BASE}/auth/login`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: formData,
			credentials: 'include'
		});

		if (!response.ok) {
			const error: ApiError = await response.json().catch(() => ({ detail: 'Login failed' }));
			throw new Error(error.detail);
		}

		const data = await response.json();
		this.setAccessToken(data.access_token);
		return data;
	}

	async logout() {
		try {
			await this.request('/auth/logout', { method: 'POST' });
		} finally {
			this.setAccessToken(null);
		}
	}

	async getCurrentUser() {
		return this.request<{ id: number; username: string; is_admin: boolean }>('/auth/me');
	}

	async checkSetup() {
		const response = await fetch(`${API_BASE}/auth/check-setup`);
		return response.json();
	}

	async setup(username: string, password: string) {
		const response = await fetch(`${API_BASE}/auth/setup`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, password })
		});
		if (!response.ok) {
			const error: ApiError = await response.json().catch(() => ({ detail: 'Setup failed' }));
			throw new Error(error.detail);
		}
		return response.json();
	}

	// Interface endpoints
	async getInterfaces() {
		return this.request<Interface[]>('/interfaces');
	}

	async getInterface(name: string) {
		return this.request<Interface>(`/interfaces/${name}`);
	}

	async createInterface(data: InterfaceCreate) {
		return this.request<Interface>('/interfaces', {
			method: 'POST',
			body: JSON.stringify(data)
		});
	}

	async updateInterface(name: string, data: Partial<InterfaceCreate>) {
		return this.request<Interface>(`/interfaces/${name}`, {
			method: 'PUT',
			body: JSON.stringify(data)
		});
	}

	async deleteInterface(name: string) {
		return this.request<void>(`/interfaces/${name}`, { method: 'DELETE' });
	}

	async bringInterfaceUp(name: string) {
		return this.request<{ message: string }>(`/interfaces/${name}/up`, { method: 'POST' });
	}

	async bringInterfaceDown(name: string) {
		return this.request<{ message: string }>(`/interfaces/${name}/down`, { method: 'POST' });
	}

	async getInterfaceStats(name: string) {
		return this.request<InterfaceStats>(`/interfaces/${name}/stats`);
	}

	// Peer endpoints
	async getPeers(interfaceName: string) {
		return this.request<Peer[]>(`/interfaces/${interfaceName}/peers`);
	}

	async addPeer(interfaceName: string, data: PeerCreate) {
		return this.request<Peer>(`/interfaces/${interfaceName}/peers`, {
			method: 'POST',
			body: JSON.stringify(data)
		});
	}

	async updatePeer(interfaceName: string, publicKey: string, data: Partial<PeerCreate>) {
		return this.request<Peer>(`/interfaces/${interfaceName}/peers/${encodeURIComponent(publicKey)}`, {
			method: 'PUT',
			body: JSON.stringify(data)
		});
	}

	async deletePeer(interfaceName: string, publicKey: string) {
		return this.request<void>(`/interfaces/${interfaceName}/peers/${encodeURIComponent(publicKey)}`, {
			method: 'DELETE'
		});
	}

	async getPeerConfig(interfaceName: string, publicKey: string): Promise<string> {
		const response = await fetch(
			`${API_BASE}/interfaces/${interfaceName}/peers/config/${encodeURIComponent(publicKey)}`,
			{
				headers: {
					Authorization: `Bearer ${this.getAccessToken()}`
				},
				credentials: 'include'
			}
		);
		if (!response.ok) {
			const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to get config' }));
			throw new Error(error.detail);
		}
		return response.text();
	}

	async getPeerQRBlob(interfaceName: string, publicKey: string): Promise<string> {
		// Get a signed token for QR access
		const response = await this.request<{ qr_token: string }>(
			`/interfaces/${interfaceName}/peers/qr/${encodeURIComponent(publicKey)}`,
			{ method: 'POST' }
		);
		// POST token in body instead of URL to avoid exposure in logs/history
		const qrResponse = await fetch(`${API_BASE}/qr-image`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ token: response.qr_token })
		});
		if (!qrResponse.ok) {
			throw new Error('Failed to load QR image');
		}
		const blob = await qrResponse.blob();
		return URL.createObjectURL(blob);
	}

	async getNextAvailableIP(interfaceName: string) {
		return this.request<{ next_ip: string }>(`/interfaces/${interfaceName}/next-ip`);
	}

	// Settings
	async getSettings() {
		return this.request<ServerSettings>('/settings');
	}

	async updateSettings(settings: ServerSettingsUpdate) {
		return this.request<ServerSettings>('/settings', {
			method: 'PATCH',
			body: JSON.stringify(settings)
		});
	}

	// System
	async getSystemInfo() {
		return this.request<SystemInfo>('/system/info');
	}

	// Privacy & Data
	async exportAllData(): Promise<Blob> {
		const token = this.getAccessToken();
		const response = await fetch(`${API_BASE}/privacy/export`, {
			headers: {
				Authorization: `Bearer ${token}`
			},
			credentials: 'include'
		});
		if (!response.ok) {
			const error: ApiError = await response.json().catch(() => ({ detail: 'Export failed' }));
			throw new Error(error.detail);
		}
		return response.blob();
	}

	async getRetentionSettings() {
		return this.request<DataRetentionSettings>('/settings/retention');
	}

	async updateRetentionSettings(settings: DataRetentionSettings) {
		return this.request<DataRetentionSettings>('/settings/retention', {
			method: 'PATCH',
			body: JSON.stringify(settings)
		});
	}

	async getTimezone() {
		return this.request<TimezonePreference>('/settings/timezone');
	}

	async updateTimezone(timezone: string) {
		return this.request<TimezonePreference>('/settings/timezone', {
			method: 'PATCH',
			body: JSON.stringify({ timezone })
		});
	}
}

// Types
export interface Interface {
	name: string;
	listen_port: number;
	address: string;
	public_key: string;
	is_active: boolean;
	peer_count: number;
	active_peer_count: number;
	total_transfer_rx: number;
	total_transfer_tx: number;
	dns?: string;
	post_up?: string;
	post_down?: string;
}

export interface InterfaceCreate {
	name: string;
	listen_port: number;
	address: string;
	dns?: string;
	post_up?: string;
	post_down?: string;
}

export interface InterfaceStats {
	name: string;
	is_active: boolean;
	peer_count: number;
	total_transfer_rx: number;
	total_transfer_tx: number;
	peers: {
		public_key: string;
		endpoint?: string;
		latest_handshake?: string;
		transfer_rx: number;
		transfer_tx: number;
	}[];
}

export interface Peer {
	name: string;
	public_key: string;
	allowed_ips: string;
	endpoint?: string;
	latest_handshake?: string;
	transfer_rx: number;
	transfer_tx: number;
	is_online: boolean;
	persistent_keepalive: number;
}

export interface PeerCreate {
	name: string;
	allowed_ips: string;
	persistent_keepalive?: number;
}

export interface ServerSettings {
	public_endpoint: string;
	wg_default_dns: string;
	wg_config_path: string;
}

export interface ServerSettingsUpdate {
	public_endpoint?: string;
	wg_default_dns?: string;
}

export interface SystemInfo {
	frontend_version: string;
	backend_version: string;
	wireguard_version: string | null;
	docker_version: string | null;
	os_name: string;
	os_version: string;
	python_version: string;
	database_type: string;
	github_url: string;
	documentation_url: string;
	license: string;
}

export interface DataRetentionSettings {
	enabled: boolean;
	logs_retention_days: number;
}

export interface TimezonePreference {
	timezone: string;
}

export const api = new ApiClient();

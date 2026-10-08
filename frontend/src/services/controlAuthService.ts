import { API_BASE_URL } from '../config';

export const CONTROL_AUTH_STORAGE_KEY = 'deploy_control_auth';

export type ControlRole = 'admin' | 'developer' | 'tester' | 'viewer';
export type ControlPermission =
    | 'create_test'
    | 'run_test'
    | 'view_results'
    | 'manage_users'
    | 'manage_projects'
    | 'api_access'
    | 'deploy_view'
    | 'deploy_request'
    | 'deploy_approve'
    | 'admin';

export interface ControlAuthSession {
    token: string;
    expires_at?: string;
}

export interface ControlAuthProfile {
    user_id: string;
    username: string;
    email: string;
    role: ControlRole;
    project_ids: string[];
    permissions: ControlPermission[];
    token: string;
    expires_at?: string;
}

const ROLE_PERMISSIONS: Record<ControlRole, ControlPermission[]> = {
    admin: [
        'create_test',
        'run_test',
        'view_results',
        'manage_users',
        'manage_projects',
        'api_access',
        'deploy_view',
        'deploy_request',
        'deploy_approve',
        'admin',
    ],
    developer: ['create_test', 'run_test', 'view_results', 'api_access', 'deploy_view', 'deploy_request'],
    tester: ['run_test', 'view_results', 'deploy_view'],
    viewer: ['view_results'],
};

const toHeaders = (headers?: HeadersInit): Headers => {
    if (headers instanceof Headers) return new Headers(headers);
    return new Headers(headers || {});
};

const parseStoredSession = (): ControlAuthSession | null => {
    try {
        const raw = localStorage.getItem(CONTROL_AUTH_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as ControlAuthSession;
        if (!parsed?.token) return null;
        return parsed;
    } catch {
        return null;
    }
};

async function ensureJsonResponse<T>(response: Response): Promise<T> {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = typeof payload === 'object' && payload && 'detail' in payload
            ? String((payload as Record<string, unknown>).detail)
            : `Request failed (${response.status})`;
        throw new Error(detail);
    }
    return payload as T;
}

export function getStoredControlAuthSession(): ControlAuthSession | null {
    return parseStoredSession();
}

export function getStoredControlAuthToken(): string {
    return parseStoredSession()?.token || '';
}

export function saveControlAuthSession(session: ControlAuthSession): void {
    localStorage.setItem(CONTROL_AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearControlAuthSession(): void {
    localStorage.removeItem(CONTROL_AUTH_STORAGE_KEY);
}

export function getControlAuthHeaders(headers?: HeadersInit): Headers {
    const merged = toHeaders(headers);
    const token = getStoredControlAuthToken();
    if (token && !merged.has('Authorization')) {
        merged.set('Authorization', `Bearer ${token}`);
    }
    return merged;
}

export function hasControlPermission(
    profile: ControlAuthProfile | null | undefined,
    permission: ControlPermission,
): boolean {
    return Boolean(profile && profile.permissions.includes(permission));
}

export async function fetchControlAuthProfile(token = getStoredControlAuthToken()): Promise<ControlAuthProfile | null> {
    const url = token
        ? `${API_BASE_URL}/api/auth/me?token=${encodeURIComponent(token)}`
        : `${API_BASE_URL}/api/auth/me`;
    const response = await fetch(url);
    if (response.status === 401) {
        return null;
    }
    const payload = await ensureJsonResponse<{
        status: string;
        user: {
            user_id: string;
            username: string;
            email: string;
            role: ControlRole;
            project_ids: string[];
            permissions?: ControlPermission[];
        };
    }>(response);

    const user = payload.user;
    return {
        ...user,
        permissions: user.permissions || ROLE_PERMISSIONS[user.role] || [],
        token,
        expires_at: getStoredControlAuthSession()?.expires_at,
    };
}

export async function loginControl(username: string, password: string): Promise<ControlAuthProfile> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    const payload = await ensureJsonResponse<{
        status: string;
        token: string;
        expires_at?: string;
    }>(response);

    saveControlAuthSession({ token: payload.token, expires_at: payload.expires_at });
    const profile = await fetchControlAuthProfile(payload.token);
    if (!profile) {
        throw new Error("Login succeeded, but the current user could not be loaded");
    }
    return {
        ...profile,
        expires_at: payload.expires_at,
    };
}

export async function attachControlToken(token: string): Promise<ControlAuthProfile> {
    saveControlAuthSession({ token });
    try {
        const profile = await fetchControlAuthProfile(token);
        if (!profile) {
            throw new Error("Invalid token");
        }
        return profile;
    } catch (error) {
        clearControlAuthSession();
        throw error;
    }
}

export async function logoutControl(): Promise<void> {
    const session = getStoredControlAuthSession();
    try {
        if (session?.token) {
            await fetch(`${API_BASE_URL}/api/auth/logout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: session.token }),
            });
        }
    } finally {
        clearControlAuthSession();
    }
}

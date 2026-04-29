import {
    attachControlToken,
    clearControlAuthSession,
    fetchControlAuthProfile,
    getControlAuthHeaders,
    getStoredControlAuthSession,
    getStoredControlAuthToken,
    hasControlPermission,
    loginControl,
    logoutControl,
    saveControlAuthSession,
    type ControlAuthProfile,
    type ControlAuthSession,
    type ControlPermission,
    type ControlRole,
} from './controlAuthService';

export type DeployRole = ControlRole;
export type DeployPermission = ControlPermission;
export type DeployAuthSession = ControlAuthSession;
export type DeployAuthProfile = ControlAuthProfile;

const DEPLOY_PERMISSIONS: DeployPermission[] = ['deploy_view', 'deploy_request', 'deploy_approve', 'admin'];

function toDeployProfile(profile: ControlAuthProfile | null): DeployAuthProfile | null {
    if (!profile) return null;
    return {
        ...profile,
        permissions: profile.permissions.filter((permission) => DEPLOY_PERMISSIONS.includes(permission)),
    };
}

export const getStoredDeployAuthSession = getStoredControlAuthSession;
export const getStoredDeployAuthToken = getStoredControlAuthToken;
export const saveDeployAuthSession = saveControlAuthSession;
export const clearDeployAuthSession = clearControlAuthSession;
export const getDeployAuthHeaders = getControlAuthHeaders;
export const hasDeployPermission = hasControlPermission;
export async function fetchDeployAuthProfile(token = getStoredDeployAuthToken()): Promise<DeployAuthProfile | null> {
    return toDeployProfile(await fetchControlAuthProfile(token));
}

export async function loginDeployControl(username: string, password: string): Promise<DeployAuthProfile> {
    const profile = await loginControl(username, password);
    return toDeployProfile(profile) as DeployAuthProfile;
}

export async function attachDeployToken(token: string): Promise<DeployAuthProfile> {
    const profile = await attachControlToken(token);
    return toDeployProfile(profile) as DeployAuthProfile;
}

export const logoutDeployControl = logoutControl;

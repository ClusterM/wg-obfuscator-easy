import api from './api';

// Get web prefix from window (injected by Flask server)
const WEB_PREFIX = (window as any).__WEB_PREFIX__ || '';

export const isAuthEnabled = (): boolean => {
  if (typeof (window as any).__AUTH_ENABLED__ === 'boolean') {
    return (window as any).__AUTH_ENABLED__;
  }
  return true;
};

export const isAuthenticated = (): boolean => {
  if (!isAuthEnabled()) {
    return true;
  }
  return !!localStorage.getItem('auth_token');
};

export const loadAuthStatus = async (): Promise<boolean> => {
  if (typeof (window as any).__AUTH_ENABLED__ === 'boolean') {
    return (window as any).__AUTH_ENABLED__;
  }
  try {
    const data = await api.getAuthStatus();
    (window as any).__AUTH_ENABLED__ = data.enabled !== false;
  } catch {
    (window as any).__AUTH_ENABLED__ = true;
  }
  return (window as any).__AUTH_ENABLED__;
};

export const login = async (username: string, password: string) => {
  try {
    await api.login(username, password);
    return true;
  } catch (error: any) {
    throw new Error(error.response?.data?.error || 'Login failed');
  }
};

export const logout = () => {
  api.logout();
  window.location.href = WEB_PREFIX + '/login';
};

export const changePassword = async (currentPassword: string, newPassword: string) => {
  try {
    await api.changePassword(currentPassword, newPassword);
    return true;
  } catch (error: any) {
    throw new Error(error.response?.data?.error || 'Failed to change password');
  }
};


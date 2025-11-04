import api from './api';

// Get web prefix from window (injected by Flask server)
const WEB_PREFIX = (window as any).__WEB_PREFIX__ || '';

export const isAuthenticated = (): boolean => {
  return !!localStorage.getItem('auth_token');
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


import axios, { AxiosInstance } from 'axios';

// Get web prefix from window (injected by Flask server)
// Default to empty string if not set (for development or no prefix)
const WEB_PREFIX = (window as any).__WEB_PREFIX__ || '';
const API_BASE_URL = WEB_PREFIX + '/api';

class ApiService {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load token from localStorage
    this.token = localStorage.getItem('auth_token');
    if (this.token) {
      this.setToken(this.token);
    }

    // Handle responses and errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // Handle 401 responses
        if (error.response?.status === 401) {
          this.clearToken();
          // Don't redirect if we're already on the login page (prevents page reload on login error)
          const loginPath = WEB_PREFIX + '/login';
          if (!window.location.pathname.endsWith('/login')) {
            window.location.href = loginPath;
          }
        }
        
        // Extract error message from response if available
        if (error.response?.data?.error) {
          // Create a new error with the server's error message and "Error: " prefix
          const serverError = new Error(`Error: ${error.response.data.error}`);
          // Preserve the original error response for compatibility
          (serverError as any).response = error.response;
          return Promise.reject(serverError);
        }
        
        return Promise.reject(error);
      }
    );
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('auth_token', token);
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
    delete this.client.defaults.headers.common['Authorization'];
  }

  // Auth endpoints
  async login(username: string, password: string) {
    const response = await this.client.post('/auth/login', { username, password });
    if (response.data.access_token || response.data.token) {
      this.setToken(response.data.access_token || response.data.token);
    }
    return response.data;
  }

  async logout() {
    this.clearToken();
  }

  async changePassword(currentPassword: string, newPassword: string) {
    return this.client.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  // Status endpoints
  async getStatus() {
    const response = await this.client.get('/status');
    return response.data;
  }

  async getStats() {
    const response = await this.client.get('/stats');
    return response.data;
  }

  async getClientStats(username: string) {
    const response = await this.client.get(`/stats/${username}`);
    return response.data;
  }

  async getObfuscatorLogs(lines: number = 100) {
    const response = await this.client.get(`/logs/obfuscator?lines=${lines}`);
    return response.data;
  }

  // Config endpoints
  async getConfig() {
    const response = await this.client.get('/config');
    return response.data;
  }

  async updateConfig(config: any) {
    const response = await this.client.patch('/config', config);
    return response.data;
  }

  async regenerateServerKeys() {
    const response = await this.client.post('/config/regenerate-keys');
    return response.data;
  }

  // System endpoints
  async getSystemTimezone() {
    const response = await this.client.get('/system/timezone');
    return response.data;
  }

  async setSystemTimezone(timezone: string) {
    const response = await this.client.patch('/system/timezone', { timezone });
    return response.data;
  }

  async restartSystem() {
    const response = await this.client.post('/system/restart');
    return response.data;
  }

  // Auth endpoints
  async getCredentials() {
    const response = await this.client.get('/auth/credentials');
    return response.data;
  }

  async changeCredentials(oldPassword: string, newUsername?: string, newPassword?: string) {
    const payload: any = { old_password: oldPassword };
    if (newUsername) {
      payload.new_username = newUsername;
    }
    if (newPassword) {
      payload.new_password = newPassword;
    }
    const response = await this.client.post('/auth/change-credentials', payload);
    return response.data;
  }

  // Client endpoints
  async getClients() {
    const response = await this.client.get('/clients');
    return response.data;
  }

  async getClient(username: string) {
    const response = await this.client.get(`/clients/${username}`);
    return response.data;
  }

  async createClient(username: string, obfuscation: boolean = true, enabled: boolean = true) {
    const response = await this.client.post('/clients', {
      username,
      obfuscation,
      enabled,
    });
    return response.data;
  }

  async updateClient(username: string, data: any) {
    const response = await this.client.patch(`/clients/${username}`, data);
    return response.data;
  }

  async getAllTimeTrafficStats(username: string): Promise<any> {
    const response = await this.client.get(`/clients/${username}/traffic-stats/all-time`);
    return response.data;
  }

  async clearClientAllTimeStats(username: string): Promise<void> {
    await this.client.post(`/clients/${username}/traffic-stats/clear-all-time`);
  }

  async deleteClient(username: string) {
    const response = await this.client.delete(`/clients/${username}`);
    return response.data;
  }

  async regenerateClientKeys(username: string) {
    const response = await this.client.post(`/clients/${username}/regenerate-keys`);
    return response.data;
  }

  async getClientConfig(username: string, type: 'wireguard' | 'obfuscator' = 'wireguard'): Promise<string> {
    const response = await this.client.get(`/clients/${username}/config/${type}`, {
      responseType: 'text',
    });
    return response.data;
  }

  async downloadClientConfig(username: string, type: 'wireguard' | 'obfuscator' = 'wireguard') {
    try {
      const response = await this.client.get(`/clients/${username}/config/${type}`, {
        responseType: 'blob',
        validateStatus: () => true, // Accept all status codes, we'll handle manually
      });
      
      // Check if response status indicates error
      if (response.status < 200 || response.status >= 300) {
        // Try to parse error from blob
        let errorMessage = `Failed to download config (HTTP ${response.status})`;
        if (response.data instanceof Blob) {
          try {
            const text = await response.data.text();
            const errorObj = JSON.parse(text);
            if (errorObj.error) {
              errorMessage = errorObj.error;
            }
          } catch (e) {
            // If parsing failed, use default error message
          }
        }
        throw new Error(errorMessage);
      }
      
      // Check if the blob is actually an error JSON based on Content-Type
      const contentType = response.headers['content-type'] || '';
      if (contentType.includes('application/json')) {
        try {
          const text = await response.data.text();
          const errorObj = JSON.parse(text);
          if (errorObj.error) {
            throw new Error(errorObj.error);
          }
        } catch (e: any) {
          // If it's not JSON or parsing fails, check if it was an error
          if (e instanceof Error && !e.message.includes('Unexpected')) {
            throw e;
          }
          // Continue with download if it's just a parse error
        }
      }
      
      // Get filename from Content-Disposition header or use default
      let filename = `${username}-${type}.conf`;
      const contentDisposition = response.headers['content-disposition'];
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }
      
      // Use the blob directly (response.data is already a Blob when responseType is 'blob')
      const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      
      // Clean up after a short delay to ensure download starts
      setTimeout(() => {
        try {
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
        } catch (e) {
          // Ignore cleanup errors
        }
      }, 100);
    } catch (error: any) {
      // Re-throw if it's already an Error with message (from our checks above)
      if (error instanceof Error && error.message.includes('Failed to download')) {
        throw error;
      }
      
      // If response is a blob error, try to parse it
      if (error.response?.data && error.response.data instanceof Blob) {
        try {
          const text = await error.response.data.text();
          const errorObj = JSON.parse(text);
          throw new Error(errorObj.error || 'Failed to download config');
        } catch (e: any) {
          // If parsing fails, use status code or generic error
          if (e instanceof Error && e.message.includes('error')) {
            throw e;
          }
          const status = error.response?.status;
          throw new Error(status ? `Failed to download config (HTTP ${status})` : 'Failed to download config');
        }
      }
      
      // If response has error data, try to extract error message
      if (error.response?.data) {
        const errorText = typeof error.response.data === 'string' 
          ? error.response.data 
          : (error.response.data.error || `Failed to download config (HTTP ${error.response.status || 'unknown'})`);
        throw new Error(errorText);
      }
      
      // If it's a network error or other error
      throw new Error(error.message || 'Failed to download config');
    }
  }
}

export default new ApiService();


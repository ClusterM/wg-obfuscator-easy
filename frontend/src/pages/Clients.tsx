import { useEffect, useState, useRef, type RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { QRCodeSVG } from 'qrcode.react';
import api from '../services/api';
import './Clients.css';

interface Client {
  username: string;
  ip: number;
  ip_full?: string;
  public_key: string;
  private_key?: string;
  preshared_key?: string | null;
  allowed_ips?: string[];
  keep_server_in_allowed_ips?: boolean;
  obfuscator_port?: number;
  masking_type_override?: string;
  verbosity_level?: string;
  enabled?: boolean;
  is_connected?: boolean;
  latest_handshake?: number;
  rx_bytes?: number;
  tx_bytes?: number;
}

const isValidWireGuardKey = (key: string): boolean => {
  if (!key || typeof key !== 'string') return false;
  try {
    const raw = atob(key);
    if (raw.length !== 32) return false;
    return btoa(raw) === key;
  } catch {
    return false;
  }
};

export default function Clients() {
  const { t } = useTranslation();
  const [clients, setClients] = useState<Record<string, Client>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newClientName, setNewClientName] = useState('');
  const [newClientEnabled, setNewClientEnabled] = useState(true);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [wireguardConfig, setWireguardConfig] = useState('');
  const [wireguardDirectConfig, setWireguardDirectConfig] = useState('');
  const [obfuscatorConfig, setObfuscatorConfig] = useState('');
  const [loadingConfigs, setLoadingConfigs] = useState(false);
  const [currentTime, setCurrentTime] = useState(Math.floor(Date.now() / 1000));
  const [serverObfuscationEnabled, setServerObfuscationEnabled] = useState(true);
  const [serverAllowClean, setServerAllowClean] = useState(false);
  const [serverConfig, setServerConfig] = useState<any>(null);
  const [success, setSuccess] = useState('');
  const [editingClientSettings, setEditingClientSettings] = useState<{
    masking_type_override?: string | null;
    obfuscator_port?: number;
    verbosity_level?: string | null;
    allowed_ips?: string[];
    keep_server_in_allowed_ips?: boolean;
    preshared_key_enabled?: boolean;
    preshared_key?: string;
  }>({});
  const [savingClientSettings, setSavingClientSettings] = useState(false);
  const [generatingPresharedKey, setGeneratingPresharedKey] = useState(false);
  const [clientSettingsError, setClientSettingsError] = useState('');
  const [clientSettingsSuccess, setClientSettingsSuccess] = useState('');
  const clientSettingsErrorTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [clientSettingsExpanded, setClientSettingsExpanded] = useState(false);
  const [qrCodeConfig, setQrCodeConfig] = useState<{ type: 'wireguard' | 'wireguard-direct' | 'obfuscator', content: string } | null>(null);
  const wireguardConfigRef = useRef<HTMLTextAreaElement | null>(null);
  const wireguardDirectConfigRef = useRef<HTMLTextAreaElement | null>(null);
  const obfuscatorConfigRef = useRef<HTMLTextAreaElement | null>(null);

  const flashElement = (element?: HTMLElement | null) => {
    if (!element) return;
    element.classList.remove('copy-flash');
    // Force reflow to restart animation
    void element.offsetWidth;
    element.classList.add('copy-flash');
    setTimeout(() => {
      element.classList.remove('copy-flash');
    }, 400);
  };

  const loadClients = async (showLoading: boolean = false) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      const data = await api.getClients();
      // API returns object with keys as usernames, but we need username field in each client
      const clientsWithUsername: Record<string, Client> = {};
      Object.keys(data).forEach(username => {
        clientsWithUsername[username] = {
          ...data[username],
          username: username, // Add username field to each client
        };
      });
      setClients(clientsWithUsername);
      
      // Update selected client if modal is open (preserve existing fields like private_key, configs, etc.)
      setSelectedClient(prev => {
        if (!prev) return prev;
        const fresh = clientsWithUsername[prev.username];
        return fresh ? { ...prev, ...fresh } : prev;
      });
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
      setSuccess('');
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    loadClients(true);
    loadServerConfig();
    
    // Auto-refresh clients every 5 seconds (without loading indicator)
    const interval = setInterval(() => {
      loadClients(false);
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  const loadServerConfig = async () => {
    try {
      const config = await api.getConfig();
      setServerObfuscationEnabled(config.obfuscation === true);
      setServerAllowClean(config.allow_clean === true);
      setServerConfig(config);
    } catch (err) {
      console.error('Failed to load server config:', err);
      // Default to true if we can't load config
      setServerObfuscationEnabled(true);
    }
  };

  const loadClientConfigs = async (
    username: string,
    obfuscationEnabled: boolean,
    allowClean: boolean,
    obfuscatorPort?: number
  ) => {
    try {
      const wgConfig = await api.getClientConfig(username, 'wireguard');
      setWireguardConfig(wgConfig);
    } catch (err: any) {
      setWireguardConfig(err.message || t('errors.serverError'));
    }

    if (obfuscationEnabled && allowClean) {
      try {
        const directConfig = await api.getClientConfig(username, 'wireguard', { direct: true });
        setWireguardDirectConfig(directConfig);
      } catch (err: any) {
        setWireguardDirectConfig(err.message || t('errors.serverError'));
      }
    } else {
      setWireguardDirectConfig('');
    }

    if (obfuscationEnabled && obfuscatorPort) {
      try {
        const obConfig = await api.getClientConfig(username, 'obfuscator');
        setObfuscatorConfig(obConfig);
      } catch (err: any) {
        setObfuscatorConfig(err.message || t('errors.serverError'));
      }
    } else {
      setObfuscatorConfig('');
    }
  };

  // Update current time every second for real-time handshake time display
  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(Math.floor(Date.now() / 1000));
    }, 1000);
    
    return () => clearInterval(timeInterval);
  }, []);

  // Update traffic counters and connection data in real-time when client modal is open
  useEffect(() => {
    if (!selectedClient) return;

    const updateClientData = async () => {
      try {
        // Get fresh client data (includes is_connected, latest_handshake, traffic counters)
        const clientData = await api.getClient(selectedClient.username);
        if (clientData) {
          setSelectedClient(prev => {
            if (!prev) return prev;
            // Merge with existing data (preserve configs, private_key, etc.)
            return {
              ...prev,
              // Update connection and stats data
              is_connected: clientData.is_connected,
              latest_handshake: clientData.latest_handshake,
              rx_bytes: clientData.rx_bytes,
              tx_bytes: clientData.tx_bytes,
            };
          });
        }
      } catch (error) {
        console.error('Error updating client data:', error);
      }
    };

    // Update immediately
    updateClientData();
    
    // Then update every 5 seconds (same as traffic collector interval)
    const updateInterval = setInterval(updateClientData, 5000);
    
    return () => clearInterval(updateInterval);
  }, [selectedClient?.username]);

  // Close modals on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (qrCodeConfig) {
          setQrCodeConfig(null);
        } else if (selectedClient) {
          setSelectedClient(null);
        } else if (showAddModal) {
          setShowAddModal(false);
        }
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [qrCodeConfig, selectedClient, showAddModal]);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  const formatHandshakeTime = (handshakeTimestamp: number): string => {
    if (!handshakeTimestamp || handshakeTimestamp === 0) {
      return t('clients.neverConnected');
    }
    
    const secondsAgo = currentTime - handshakeTimestamp;
    
    if (secondsAgo < 60) {
      return t('clients.secondsAgo', { count: secondsAgo }).replace('{{count}}', secondsAgo.toString());
    } else if (secondsAgo < 3600) {
      const minutes = Math.floor(secondsAgo / 60);
      return t('clients.minutesAgo', { count: minutes }).replace('{{count}}', minutes.toString());
    } else if (secondsAgo < 86400) {
      const hours = Math.floor(secondsAgo / 3600);
      return t('clients.hoursAgo', { count: hours }).replace('{{count}}', hours.toString());
    } else {
      const days = Math.floor(secondsAgo / 86400);
      return t('clients.daysAgo', { count: days }).replace('{{count}}', days.toString());
    }
  };

  const handleAddClient = async () => {
    if (!newClientName.trim()) return;

    try {
      setError('');
      await api.createClient(newClientName.trim(), true, newClientEnabled);
      setShowAddModal(false);
      setNewClientName('');
      setNewClientEnabled(true);
      await loadClients();
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    }
  };

  const handleDeleteClient = async (username: string) => {
    if (!confirm(t('clients.confirmDelete'))) return;

    try {
      setError('');
      await api.deleteClient(username);
      await loadClients();
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    }
  };

  const handleToggleEnabled = async (username: string, currentEnabled: boolean) => {
    try {
      setError('');
      await api.updateClient(username, { enabled: !currentEnabled });
      await loadClients();
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    }
  };

  const handleRegenerateClientKeys = async (username: string) => {
    if (!confirm(t('clients.confirmRegenerateKeys'))) return;

    try {
      setError('');
      setSuccess('');
      const result = await api.regenerateClientKeys(username);
      
      // Update selected client if modal is open
      if (selectedClient && selectedClient.username === username) {
        setSelectedClient({
          ...selectedClient,
          private_key: result.private_key,
          public_key: result.public_key,
        });
        
        // Reload configs with new keys
        setLoadingConfigs(true);
        try {
          await loadClientConfigs(
            username,
            serverObfuscationEnabled,
            serverAllowClean,
            selectedClient.obfuscator_port
          );
        } finally {
          setLoadingConfigs(false);
        }
      }
      
      await loadClients();
      setSuccess(t('clients.clientKeysRegenerated'));
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    }
  };

  const handleClientClick = async (client: Client) => {
    setSelectedClient(client);
    setLoadingConfigs(true);
    setWireguardConfig('');
    setWireguardDirectConfig('');
    setObfuscatorConfig('');
    setEditingClientSettings({});
    setClientSettingsError('');
    setClientSettingsSuccess('');
    setClientSettingsExpanded(false);
    if (clientSettingsErrorTimeoutRef.current) {
      clearTimeout(clientSettingsErrorTimeoutRef.current);
      clientSettingsErrorTimeoutRef.current = null;
    }
    
    try {
      // Load full client data
      const fullClient = await api.getClient(client.username);
      setSelectedClient({ ...client, ...fullClient });
      
      // Initialize editing settings with current client values
      setEditingClientSettings({
        masking_type_override: fullClient.masking_type_override ?? null,
        obfuscator_port: fullClient.obfuscator_port,
        verbosity_level: fullClient.verbosity_level || 'INFO',
        allowed_ips: fullClient.allowed_ips || ['0.0.0.0/0'],
        keep_server_in_allowed_ips: Boolean(fullClient.keep_server_in_allowed_ips),
        preshared_key_enabled: Boolean(fullClient.preshared_key),
        preshared_key: fullClient.preshared_key || '',
      });
      
      // Load server config to check obfuscation setting
      const serverConfig = await api.getConfig();
      const isObfuscationEnabled = serverConfig.obfuscation === true;
      const isAllowClean = serverConfig.allow_clean === true;
      setServerObfuscationEnabled(isObfuscationEnabled);
      setServerAllowClean(isAllowClean);
      setServerConfig(serverConfig);
      
      await loadClientConfigs(
        client.username,
        isObfuscationEnabled,
        isAllowClean,
        fullClient.obfuscator_port
      );
    } catch (err: any) {
      setClientSettingsError(err.message || t('errors.serverError'));
    } finally {
      setLoadingConfigs(false);
    }
  };

  const copyToClipboard = async (text: string, type: 'wireguard' | 'wireguard-direct' | 'obfuscator') => {
    const targetRef = type === 'obfuscator'
      ? obfuscatorConfigRef
      : type === 'wireguard-direct'
        ? wireguardDirectConfigRef
        : wireguardConfigRef;
    
    try {
      // Try modern Clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        flashElement(targetRef.current);
        return;
      }
      
      // Fallback to old method for older browsers or non-HTTPS contexts
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      try {
        const successful = document.execCommand('copy');
        if (successful) {
          flashElement(targetRef.current);
        } else {
          throw new Error('execCommand failed');
        }
      } finally {
        document.body.removeChild(textArea);
      }
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      setError(t('common.copyFailed') || 'Failed to copy to clipboard');
      setTimeout(() => setError(''), 3000);
    }
  };

  const validateCidr = (cidr: string): boolean => {
    if (!cidr || typeof cidr !== 'string') return false;
    
    // Trim whitespace
    const trimmed = cidr.trim();
    if (!trimmed) return false;
    
    // Must contain exactly one '/'
    if (trimmed.indexOf('/') === -1 || trimmed.indexOf('/') !== trimmed.lastIndexOf('/')) {
      return false;
    }
    
    const [ip, mask] = trimmed.split('/');
    if (!ip || !mask) return false;
    
    // Validate mask is numeric and within range
    const maskNum = parseInt(mask, 10);
    if (mask !== String(maskNum) || isNaN(maskNum) || maskNum < 0 || maskNum > 32) {
      return false;
    }
    
    // Validate IP format using regex (IPv4 CIDR)
    const ipv4Regex = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
    const match = ip.match(ipv4Regex);
    if (!match) return false;
    
    // Validate each octet is between 0-255
    for (let i = 1; i <= 4; i++) {
      const octet = parseInt(match[i], 10);
      if (isNaN(octet) || octet < 0 || octet > 255) {
        return false;
      }
    }
    
    // Additional check: if mask is /0, address must be 0.0.0.0
    if (maskNum === 0 && ip !== '0.0.0.0') {
      return false;
    }
    
    // Validate that the network address matches the given IP (strict CIDR validation)
    // For example, 192.168.1.0/24 is valid, but 192.168.1.5/24 is not (host bits set)
    // This ensures the IP address is a valid network address for the given prefix length
    try {
      const octets = ip.split('.').map(oct => parseInt(oct, 10));
      
      // Calculate how many bits are in each octet
      for (let i = 0; i < 4; i++) {
        const bitsFromStart = i * 8;
        const bitsInOctet = Math.max(0, Math.min(8, maskNum - bitsFromStart));
        
        if (bitsInOctet === 0) {
          // All bits in this and subsequent octets must be 0
          if (octets[i] !== 0) {
            return false;
          }
        } else if (bitsInOctet < 8) {
          // Some bits in this octet are host bits and must be 0
          const hostBits = 8 - bitsInOctet;
          const hostMask = (1 << hostBits) - 1;
          if ((octets[i] & hostMask) !== 0) {
            return false;
          }
        }
        // If bitsInOctet === 8, all bits are network bits, no validation needed
      }
    } catch (e) {
      return false;
    }
    
    return true;
  };

  const handleAllowedIpChange = (index: number, value: string) => {
    // Clear success message when user starts typing
    setClientSettingsSuccess('');
    const newAllowedIps = [...(editingClientSettings.allowed_ips || [])];
    newAllowedIps[index] = value;
    setEditingClientSettings({ ...editingClientSettings, allowed_ips: newAllowedIps });
  };

  const handleAddAllowedIp = () => {
    // Clear success message
    setClientSettingsSuccess('');
    const newAllowedIps = [...(editingClientSettings.allowed_ips || []), ''];
    setEditingClientSettings({ ...editingClientSettings, allowed_ips: newAllowedIps });
  };

  const handleGeneratePresharedKey = async () => {
    try {
      setGeneratingPresharedKey(true);
      setClientSettingsSuccess('');
      setClientSettingsError('');
      const result = await api.generatePresharedKey();
      setEditingClientSettings((prev) => ({
        ...prev,
        preshared_key_enabled: true,
        preshared_key: result.preshared_key,
      }));
    } catch (err: any) {
      setClientSettingsError(err.message || t('errors.serverError'));
      if (clientSettingsErrorTimeoutRef.current) {
        clearTimeout(clientSettingsErrorTimeoutRef.current);
      }
      clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
    } finally {
      setGeneratingPresharedKey(false);
    }
  };

  const handleRemoveAllowedIp = (index: number) => {
    // Clear success message
    setClientSettingsSuccess('');
    const newAllowedIps = [...(editingClientSettings.allowed_ips || [])];
    if (newAllowedIps.length <= 1) {
      setClientSettingsError(t('clients.allowedIpsMinOne'));
      // Auto-hide error after 5 seconds
      if (clientSettingsErrorTimeoutRef.current) {
        clearTimeout(clientSettingsErrorTimeoutRef.current);
      }
      clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
      return;
    }
    newAllowedIps.splice(index, 1);
    setEditingClientSettings({ ...editingClientSettings, allowed_ips: newAllowedIps });
  };

  const handleSaveClientSettings = async () => {
    if (!selectedClient) return;

    // Validate allowed_ips
    const allowedIps = (editingClientSettings.allowed_ips || []).filter(ip => ip.trim() !== '');
    if (allowedIps.length === 0) {
      setClientSettingsError(t('clients.allowedIpsMinOne'));
      // Auto-hide error after 5 seconds
      if (clientSettingsErrorTimeoutRef.current) {
        clearTimeout(clientSettingsErrorTimeoutRef.current);
      }
      clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
      return;
    }
    for (const ip of allowedIps) {
      if (!validateCidr(ip)) {
        setClientSettingsError(t('clients.allowedIpsInvalidFormat'));
        // Auto-hide error after 5 seconds
        if (clientSettingsErrorTimeoutRef.current) {
          clearTimeout(clientSettingsErrorTimeoutRef.current);
        }
        clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
        return;
      }
    }

    if (editingClientSettings.preshared_key_enabled) {
      const presharedKey = (editingClientSettings.preshared_key || '').trim();
      if (!presharedKey) {
        setClientSettingsError(t('clients.presharedKeyEmpty'));
        if (clientSettingsErrorTimeoutRef.current) {
          clearTimeout(clientSettingsErrorTimeoutRef.current);
        }
        clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
        return;
      }
      if (!isValidWireGuardKey(presharedKey)) {
        setClientSettingsError(t('clients.presharedKeyInvalid'));
        if (clientSettingsErrorTimeoutRef.current) {
          clearTimeout(clientSettingsErrorTimeoutRef.current);
        }
        clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
        return;
      }
    }

    // Validate obfuscator_port if provided
    if (editingClientSettings.obfuscator_port !== undefined && editingClientSettings.obfuscator_port !== null) {
      const port = editingClientSettings.obfuscator_port;
      if (isNaN(port) || port < 1 || port > 65535) {
        setClientSettingsError(t('clients.obfuscatorPortInvalid'));
        // Auto-hide error after 5 seconds
        if (clientSettingsErrorTimeoutRef.current) {
          clearTimeout(clientSettingsErrorTimeoutRef.current);
        }
        clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
        return;
      }
    }

    try {
      setSavingClientSettings(true);
      // Clear previous messages and timeout
      if (clientSettingsErrorTimeoutRef.current) {
        clearTimeout(clientSettingsErrorTimeoutRef.current);
        clientSettingsErrorTimeoutRef.current = null;
      }
      setClientSettingsError('');
      setClientSettingsSuccess('');
      
      const updateData: any = {};
      // Only send masking_type_override if masking_forced is not enabled
      if ('masking_type_override' in editingClientSettings && serverConfig?.masking_forced !== true) {
        updateData.masking_type_override = editingClientSettings.masking_type_override;
      }
      if ('obfuscator_port' in editingClientSettings) {
        // Send null if undefined or null, otherwise send the port number
        if (editingClientSettings.obfuscator_port === undefined || editingClientSettings.obfuscator_port === null) {
          updateData.obfuscator_port = null;
        } else {
          updateData.obfuscator_port = editingClientSettings.obfuscator_port;
        }
      }
      if ('allowed_ips' in editingClientSettings) {
        updateData.allowed_ips = (editingClientSettings.allowed_ips || []).filter(ip => ip.trim() !== '');
      }
      updateData.keep_server_in_allowed_ips = editingClientSettings.keep_server_in_allowed_ips === true;
      if ('verbosity_level' in editingClientSettings) {
        // Always send verbosity_level, default to INFO if not set
        updateData.verbosity_level = editingClientSettings.verbosity_level || 'INFO';
      }
      updateData.preshared_key = editingClientSettings.preshared_key_enabled
        ? (editingClientSettings.preshared_key || '').trim()
        : null;

      const updatedClient = await api.updateClient(selectedClient.username, updateData);
      setSelectedClient({ ...selectedClient, ...updatedClient });
      setEditingClientSettings({
        masking_type_override: updatedClient.masking_type_override ?? null,
        obfuscator_port: updatedClient.obfuscator_port,
        verbosity_level: updatedClient.verbosity_level || 'INFO',
        allowed_ips: updatedClient.allowed_ips || ['0.0.0.0/0'],
        keep_server_in_allowed_ips: Boolean(updatedClient.keep_server_in_allowed_ips),
        preshared_key_enabled: Boolean(updatedClient.preshared_key),
        preshared_key: updatedClient.preshared_key || '',
      });
      
      // Reload configs
      setLoadingConfigs(true);
      try {
        await loadClientConfigs(
          updatedClient.username,
          serverObfuscationEnabled,
          serverAllowClean,
          updatedClient.obfuscator_port
        );
      } finally {
        setLoadingConfigs(false);
      }
      
      setClientSettingsSuccess(t('clients.clientSettingsUpdated'));
      await loadClients();
      // Auto-hide success after 3 seconds
      setTimeout(() => setClientSettingsSuccess(''), 3000);
    } catch (err: any) {
      setClientSettingsError(err.message || t('errors.serverError'));
      // Auto-hide error after 5 seconds
      if (clientSettingsErrorTimeoutRef.current) {
        clearTimeout(clientSettingsErrorTimeoutRef.current);
      }
      clientSettingsErrorTimeoutRef.current = setTimeout(() => setClientSettingsError(''), 5000);
    } finally {
      setSavingClientSettings(false);
    }
  };

  const renderConfigField = (
    title: string,
    value: string,
    type: 'wireguard' | 'wireguard-direct' | 'obfuscator',
    textareaRef: RefObject<HTMLTextAreaElement>
  ) => (
    <div className="config-section">
      <h3>{title}</h3>
      {loadingConfigs ? (
        <div className="loading">{t('common.loading')}</div>
      ) : (
        <div className="config-field-container">
          <textarea
            className="config-textarea copy-highlight-target"
            value={value}
            readOnly
            rows={10}
            ref={textareaRef}
          />
          <div className="config-actions">
            <button
              onClick={() => setQrCodeConfig({ type, content: value })}
              className="btn-secondary btn-qr"
              disabled={!value}
            >
              📱 {t('common.showQR')}
            </button>
            <button
              onClick={() => copyToClipboard(value, type)}
              className="btn-primary btn-copy"
              disabled={!value}
            >
              📋 {t('common.copy')}
            </button>
          </div>
        </div>
      )}
    </div>
  );

  if (loading) {
    return <div className="loading">{t('common.loading')}</div>;
  }

  const clientList = Object.values(clients);

  return (
    <div className="clients-page">
      <div className="page-header">
        <h1>{t('clients.title')}</h1>
      </div>

      {error && (
        <div className="error-message alert-message">
          <span className="message-text">{error}</span>
          <button
            type="button"
            className="message-close"
            onClick={() => setError('')}
            aria-label={t('common.close')}
          >
            &times;
          </button>
        </div>
      )}
      {success && <div className="success-message">{success}</div>}

      {clientList.length === 0 ? (
        <div className="no-clients">{t('clients.noClients')}</div>
      ) : (
        <div className="clients-table-container">
          <table className="clients-table">
            <thead>
              <tr>
                <th>{t('clients.username')}</th>
                <th>{t('clients.connection')}</th>
                <th>{t('clients.ip')}</th>
                <th>{t('clients.publicKey')}</th>
                <th>{t('clients.received')}</th>
                <th>{t('clients.sent')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {clientList.map((client) => (
                <tr 
                  key={client.username} 
                  className={client.enabled === false ? 'client-disabled' : ''}
                  onClick={() => handleClientClick(client)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{client.username}</td>
                  <td>
                    <div className="connection-status">
                      <span className={client.is_connected ? 'connected' : 'disconnected'}>
                        {client.is_connected ? t('clients.connected') : t('clients.disconnected')}
                      </span>
                      {client.latest_handshake !== undefined && (
                        <div className="handshake-time">
                          {formatHandshakeTime(client.latest_handshake)}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="mono">{client.ip_full || client.ip}</td>
                  <td className="mono small">{client.public_key.substring(0, 20)}...</td>
                  <td>
                    {client.rx_bytes !== undefined ? formatBytes(client.rx_bytes) : '-'}
                  </td>
                  <td>
                    {client.tx_bytes !== undefined ? formatBytes(client.tx_bytes) : '-'}
                  </td>
                  <td>
                    <div className="actions-cell">
                      <label 
                        className="toggle-switch"
                        onClick={(e) => e.stopPropagation()}
                        title={client.enabled !== false ? t('clients.disableClient') : t('clients.enableClient')}
                      >
                        <input
                          type="checkbox"
                          checked={client.enabled !== false}
                          onChange={() => handleToggleEnabled(client.username, client.enabled !== false)}
                        />
                        <span className="slider"></span>
                      </label>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteClient(client.username);
                        }}
                        className="btn-small btn-danger"
                        title={t('clients.deleteClient')}
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="add-client-footer">
        <button onClick={() => setShowAddModal(true)} className="btn-primary btn-small-add">
          {t('clients.addClient')}
        </button>
      </div>

      {showAddModal && (
        <div 
          className="modal-overlay" 
          onMouseDown={(e) => {
            // Store where mousedown started
            if (e.target === e.currentTarget) {
              (e.currentTarget as HTMLElement).setAttribute('data-mousedown-on-overlay', 'true');
            }
          }}
          onMouseUp={(e) => {
            // Only close if mousedown and mouseup both happened on overlay
            if (e.target === e.currentTarget && 
                (e.currentTarget as HTMLElement).getAttribute('data-mousedown-on-overlay') === 'true') {
              setShowAddModal(false);
            }
            (e.currentTarget as HTMLElement).removeAttribute('data-mousedown-on-overlay');
          }}
          onClick={(e) => {
            // Prevent click from bubbling if it was a drag
            e.stopPropagation();
          }}
        >
          <div className="modal-content">
            <h2>{t('clients.addClient')}</h2>
            <div className="form-group">
              <label>{t('clients.clientName')}</label>
              <input
                type="text"
                value={newClientName}
                onChange={(e) => setNewClientName(e.target.value)}
                placeholder={t('clients.clientName')}
                autoFocus
              />
            </div>
            <div className="form-group">
              <label>
                <input
                  type="checkbox"
                  checked={newClientEnabled}
                  onChange={(e) => setNewClientEnabled(e.target.checked)}
                />
                {t('clients.enable')}
              </label>
            </div>
            <div className="modal-actions">
              <button onClick={() => setShowAddModal(false)} className="btn-secondary">
                {t('common.cancel')}
              </button>
              <button onClick={handleAddClient} className="btn-primary">
                {t('common.create')}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedClient && (
        <div 
          className="modal-overlay"
          onMouseDown={(e) => {
            // Store where mousedown started
            if (e.target === e.currentTarget) {
              (e.currentTarget as HTMLElement).setAttribute('data-mousedown-on-overlay', 'true');
            }
          }}
          onMouseUp={(e) => {
            // Only close if mousedown and mouseup both happened on overlay
            if (e.target === e.currentTarget && 
                (e.currentTarget as HTMLElement).getAttribute('data-mousedown-on-overlay') === 'true') {
              setSelectedClient(null);
            }
            (e.currentTarget as HTMLElement).removeAttribute('data-mousedown-on-overlay');
          }}
          onClick={(e) => {
            // Prevent click from bubbling if it was a drag
            e.stopPropagation();
          }}
        >
          <div className="modal-content client-details-modal">
            <div className="modal-header">
              <h2>{selectedClient.username}</h2>
              <label 
                className="toggle-switch"
                title={selectedClient.enabled !== false ? t('clients.disableClient') : t('clients.enableClient')}
              >
                <input
                  type="checkbox"
                  checked={selectedClient.enabled !== false}
                  onChange={() => {
                    handleToggleEnabled(selectedClient.username, selectedClient.enabled !== false);
                    // Update local state immediately for better UX. An absent
                    // enabled flag means the client is enabled.
                    setSelectedClient(prev => prev ? {...prev, enabled: prev.enabled === false} : prev);
                  }}
                />
                <span className="slider"></span>
              </label>
            </div>
            
            <div className="client-details">
              <table className="details-table">
                <tbody>
                  <tr>
                    <td className="detail-label">{t('clients.username')}:</td>
                    <td className="detail-value">{selectedClient.username}</td>
                  </tr>
                  
                  <tr>
                    <td className="detail-label">{t('clients.ip')}:</td>
                    <td className="detail-value mono">{selectedClient.ip_full || selectedClient.ip}</td>
                  </tr>
                  
                  <tr>
                    <td className="detail-label">{t('clients.publicKey')}:</td>
                    <td className="detail-value mono small">{selectedClient.public_key}</td>
                  </tr>
                  
                  {selectedClient.private_key && (
                    <tr>
                      <td className="detail-label">{t('clients.privateKey')}:</td>
                      <td className="detail-value mono small">{selectedClient.private_key}</td>
                    </tr>
                  )}

                  {selectedClient.preshared_key && (
                    <tr>
                      <td className="detail-label">{t('clients.presharedKey')}:</td>
                      <td className="detail-value mono small">{selectedClient.preshared_key}</td>
                    </tr>
                  )}
                  
                  <tr>
                    <td className="detail-label">{t('clients.connection')}:</td>
                    <td className={`detail-value ${selectedClient.is_connected ? 'connected' : 'disconnected'}`}>
                      {selectedClient.is_connected ? t('clients.connected') : t('clients.disconnected')}
                    </td>
                  </tr>
                  
                  {selectedClient.latest_handshake !== undefined && (
                    <tr>
                      <td className="detail-label">{t('clients.lastHandshake')}:</td>
                      <td className="detail-value">
                        {formatHandshakeTime(selectedClient.latest_handshake)}
                      </td>
                    </tr>
                  )}
                  {selectedClient.rx_bytes !== undefined && selectedClient.tx_bytes !== undefined && (
                    <>
                      <tr>
                        <td className="detail-label">{t('clients.currentReceived')}:</td>
                        <td className="detail-value">
                          {formatBytes(selectedClient.rx_bytes)}
                        </td>
                      </tr>
                      <tr>
                        <td className="detail-label">{t('clients.currentSent')}:</td>
                        <td className="detail-value">
                          {formatBytes(selectedClient.tx_bytes)}
                        </td>
                      </tr>
                    </>
                  )}
                </tbody>
              </table>
            </div>

            {clientSettingsError && <div className="error-message">{clientSettingsError}</div>}
            {clientSettingsSuccess && <div className="success-message">{clientSettingsSuccess}</div>}

            <div className="client-settings-section">
              <div 
                className="settings-header-toggle"
                onClick={() => setClientSettingsExpanded(!clientSettingsExpanded)}
              >
                <h3>{t('clients.clientSettings')}</h3>
                <span className="toggle-icon">{clientSettingsExpanded ? '▼' : '▶'}</span>
              </div>
              
              {clientSettingsExpanded && (
                <div className="settings-content">
                  <div className="form-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={editingClientSettings.preshared_key_enabled === true}
                        onChange={(e) => {
                          setClientSettingsSuccess('');
                          setEditingClientSettings({
                            ...editingClientSettings,
                            preshared_key_enabled: e.target.checked,
                          });
                        }}
                      />
                      {t('clients.enablePresharedKey')}
                    </label>
                    <div className="field-description">{t('clients.enablePresharedKeyDescription')}</div>
                  </div>

                  {editingClientSettings.preshared_key_enabled && (
                    <div className="form-group">
                      <label>{t('clients.presharedKey')}</label>
                      <div className="input-with-button">
                        <input
                          type="text"
                          value={editingClientSettings.preshared_key || ''}
                          onChange={(e) => {
                            setClientSettingsSuccess('');
                            setEditingClientSettings({
                              ...editingClientSettings,
                              preshared_key: e.target.value,
                            });
                          }}
                          placeholder={t('clients.presharedKeyPlaceholder')}
                          className={`mono ${
                            editingClientSettings.preshared_key &&
                            !isValidWireGuardKey(editingClientSettings.preshared_key.trim())
                              ? 'invalid'
                              : ''
                          }`}
                        />
                        <button
                          type="button"
                          onClick={handleGeneratePresharedKey}
                          disabled={generatingPresharedKey}
                          className="btn-secondary btn-generate-key"
                          title={t('clients.generatePresharedKey')}
                        >
                          {generatingPresharedKey ? t('common.loading') : t('clients.generatePresharedKey')}
                        </button>
                      </div>
                      <div className="field-description">{t('clients.presharedKeyDescription')}</div>
                    </div>
                  )}

                  <div className="settings-warning">
                    {t('clients.settingsWarning')}
                  </div>
                  
                  <div className="form-group">
                <label>{t('clients.maskingTypeOverride')}</label>
                <select
                  value={editingClientSettings.masking_type_override || 'default'}
                  onChange={(e) => {
                    setClientSettingsSuccess('');
                    const value = e.target.value === 'default' ? null : e.target.value;
                    setEditingClientSettings({ ...editingClientSettings, masking_type_override: value });
                  }}
                  disabled={serverConfig?.masking_forced === true}
                >
                  <option value="default">{t('clients.useDefault')}</option>
                  <option value="NONE">NONE</option>
                  <option value="STUN">STUN</option>
                </select>
                {serverConfig?.masking_forced === true && (
                  <div className="field-description">{t('clients.maskingTypeOverrideDisabled')}</div>
                )}
                <div className="field-description">{t('clients.maskingTypeOverrideDescription')}</div>
              </div>

              <div className="form-group">
                <label>{t('clients.obfuscatorPort')}</label>
                <input
                  type="number"
                  value={editingClientSettings.obfuscator_port || ''}
                  onChange={(e) => {
                    setClientSettingsSuccess('');
                    const value = e.target.value === '' ? undefined : parseInt(e.target.value, 10);
                    setEditingClientSettings({ ...editingClientSettings, obfuscator_port: value });
                  }}
                  min={1}
                  max={65535}
                  placeholder={t('clients.obfuscatorPortPlaceholder')}
                />
                <div className="field-description">{t('clients.obfuscatorPortDescription')}</div>
              </div>

              <div className="form-group">
                <label>{t('clients.allowedIPs')}</label>
                {(editingClientSettings.allowed_ips || []).map((ip, index) => (
                  <div key={index} className="allowed-ip-row">
                    <input
                      type="text"
                      value={ip}
                      onChange={(e) => handleAllowedIpChange(index, e.target.value)}
                      placeholder="0.0.0.0/0"
                      className={!validateCidr(ip) && ip !== '' ? 'invalid' : ''}
                    />
                    {(editingClientSettings.allowed_ips || []).length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveAllowedIp(index)}
                        className="btn-remove"
                        title={t('clients.removeAllowedIp')}
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={handleAddAllowedIp}
                  className="btn-add-ip"
                >
                  + {t('clients.addAllowedIp')}
                </button>
                <div className="field-description">{t('clients.allowedIPsDescription')}</div>
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={editingClientSettings.keep_server_in_allowed_ips === true}
                    onChange={(e) => {
                      setClientSettingsSuccess('');
                      setEditingClientSettings({
                        ...editingClientSettings,
                        keep_server_in_allowed_ips: e.target.checked,
                      });
                    }}
                  />
                  {t('clients.keepServerInAllowedIps')}
                </label>
                <div className="field-description">{t('clients.keepServerInAllowedIpsDescription')}</div>
              </div>

              <div className="form-group">
                <label>{t('clients.verbosityLevel')}</label>
                <select
                  value={editingClientSettings.verbosity_level || 'INFO'}
                  onChange={(e) => {
                    setClientSettingsSuccess('');
                    setEditingClientSettings({ ...editingClientSettings, verbosity_level: e.target.value });
                  }}
                >
                  <option value="ERROR">ERROR</option>
                  <option value="WARNING">WARNING</option>
                  <option value="INFO">INFO</option>
                  <option value="DEBUG">DEBUG</option>
                  <option value="TRACE">TRACE</option>
                </select>
                <div className="field-description">{t('clients.verbosityLevelDescription')}</div>
              </div>

              <div className="form-actions">
                <button
                  onClick={handleSaveClientSettings}
                  disabled={savingClientSettings}
                  className="btn-primary"
                >
                  {savingClientSettings ? t('common.loading') : t('common.save')}
                </button>
              </div>
                </div>
              )}
            </div>

            {serverObfuscationEnabled && serverAllowClean ? (
              <>
                <div className="config-group">
                  <h2>{t('clients.connectWithoutObfuscation')}</h2>
                  {renderConfigField(
                    t('clients.wireguardConfig'),
                    wireguardDirectConfig,
                    'wireguard-direct',
                    wireguardDirectConfigRef
                  )}
                </div>
                <div className="config-group">
                  <h2>{t('clients.connectWithObfuscation')}</h2>
                  {renderConfigField(
                    t('clients.wireguardConfig'),
                    wireguardConfig,
                    'wireguard',
                    wireguardConfigRef
                  )}
                  {renderConfigField(
                    t('clients.obfuscatorConfig'),
                    obfuscatorConfig,
                    'obfuscator',
                    obfuscatorConfigRef
                  )}
                </div>
              </>
            ) : (
              <>
                {renderConfigField(
                  t('clients.wireguardConfig'),
                  wireguardConfig,
                  'wireguard',
                  wireguardConfigRef
                )}
                {serverObfuscationEnabled && renderConfigField(
                  t('clients.obfuscatorConfig'),
                  obfuscatorConfig,
                  'obfuscator',
                  obfuscatorConfigRef
                )}
              </>
            )}

            <div className="modal-actions">
              <button 
                onClick={() => handleRegenerateClientKeys(selectedClient.username)} 
                className="btn-warning"
              >
                {t('clients.regenerateKeys')}
              </button>
              <button onClick={() => setSelectedClient(null)} className="btn-primary">
                {t('common.close')}
              </button>
            </div>
          </div>
        </div>
      )}

      {qrCodeConfig && (
        <div 
          className="modal-overlay"
          onMouseDown={(e) => {
            // Store where mousedown started
            if (e.target === e.currentTarget) {
              (e.currentTarget as HTMLElement).setAttribute('data-mousedown-on-overlay', 'true');
            }
          }}
          onMouseUp={(e) => {
            // Only close if mousedown and mouseup both happened on overlay
            if (e.target === e.currentTarget && 
                (e.currentTarget as HTMLElement).getAttribute('data-mousedown-on-overlay') === 'true') {
              setQrCodeConfig(null);
            }
            (e.currentTarget as HTMLElement).removeAttribute('data-mousedown-on-overlay');
          }}
          onClick={(e) => {
            // Prevent click from bubbling if it was a drag
            e.stopPropagation();
          }}
        >
          <div className="modal-content qr-modal">
            <h2>
              {qrCodeConfig.type === 'obfuscator'
                ? t('clients.obfuscatorConfig')
                : qrCodeConfig.type === 'wireguard-direct'
                  ? t('clients.connectWithoutObfuscation')
                  : t('clients.wireguardConfig')}
            </h2>
            <div className="qr-container">
              <QRCodeSVG
                value={qrCodeConfig.content}
                size={Math.min(window.innerWidth * 0.85, window.innerHeight * 0.7, 700)}
                level="M"
                includeMargin={false}
              />
            </div>
            <div className="modal-actions" style={{ marginTop: '1rem' }}>
              <button onClick={() => setQrCodeConfig(null)} className="btn-primary">
                {t('common.close')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


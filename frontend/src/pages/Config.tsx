import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import './Config.css';

interface Config {
  external_ip: string;
  external_port: number;
  subnet: string;
  server_ip: string;
  server_public_key: string;
  obfuscation: boolean;
  obfuscation_key?: string;
  obfuscator_verbosity: string;
  masking_type: string;
  masking_forced: boolean;
}

export default function Config() {
  const { t } = useTranslation();
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [currentUsername, setCurrentUsername] = useState('');
  const [newUsername, setNewUsername] = useState('');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingCredentials, setChangingCredentials] = useState(false);
  const [originalObfuscationKey, setOriginalObfuscationKey] = useState<string | undefined>(undefined);

  // Timezone state
  const [currentTimezone, setCurrentTimezone] = useState('');
  const [timezoneOffset, setTimezoneOffset] = useState('');
  const [availableTimezones, setAvailableTimezones] = useState<string[]>([]);
  const [selectedTimezone, setSelectedTimezone] = useState('');
  const [changingTimezone, setChangingTimezone] = useState(false);
  const [showRestartModal, setShowRestartModal] = useState(false);
  const [restartStatus, setRestartStatus] = useState<'waiting' | 'checking' | 'success' | 'error'>('waiting');

  // Grafana token state
  const [grafanaToken, setGrafanaToken] = useState<string | null>(null);
  const [generatingGrafanaToken, setGeneratingGrafanaToken] = useState(false);
  const [showGrafanaInstructions, setShowGrafanaInstructions] = useState(false);

  const copyTextToClipboard = async (text: string) => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }

      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      let successful = false;
      try {
        successful = document.execCommand('copy');
      } finally {
        document.body.removeChild(textArea);
      }

      if (!successful) {
        throw new Error('execCommand failed');
      }

      return true;
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      return false;
    }
  };

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await api.getConfig();
      setConfig(data);
      setOriginalObfuscationKey(data.obfuscation_key);
      setError('');
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    } finally {
      setLoading(false);
    }
  };

  const loadCredentials = async () => {
    try {
      const data = await api.getCredentials();
      setCurrentUsername(data.username);
    } catch (err: any) {
      console.error('Failed to load credentials:', err);
    }
  };

  const loadTimezone = async () => {
    try {
      const data = await api.getSystemTimezone();
      setCurrentTimezone(data.timezone);
      setTimezoneOffset(data.offset);
      setAvailableTimezones(data.available_timezones);
      setSelectedTimezone(data.timezone);
    } catch (err: any) {
      console.error('Failed to load timezone:', err);
    }
  };

  const loadGrafanaToken = async () => {
    try {
      const data = await api.getGrafanaToken();
      if (data.token) {
        setGrafanaToken(data.token);
        setShowGrafanaInstructions(true);
      }
    } catch (err: any) {
      console.error('Failed to load Grafana token:', err);
    }
  };

  const waitForSystemRestart = async () => {
    setRestartStatus('waiting');

    // Wait 3 seconds before starting checks (give system time to start shutting down)
    await new Promise(resolve => setTimeout(resolve, 3000));

    const maxAttempts = 60; // 60 attempts * 2 seconds = 2 minutes max
    let attempts = 0;

    const checkSystem = async (): Promise<boolean> => {
      try {
        setRestartStatus('checking');
        // Try to load timezone data as a health check
        await api.getSystemTimezone();
        return true;
      } catch (error) {
        return false;
      }
    };

    const checkInterval = setInterval(async () => {
      attempts++;

      if (await checkSystem()) {
        // System is back online!
        clearInterval(checkInterval);
        setRestartStatus('success');

        // Reload timezone data
        await loadTimezone();

        // Close modal after 3 seconds and reset changing state
        setTimeout(() => {
          setShowRestartModal(false);
          setRestartStatus('waiting');
          setChangingTimezone(false);
        }, 3000);
      } else if (attempts >= maxAttempts) {
        // Timeout - system didn't come back
        clearInterval(checkInterval);
        setRestartStatus('error');
        setChangingTimezone(false);
      }
    }, 2000); // Check every 2 seconds
  };

  useEffect(() => {
    loadConfig();
    loadCredentials();
    loadTimezone();
    loadGrafanaToken();
  }, []);

  const handleSave = async () => {
    if (!config) return;

    // Check if obfuscation key was changed
    const keyChanged = config.obfuscation_key !== originalObfuscationKey;
    if (keyChanged) {
      if (!confirm(t('config.confirmObfuscationKeyChange'))) {
        return;
      }
    }

    try {
      setSaving(true);
      setError('');
      setSuccess('');
      await api.updateConfig({
        subnet: config.subnet,
        obfuscation: config.obfuscation,
        obfuscation_key: config.obfuscation_key,
        verbosity_level: config.obfuscator_verbosity,
        masking_type: config.masking_type,
        masking_forced: config.masking_forced,
      });
      setSuccess(t('config.configUpdated'));
      await loadConfig();
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateKeys = async () => {
    if (!confirm(t('config.confirmRegenerateKeys'))) return;

    try {
      await api.regenerateServerKeys();
      setSuccess(t('config.keysRegenerated'));
      await loadConfig();
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    }
  };

  const generateRandomKey = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=[]{}|;:,.<>?';
    let result = '';
    const randomValues = new Uint8Array(64);
    crypto.getRandomValues(randomValues);
    for (let i = 0; i < 64; i++) {
      result += chars[randomValues[i] % chars.length];
    }
    if (config) {
      setConfig({ ...config, obfuscation_key: result });
    }
  };

  const handleChangeCredentials = async () => {
    if (!oldPassword) {
      setError(t('config.oldPassword') + ' ' + t('errors.validationError'));
      return;
    }

    if (newPassword && newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (!newUsername.trim() && !newPassword) {
      setError('Please provide new username or password');
      return;
    }

    try {
      setChangingCredentials(true);
      setError('');
      setSuccess('');
      await api.changeCredentials(
        oldPassword,
        newUsername.trim() || undefined,
        newPassword || undefined
      );
      setSuccess(t('config.credentialsChanged'));
      setOldPassword('');
      setNewUsername('');
      setNewPassword('');
      setConfirmPassword('');
      await loadCredentials();
      // Redirect to login after 2 seconds
      setTimeout(() => {
        window.location.href = '/login';
      }, 2000);
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    } finally {
      setChangingCredentials(false);
    }
  };

  const handleGenerateGrafanaToken = async () => {
    try {
      setGeneratingGrafanaToken(true);
      setError('');
      setSuccess('');
      const data = await api.generateGrafanaToken();
      setGrafanaToken(data.token);
      setShowGrafanaInstructions(true);
      setSuccess(t('config.grafanaTokenGenerated'));
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    } finally {
      setGeneratingGrafanaToken(false);
    }
  };

  const handleDeleteGrafanaToken = async () => {
    if (!confirm(t('config.confirmDeleteGrafanaToken'))) {
      return;
    }

    try {
      setError('');
      setSuccess('');
      await api.deleteGrafanaToken();
      setGrafanaToken(null);
      setShowGrafanaInstructions(false);
      setSuccess(t('config.grafanaTokenDeleted'));
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    }
  };

  const handleCopyGrafanaToken = async () => {
    if (!grafanaToken) return;
    
    const copied = await copyTextToClipboard(grafanaToken);
    if (copied) {
      setSuccess(t('config.tokenCopied'));
      setTimeout(() => setSuccess(''), 2000);
    } else {
      setError(t('common.copyFailed'));
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleCopyUrl = async (url: string) => {
    const copied = await copyTextToClipboard(url);
    if (copied) {
      setSuccess(t('common.copied'));
      setTimeout(() => setSuccess(''), 2000);
    } else {
      setError(t('common.copyFailed'));
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleChangeTimezone = async () => {
    if (!selectedTimezone || selectedTimezone === currentTimezone) {
      return;
    }

    // Show alert about system restart
    const confirmRestart = window.confirm(t('config.timezoneRestartAlert'));
    if (!confirmRestart) {
      return;
    }

    try {
      setChangingTimezone(true);
      setError('');
      setSuccess('');

      // First, set the timezone
      await api.setSystemTimezone(selectedTimezone);

      // Then restart the system to apply changes
      await api.restartSystem();

      // Show restart modal and start waiting for system
      setShowRestartModal(true);
      await waitForSystemRestart();

    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
      setChangingTimezone(false);
    }
  };

  if (loading) {
    return <div className="loading">{t('common.loading')}</div>;
  }

  if (!config) {
    return <div className="error">{t('errors.notFound')}</div>;
  }

  return (
    <div className="config-page">
      <h1>{t('config.title')}</h1>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      <div className="config-section">
        <h2>{t('config.general')}</h2>
        <div className="form-group">
          <label>{t('config.subnet')}</label>
          <input
            type="text"
            value={config.subnet}
            onChange={(e) => setConfig({ ...config, subnet: e.target.value })}
            placeholder={t('config.subnetFormat')}
          />
          <small>{t('config.subnetFormat')}</small>
          <div className="field-description">{t('config.subnetDescription')}</div>
        </div>

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={config.obfuscation}
              onChange={(e) => setConfig({ ...config, obfuscation: e.target.checked })}
            />
            {t('config.enableObfuscation')}
          </label>
          <div className="field-description">{t('config.enableObfuscationDescription')}</div>
        </div>

        {config.obfuscation && (
          <>
            <div className="form-group">
              <label>{t('config.obfuscationKey')}</label>
              <div className="input-with-button">
                <input
                  type="text"
                  value={config.obfuscation_key || ''}
                  onChange={(e) => setConfig({ ...config, obfuscation_key: e.target.value })}
                  placeholder={t('config.obfuscationKeyPlaceholder')}
                  maxLength={300}
                  className="mono"
                />
                <button
                  type="button"
                  onClick={generateRandomKey}
                  className="btn-secondary btn-generate-key"
                  title={t('config.generateRandomKey')}
                >
                  {t('config.generateRandomKey')}
                </button>
              </div>
              <div className="field-description">{t('config.obfuscationKeyDescription')}</div>
            </div>

            <div className="form-group">
              <label>{t('config.maskingType')}</label>
              <select
                value={config.masking_type}
                onChange={(e) => setConfig({ ...config, masking_type: e.target.value })}
              >
                <option value="NONE">NONE</option>
                <option value="STUN">STUN</option>
              </select>
              <div className="field-description">{t('config.maskingTypeDescription')}</div>
            </div>

            <div className="form-group">
              <label>
                <input
                  type="checkbox"
                  checked={config.masking_forced}
                  onChange={(e) => setConfig({ ...config, masking_forced: e.target.checked })}
                />
                {t('config.maskingForced')}
              </label>
              <div className="field-description">{t('config.maskingForcedDescription')}</div>
            </div>

            <div className="form-group">
              <label>{t('config.obfuscatorVerbosity')}</label>
              <select
                value={config.obfuscator_verbosity}
                onChange={(e) => setConfig({ ...config, obfuscator_verbosity: e.target.value })}
              >
                <option value="ERROR">ERROR</option>
                <option value="WARNING">WARNING</option>
                <option value="INFO">INFO</option>
                <option value="DEBUG">DEBUG</option>
                <option value="TRACE">TRACE</option>
              </select>
              <div className="field-description">{t('config.obfuscatorVerbosityDescription')}</div>
            </div>
          </>
        )}

        <div className="form-actions">
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? t('common.loading') : t('common.save')}
          </button>
        </div>
      </div>

      <div className="config-section">
        <h2>{t('config.serverKeys')}</h2>
        <div className="info-group">
          <label>{t('dashboard.publicKey')}</label>
          <div className="value code">{config.server_public_key}</div>
        </div>
        <div className="form-actions">
          <button onClick={handleRegenerateKeys} className="btn-warning">
            {t('config.regenerateServerKeys')}
          </button>
        </div>
      </div>

      <div className="config-section">
        <h2>{t('config.grafanaToken')}</h2>
        <div className="field-description">{t('config.grafanaTokenDescription')}</div>
        
        {grafanaToken ? (
          <>
            <div className="form-group">
              <label>{t('config.grafanaToken')}</label>
              <div className="input-with-button">
                <input
                  type="text"
                  value={grafanaToken}
                  readOnly
                  className="mono"
                  style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
                />
                <button
                  type="button"
                  onClick={handleCopyGrafanaToken}
                  className="btn-secondary"
                  title={t('config.copyToken')}
                >
                  {t('config.copyToken')}
                </button>
              </div>
            </div>

            {showGrafanaInstructions && (() => {
              const baseUrl = `${window.location.origin}${(window as any).__WEB_PREFIX__ || ''}/api/grafana`;
              const endpoints = [
                { url: `${baseUrl}/clients`, label: t('config.grafanaEndpointClients') },
                { url: `${baseUrl}/status`, label: t('config.grafanaEndpointStatus') },
                { url: `${baseUrl}/clients/{username}/traffic`, label: t('config.grafanaEndpointTraffic') },
                { url: `${baseUrl}/clients/{username}/traffic-bytes`, label: t('config.grafanaEndpointTrafficBytes') },
              ];

              return (
                <div className="grafana-instructions">
                  <h3>{t('config.grafanaTokenInstructions')}</h3>
                  <div className="instructions-content">
                    <ol style={{ margin: '0 0 1rem 0', paddingLeft: '1.5rem', lineHeight: '1.8' }}>
                      <li>{t('config.grafanaTokenInstructionsStep1')}</li>
                      <li>{t('config.grafanaTokenInstructionsStep2')}</li>
                      <li>
                        {t('config.grafanaTokenInstructionsStep3')}
                        <ul style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
                          {endpoints.map((endpoint, index) => (
                            <li key={index} style={{ marginBottom: '0.5rem' }}>
                              <div className="url-copy-container">
                                <span className="url-label">{endpoint.label}:</span>
                                <code className="url-code">{endpoint.url}</code>
                                <button
                                  type="button"
                                  onClick={() => handleCopyUrl(endpoint.url)}
                                  className="btn-copy-url"
                                  title={t('common.copy')}
                                >
                                  {t('common.copy')}
                                </button>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </li>
                      <li>{t('config.grafanaTokenInstructionsStep4')}</li>
                      <li>{t('config.grafanaTokenInstructionsStep5')}</li>
                      <li>{t('config.grafanaTokenInstructionsStep6')}</li>
                    </ol>
                  </div>
                </div>
              );
            })()}

            <div className="form-actions form-actions-space-between">
              <button
                onClick={handleGenerateGrafanaToken}
                disabled={generatingGrafanaToken}
                className="btn-warning"
              >
                {generatingGrafanaToken ? t('common.loading') : t('config.generateGrafanaToken')}
              </button>
              <button
                onClick={handleDeleteGrafanaToken}
                className="btn-danger"
              >
                {t('config.deleteGrafanaToken')}
              </button>
            </div>
          </>
        ) : (
          <div className="form-actions">
            <button
              onClick={handleGenerateGrafanaToken}
              disabled={generatingGrafanaToken}
              className="btn-warning"
            >
              {generatingGrafanaToken ? t('common.loading') : t('config.generateGrafanaToken')}
            </button>
          </div>
        )}
      </div>

      <div className="config-section">
        <h2>{t('config.systemTimezone')}</h2>
        <div className="info-group">
          <label>{t('config.currentTimezone')}</label>
          <div className="value">
            {currentTimezone} {timezoneOffset && `(${timezoneOffset})`}
          </div>
        </div>

        <div className="form-group">
          <label>{t('config.timezone')}</label>
          <select
            value={selectedTimezone}
            onChange={(e) => setSelectedTimezone(e.target.value)}
            disabled={changingTimezone}
          >
            {availableTimezones.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
          <div className="field-description">{t('config.timezoneDescription')}</div>
        </div>

        <div className="form-actions">
          <button
            onClick={handleChangeTimezone}
            disabled={changingTimezone || selectedTimezone === currentTimezone}
            className="btn-primary"
          >
            {changingTimezone ? t('common.loading') : t('common.save')}
          </button>
        </div>
      </div>

      <div className="config-section">
        <h2>{t('config.adminCredentials')}</h2>
        <div className="info-group">
          <label>{t('config.currentUsername')}</label>
          <div className="value">{currentUsername || '-'}</div>
        </div>
        
        <div className="form-group">
          <label>{t('config.newUsername')}</label>
          <input
            type="text"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            placeholder={currentUsername || t('config.newUsername')}
          />
        </div>

        <div className="form-group">
          <label>{t('config.oldPassword')}</label>
          <input
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            placeholder={t('config.oldPassword')}
            required
          />
        </div>

        <div className="form-group">
          <label>{t('config.newPassword')}</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder={t('config.newPassword')}
          />
          <small>Leave empty to keep current password</small>
        </div>

        {newPassword && (
          <div className="form-group">
            <label>{t('config.confirmNewPassword')}</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder={t('config.confirmNewPassword')}
            />
          </div>
        )}

        <div className="form-actions">
          <button 
            onClick={handleChangeCredentials} 
            disabled={changingCredentials} 
            className="btn-warning"
          >
            {changingCredentials ? t('common.loading') : t('config.changeCredentials')}
          </button>
        </div>
      </div>

      {/* System Restart Modal */}
      {showRestartModal && (
        <div className="restart-modal-overlay" onClick={() => setShowRestartModal(false)}>
          <div className="restart-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="restart-modal-header">
              <h3>{t('config.timezoneRestartModalTitle')}</h3>
            </div>
            <div className="restart-modal-body">
              {restartStatus === 'waiting' && (
                <div className="restart-status">
                  <div className="spinner"></div>
                  <p>{t('config.timezoneRestartModalMessage')}</p>
                </div>
              )}
              {restartStatus === 'checking' && (
                <div className="restart-status">
                  <div className="spinner"></div>
                  <p>{t('config.timezoneRestartModalChecking')}</p>
                </div>
              )}
              {restartStatus === 'success' && (
                <div className="restart-status success">
                  <div className="success-icon">✓</div>
                  <p>{t('config.timezoneRestartModalSuccess')}</p>
                </div>
              )}
              {restartStatus === 'error' && (
                <div className="restart-status error">
                  <div className="error-icon">✗</div>
                  <p>{t('config.timezoneRestartModalError')}</p>
                  <button
                    onClick={() => window.location.reload()}
                    className="btn-primary"
                  >
                    {t('common.refresh')}
                  </button>
                </div>
              )}
            </div>
            {restartStatus !== 'error' && (
              <div className="restart-modal-footer">
                <button
                  onClick={() => setShowRestartModal(false)}
                  className="btn-secondary"
                  disabled={restartStatus === 'waiting' || restartStatus === 'checking'}
                >
                  {t('common.close')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


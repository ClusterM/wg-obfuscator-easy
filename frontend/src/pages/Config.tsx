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

  useEffect(() => {
    loadConfig();
    loadCredentials();
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
    </div>
  );
}


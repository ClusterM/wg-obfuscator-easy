import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import './Dashboard.css';

interface Status {
  external_ip: string;
  external_port: number;
  subnet: string;
  server_ip: string;
  server_public_key: string;
  clients_count: number;
  connected_clients_count: number;
  version?: string;
  wireguard: { running: boolean; error?: string };
  obfuscator: { enabled: boolean; running: boolean; error?: string; version?: string };
}

export default function Dashboard() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Status | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const [statusData, logsData] = await Promise.all([
        api.getStatus(),
        api.getObfuscatorLogs(20).catch(() => ({ lines: [] })),
      ]);
      setStatus(statusData);
      setLogs(logsData.lines || []);
      setError('');
    } catch (err: any) {
      setError(err.message || t('errors.serverError'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading && !status) {
    return <div className="loading">{t('common.loading')}</div>;
  }

  if (error && !status) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="dashboard">
      <h1>{t('dashboard.title')}</h1>

      <div className="status-grid">
        <div className="status-card">
          <h2>{t('dashboard.status')}</h2>
          <div className="status-item">
            <span className="label">{t('dashboard.wireguardStatus')}:</span>
            <span className={`value ${status?.wireguard.running ? 'running' : 'stopped'}`}>
              {status?.wireguard.running ? t('dashboard.running') : t('dashboard.stopped')}
            </span>
          </div>
          <div className="status-item">
            <span className="label">{t('dashboard.obfuscatorStatus')}:</span>
            <span className={`value ${status?.obfuscator.running ? 'running' : 'stopped'}`}>
              {status?.obfuscator.enabled
                ? status.obfuscator.running
                  ? t('dashboard.running')
                  : t('dashboard.stopped')
                : t('dashboard.disabled')}
            </span>
          </div>
          {status?.version && (
            <div className="status-item">
              <span className="label">{t('dashboard.appVersion')}:</span>
              <span className="value">{status.version}</span>
            </div>
          )}
          {status?.obfuscator.version && (
            <div className="status-item">
              <span className="label">{t('dashboard.obfuscatorVersion')}:</span>
              <span className="value">{status.obfuscator.version}</span>
            </div>
          )}
          <div className="status-item">
            <span className="label">{t('dashboard.clientsConnectedTotal')}:</span>
            <span className="value">{status?.connected_clients_count || 0} / {status?.clients_count || 0}</span>
          </div>
        </div>

        <div className="status-card">
          <h2>{t('dashboard.serverInfo')}</h2>
          <div className="status-item">
            <span className="label">{t('dashboard.externalIp')}:</span>
            <span className="value">{status?.external_ip}</span>
          </div>
          <div className="status-item">
            <span className="label">{t('dashboard.externalPort')}:</span>
            <span className="value">{status?.external_port}</span>
          </div>
          <div className="status-item">
            <span className="label">{t('dashboard.serverIp')}:</span>
            <span className="value">{status?.server_ip}</span>
          </div>
          <div className="status-item">
            <span className="label">{t('dashboard.subnet')}:</span>
            <span className="value">{status?.subnet}</span>
          </div>
          <div className="status-item">
            <span className="label">{t('dashboard.publicKey')}:</span>
            <span className="value code">{status?.server_public_key}</span>
          </div>
        </div>
      </div>

      <div className="logs-section">
        <h2>{t('dashboard.recentLogs')}</h2>
        <div className="logs-container">
          {logs.length > 0 ? (
            logs.map((log, idx) => (
              <div key={idx} className="log-line">
                {log}
              </div>
            ))
          ) : (
            <div className="no-logs">{t('dashboard.noLogs')}</div>
          )}
        </div>
      </div>
    </div>
  );
}


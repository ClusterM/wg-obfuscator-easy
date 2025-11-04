import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { logout } from '../services/auth';
import api from '../services/api';
import LanguageSelector from './LanguageSelector';
import './Layout.css';

export default function Layout() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [serverEnabled, setServerEnabled] = useState(true);
  const [loadingEnabled, setLoadingEnabled] = useState(true);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const config = await api.getConfig();
      setServerEnabled(config.enabled !== false);
    } catch (err) {
      console.error('Failed to load config:', err);
    } finally {
      setLoadingEnabled(false);
    }
  };

  const handleToggleServer = async () => {
    const newValue = !serverEnabled;
    setServerEnabled(newValue);
    try {
      await api.updateConfig({ enabled: newValue });
    } catch (err: any) {
      // Revert on error
      setServerEnabled(!newValue);
      alert(err.message || t('errors.serverError'));
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="layout">
      <nav className="navbar">
        <div className="nav-header">
          <div className="nav-brand-center">
            <img src="logo.png" alt="Logo" className="nav-logo" />
            <h1>WireGuard Obfuscator</h1>
          </div>
          <div className="nav-top-actions">
            {!loadingEnabled && (
              <label 
                className="server-toggle"
                title={serverEnabled ? t('config.disableServer') : t('config.enableServer')}
              >
                <input
                  type="checkbox"
                  checked={serverEnabled}
                  onChange={handleToggleServer}
                />
                <span className="slider"></span>
              </label>
            )}
            <LanguageSelector />
            <button onClick={handleLogout} className="btn-logout">
              {t('auth.logout')}
            </button>
          </div>
        </div>
        <div className="nav-tabs">
          <Link
            to="/dashboard"
            className={isActive('/dashboard') ? 'tab-active' : ''}
          >
            {t('nav.dashboard')}
          </Link>
          <Link
            to="/clients"
            className={isActive('/clients') ? 'tab-active' : ''}
          >
            {t('nav.clients')}
          </Link>
          <Link
            to="/config"
            className={isActive('/config') ? 'tab-active' : ''}
          >
            {t('nav.configuration')}
          </Link>
        </div>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}


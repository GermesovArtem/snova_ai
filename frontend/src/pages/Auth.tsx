import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Cloud, User as UserIcon, Loader2, MessageCircle } from 'lucide-react';
import { api } from '../api';
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';

// Global types for Telegram
declare global {
  interface Window {
    Telegram?: any;
    onTelegramAuth?: (user: any) => void;
  }
}

// Отдельный компонент для виджета
function TelegramWidget({ onAuth, onLoaded }: { onAuth: (user: any) => void, onLoaded?: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.onTelegramAuth = (user: any) => onAuth(user);

    if (containerRef.current) {
        containerRef.current.innerHTML = '';
        const script = document.createElement('script');
        script.src = '/telegram-widget.js';
        script.setAttribute('data-telegram-login', 'snovananobananabot');
        script.setAttribute('data-size', 'large');
        script.setAttribute('data-onauth', 'onTelegramAuth(user)');
        script.setAttribute('data-request-access', 'write');
        script.async = true;
        
        script.onload = () => onLoaded?.();
        containerRef.current.appendChild(script);
    }
  }, [onAuth, onLoaded]);

  return (
    <div 
        ref={containerRef} 
        id="telegram-widget-container"
        style={{ minHeight: '40px', display: 'flex', justifyContent: 'center' }}
    ></div>
  );
}

export default function Auth({ onLogin }: { onLogin: () => void }) {
  const navigate = useNavigate();
  
  // Мгновенное определение режима TWA
  const isTWA = useMemo(() => {
    try {
      return !!(window.Telegram?.WebApp?.initData || 
                window.location.hash.includes('tgWebAppData') || 
                new URLSearchParams(window.location.search).get('tgWebAppData'));
    } catch (e) {
      return false;
    }
  }, []);
  
  const [isWebAppAuth, setIsWebAppAuth] = useState(isTWA);
  const [widgetFailed, setWidgetFailed] = useState(false);

  const handleAuth = useCallback(async (data: any, type: 'twa' | 'widget') => {
    try {
      const payload = type === 'twa' ? data : { ...data, auth_type: 'widget' };
      if (type === 'twa') payload.auth_type = 'twa';

      const res = await api.loginTelegram(payload);
      if (res.success && res.access_token) {
        localStorage.setItem('token', res.access_token);
        onLogin();
        navigate('/app', { replace: true });
      } else {
        setIsWebAppAuth(false);
        if (type === 'twa') setWidgetFailed(true);
      }
    } catch (e) {
      setIsWebAppAuth(false);
      setWidgetFailed(true);
    }
  }, [navigate, onLogin]);

  useEffect(() => {
    if (isTWA) {
      const twa = window.Telegram?.WebApp;
      if (twa?.initData) {
        const urlParams = new URLSearchParams(twa.initData);
        const userStr = urlParams.get('user');
        let userId = 0;
        if (userStr) try { userId = JSON.parse(userStr).id; } catch(e) {}
        handleAuth({ initData: twa.initData, id: userId }, 'twa');
      }
    } else {
      // Таймаут на загрузку виджета
      const timer = setTimeout(() => {
          const container = document.getElementById('telegram-widget-container');
          if (!container || container.children.length === 0) {
              setWidgetFailed(true);
          }
      }, 6000); 
      return () => clearTimeout(timer);
    }
  }, [isTWA, handleAuth]);

  const handleFallbackLogin = () => {
    window.location.href = `https://t.me/snovananobananabot?start=login`;
  };

  const handleOAuthPlaceholder = (provider: string) => {
    alert(`Вход через ${provider} будет доступен в следующем обновлении!`);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-color)', color: 'var(--text-color)' }}>
      <header style={{ padding: '20px', display: 'flex', alignItems: 'center' }}>
        <button
          onClick={() => navigate('/')}
          style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}
        >
          <ChevronLeft size={24} />
        </button>
      </header>

      <main style={{ flex: 1, padding: '40px 20px', textAlign: 'center', display: 'flex', flexDirection: 'column', maxWidth: '400px', margin: '0 auto', width: '100%' }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{ marginBottom: '60px' }}
        >
          <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: 'linear-gradient(135deg, #64b5f6, #1976d2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '32px', margin: '0 auto 20px' }}>
            S
          </div>
          <div style={{ fontSize: '28px', fontWeight: 'bold' }}>S•NOVA AI</div>
          <div style={{ fontSize: '15px', color: 'var(--text-muted)', marginTop: '8px' }}>
            Авторизуйтесь, чтобы продолжить
          </div>
        </motion.div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {isWebAppAuth ? (
            <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '15px' }}>
              <Loader2 className="animate-spin" size={32} color="var(--tg-accent)" />
              <span style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Безопасный вход через Telegram...</span>
            </div>
          ) : (
            <>
              {!widgetFailed ? (
                <TelegramWidget onAuth={(user) => handleAuth(user, 'widget')} />
              ) : (
                <button 
                    className="btn btn-primary" 
                    onClick={handleFallbackLogin}
                    style={{ background: 'var(--tg-accent)', width: '100%' }}
                >
                  <MessageCircle size={20} /> Войти через Telegram
                </button>
              )}
            </>
          )}

          <div style={{ width: '100%', height: '1px', background: 'rgba(255,255,255,0.05)', margin: '10px 0' }}></div>

          <button className="tg-key-btn" onClick={() => handleOAuthPlaceholder('Yandex')} style={{ width: '100%', background: 'rgba(255,255,255,0.03)' }}>
            <Cloud size={20} /> Yandex ID
          </button>

          <button className="tg-key-btn" onClick={() => handleOAuthPlaceholder('VK')} style={{ width: '100%', background: 'rgba(255,255,255,0.03)' }}>
            <UserIcon size={20} /> VK ID
          </button>
        </div>

        <p style={{ marginTop: 'auto', padding: '40px 0', fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
          Авторизуясь, вы подтверждаете <br />
          <u>Пользовательское соглашение</u> и <u>Политику конфиденциальности</u>.
        </p>
      </main>
    </div>
  );
}

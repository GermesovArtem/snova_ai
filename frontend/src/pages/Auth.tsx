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
        script.src = 'https://telegram.org/js/telegram-widget.js?22';
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
      }, 6000); // Увеличиваем до 6 секунд
      return () => clearTimeout(timer);
    }
  }, [isTWA, handleAuth]);

  const handleFallbackLogin = () => {
    // В крайнем случае отправляем в бота для авторизации
    window.location.href = `https://t.me/snovananobananabot?start=login`;
  };

  const handleOAuthPlaceholder = (provider: string) => {
    alert(`Вход через ${provider} будет доступен в следующем обновлении!`);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#000', color: '#fff' }}>
      <style>
        {`
          @keyframes customSpin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}
      </style>
      <header style={{ padding: '20px', display: 'flex', alignItems: 'center', zIndex: 10 }}>
        <button
          onClick={() => navigate('/')}
          style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}
        >
          <ChevronLeft size={24} />
        </button>
      </header>

      <main style={{ flex: 1, padding: '40px 20px', textAlign: 'center', display: 'flex', flexDirection: 'column' }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{ marginBottom: '40px' }}
        >
          <div style={{ fontSize: '18px', fontWeight: 600, color: 'rgba(255,255,255,0.6)' }}>
            Добро пожаловать в
          </div>
          <div style={{ fontSize: '32px', fontWeight: 800 }}>S•NOVA AI</div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          style={{ display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center' }}
        >
          {isWebAppAuth ? (
            <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '15px' }}>
              <Loader2 size={32} color="#0088cc" style={{ animation: 'customSpin 1.5s linear infinite' }} />
              <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: '14px' }}>Безопасный вход через Telegram...</span>
            </div>
          ) : (
            <>
              {!widgetFailed ? (
                <TelegramWidget onAuth={(user) => handleAuth(user, 'widget')} />
              ) : (
                <button 
                    className="btn btn-primary" 
                    onClick={handleFallbackLogin}
                    style={{ width: '100%', maxWidth: '300px', background: '#0088cc', borderRadius: '30px', display: 'flex', gap: '10px', alignItems: 'center', justifyContent: 'center' }}
                >
                  <MessageCircle size={20} /> Войти через Telegram
                </button>
              )}
            </>
          )}

          <div style={{ width: '100%', height: '1px', background: 'rgba(255,255,255,0.1)', margin: '15px 0' }}></div>

          <button className="btn btn-secondary glass" onClick={() => handleOAuthPlaceholder('Yandex')} style={{ width: '100%', maxWidth: '300px', borderRadius: '30px' }}>
            <Cloud size={20} /> Yandex ID
          </button>

          <button className="btn btn-secondary glass" onClick={() => handleOAuthPlaceholder('VK')} style={{ width: '100%', maxWidth: '300px', borderRadius: '30px' }}>
            <UserIcon size={20} /> VK ID
          </button>
        </motion.div>

        <p style={{ marginTop: 'auto', padding: '40px 0', fontSize: '12px', color: 'rgba(255,255,255,0.4)', lineHeight: 1.6 }}>
          Авторизуясь, вы подтверждаете <br />
          <u>Пользовательское соглашение</u> и <u>Политику конфиденциальности</u>.
        </p>
      </main>
    </div>
  );
}

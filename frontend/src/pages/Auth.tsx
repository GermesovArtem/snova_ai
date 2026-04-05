import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Cloud, User as UserIcon, Loader2 } from 'lucide-react';
import { api } from '../api';
import { useEffect, useRef, useState } from 'react';

// Global types for Telegram
declare global {
  interface Window {
    Telegram?: any;
    onTelegramAuth?: (user: any) => void;
  }
}

export default function Auth({ onLogin }: { onLogin: () => void }) {
  const navigate = useNavigate();
  const [isWebAppAuth, setIsWebAppAuth] = useState(false);
  const widgetContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 1. Попытка бесшовного входа через Telegram Web App (TWA)
    const initData = window.Telegram?.WebApp?.initData;
    
    if (initData) {
      setIsWebAppAuth(true);
      
      // Парсим ID пользователя, так как он обязателен в схеме бэкенда
      const urlParams = new URLSearchParams(initData);
      const userStr = urlParams.get('user');
      let userId = 0;
      if (userStr) {
        try { userId = JSON.parse(userStr).id; } catch(e) {}
      }

      api.loginTelegram({ 
        auth_type: 'twa', 
        initData: initData,
        id: userId
      }).then(res => {
        if (res.success && res.access_token) {
          localStorage.setItem('token', res.access_token);
          onLogin();
          navigate('/app');
        } else {
          setIsWebAppAuth(false);
          alert("Ошибка авто-входа: " + (res.error || 'Неверная подпись'));
        }
      }).catch(e => {
        setIsWebAppAuth(false);
        console.error(e);
      });
      return;
    }

    // 2. Иначе (мы в обычном браузере) — рендерим виджет
    window.onTelegramAuth = async (user: any) => {
      user.auth_type = 'widget';
      try {
        const res = await api.loginTelegram(user);
        if (res.success && res.access_token) {
          localStorage.setItem('token', res.access_token);
          onLogin();
          navigate('/app');
        } else {
          alert('Ошибка авторизации через виджет: ' + (res.error || 'Неверная подпись'));
        }
      } catch (e) {
        alert('Ошибка сети при авторизации');
      }
    };

    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    // Используем юзернейм вашего бота:
    script.setAttribute('data-telegram-login', 'snovananobananabot');
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-onauth', 'onTelegramAuth(user)');
    script.setAttribute('data-request-access', 'write');
    script.async = true;
    
    if (widgetContainerRef.current) {
      widgetContainerRef.current.innerHTML = '';
      widgetContainerRef.current.appendChild(script);
    }
  }, [navigate, onLogin]);

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
            <div style={{ minHeight: '40px', display: 'flex', justifyContent: 'center' }} ref={widgetContainerRef}></div>
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

import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, MessageCircle, Cloud, User as UserIcon } from 'lucide-react';
import { api } from '../api';

export default function Auth({ onLogin }: { onLogin: () => void }) {
  const navigate = useNavigate();

  const handleMockLogin = async (type: string) => {
    // В реальном сценарии здесь будет вызов OAuth провайдера.
    // Для демо сейчас симулируем успешный вход через наш API.
    const mockData = {
        id: 209,
        first_name: "Web",
        last_name: "User",
        username: "web_user",
        auth_date: Math.floor(Date.now() / 1000),
        hash: "mock_hash"
    };

    try {
        const res = await api.loginTelegram(mockData);
        if (res.success && res.access_token) {
            localStorage.setItem('token', res.access_token);
            onLogin();
            navigate('/app');
        } else {
            alert("Ошибка входа: " + (res.detail || "Неизвестно"));
        }
    } catch (e) {
        alert("Ошибка сети");
    }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#000' }}>
      <header style={{ padding: '20px', display: 'flex', alignItems: 'center' }}>
        <button 
          onClick={() => navigate('/')} 
          style={{ background: 'none', border: 'none', color: '#fff' }}
        >
          <ChevronLeft size={24} />
        </button>
      </header>

      <main style={{ flex: 1, padding: '40px 20px', textAlign: 'center' }}>
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{ marginBottom: '60px' }}
        >
          <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--accent-soft)' }}>
            Добро пожаловать в
          </div>
          <div style={{ fontSize: '32px', fontWeight: 800 }}>S•NOVA AI</div>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
        >
          <button className="btn btn-primary" onClick={() => handleMockLogin('telegram')} style={{ background: '#0088cc', color: '#fff' }}>
            <MessageCircle size={20} fill="#fff" /> Войти через Telegram
          </button>
          
          <button className="btn btn-glass" onClick={() => handleMockLogin('yandex')}>
            <Cloud size={20} /> Yandex ID
          </button>

          <button className="btn btn-glass" onClick={() => handleMockLogin('vk')}>
            <UserIcon size={20} /> VK ID
          </button>
        </motion.div>

        <p style={{ marginTop: 'auto', padding: '40px 20px', fontSize: '12px', color: 'rgba(255,255,255,0.4)', lineHeight: 1.6 }}>
          Авторизуясь, вы подтверждаете <br /> 
          <u>Пользовательское соглашение</u> и <u>Политику конфиденциальности</u>.
        </p>
      </main>
    </div>
  );
}

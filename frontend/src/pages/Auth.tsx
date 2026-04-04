import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Cloud, User as UserIcon, MessageCircle } from 'lucide-react';
import { api } from '../api';

export default function Auth({ onLogin }: { onLogin: () => void }) {
  const navigate = useNavigate();

  const handleTelegramLogin = async () => {
    // В будущем здесь будет переход на OAuth Телеграма.
    // Сейчас, так как виджет по IP блокируется, мы используем надежный метод:
    // Мы отправляем пользователя на бэкенд, который выдает ему токен (для теста).
    // ПОЗЖЕ: заменим на реальный OAuth редирект.

    // ВНИМАНИЕ: Используем ваш реальный ID для входа через кнопку
    const mockUser = {
      id: 6930578591, // ВАШ РЕАЛЬНЫЙ ТЕЛЕГРАМ ID
      first_name: "Artem",
      username: "web_user",
      auth_date: Math.floor(Date.now() / 1000),
      hash: "test_bypass"
    };

    try {
      const res = await api.loginTelegram(mockUser);
      if (res.success && res.access_token) {
        localStorage.setItem('token', res.access_token);
        onLogin();
        navigate('/app');
      }
    } catch (e) {
      alert("Ошибка входа");
    }
  };

  const handleOAuthPlaceholder = (provider: string) => {
    alert(`Вход через ${provider} будет доступен в следующем обновлении!`);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#000', color: '#fff' }}>
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
          <button className="btn btn-primary" onClick={handleTelegramLogin} style={{ width: '100%', maxWidth: '300px', background: '#0088cc', color: '#fff' }}>
            <MessageCircle size={20} fill="#fff" /> Войти через Telegram
          </button>

          <div style={{ width: '100%', height: '1px', background: 'rgba(255,255,255,0.1)', margin: '10px 0' }}></div>

          <button className="btn btn-glass" onClick={() => handleOAuthPlaceholder('Yandex')} style={{ width: '100%', maxWidth: '300px' }}>
            <Cloud size={20} /> Yandex ID
          </button>

          <button className="btn btn-glass" onClick={() => handleOAuthPlaceholder('VK')} style={{ width: '100%', maxWidth: '300px' }}>
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

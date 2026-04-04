import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Image as ImageIcon, Settings, User, CreditCard, ChevronDown, Sparkles } from 'lucide-react';
import { api } from '../api';

interface Message {
  id: string;
  type: 'user' | 'bot';
  text: string;
  image?: string;
}

export default function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', type: 'bot', text: 'Привет! Я S•NOVA AI. Отправь мне фото или опиши словами, что хочешь создать. ✨' }
  ]);
  const [input, setInput] = useState('');
  const [user, setUser] = useState<any>(null);
  const [model, setModel] = useState('nano-banana-2');
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getMe().then(res => {
      if (res.success) {
        setUser(res.data);
        if (res.data.model_preference) setModel(res.data.model_preference);
      }
    });
  }, []);

  const handleSettingsClick = () => {
    console.log("Settings clicked");
    alert("Настройки: выбор модели по умолчанию и параметры профиля будут доступны в следующем обновлении!");
  };

  const handleBalanceClick = () => {
    console.log("Balance clicked");
    alert(`Ваш баланс: ${user?.balance || 0} кр. Пополнить можно через бота @snovananobananabot`);
  };

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const newUserMsg: Message = { id: Date.now().toString(), type: 'user', text: input };
    setMessages(prev => [...prev, newUserMsg]);
    setInput('');

    try {
      const res = await api.generateEdit(input);
      if (res.success) {
        setMessages(prev => [...prev, { 
          id: (Date.now() + 1).toString(), 
          type: 'bot', 
          text: 'Запрос принят! Начинаю генерацию... 🚀' 
        }]);
        // Here we could start polling for the result if task_uuid is returned
      } else {
        setMessages(prev => [...prev, { 
          id: (Date.now() + 1).toString(), 
          type: 'bot', 
          text: `Ошибка: ${res.detail || 'Неизвестная ошибка'}` 
        }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { id: 'err', type: 'bot', text: 'Ошибка связи с сервером.' }]);
      setMessages(prev => [...prev, { id: 'err', type: 'bot', sender: 'bot', text: 'Ошибка связи с сервером.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container" style={{ 
      height: '100vh', 
      display: 'flex', 
      flexDirection: 'column', 
      background: '#000',
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      overflow: 'hidden'
    }}>
      {/* HEADER: Форсируем положение сверху */}
      <header className="header glass" style={{ 
        height: '70px',
        padding: '0 20px', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        position: 'absolute',
        top: 0, left: 0, right: 0,
        zIndex: 9999,
        pointerEvents: 'auto'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
            <img src="/vite.svg" alt="Logo" style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '18px' }}>S•NOVA AI</div>
            <div style={{ fontSize: '12px', color: '#44ff44' }}>Online</div>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
           <button onClick={() => { console.log('LOG: Settings clicked'); handleSettingsClick(); }} className="glass" style={{
            width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff'
          }}>
            <Settings size={20} />
          </button>
          
          <div onClick={() => { console.log('LOG: Balance clicked'); handleBalanceClick(); }} className="glass" style={{
            padding: '8px 16px', borderRadius: '12px', fontSize: '14px', fontWeight: 700, cursor: 'pointer'
          }}>
            {user?.balance || 0} кр.
          </div>
        </div>
      </header>
      <main style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {/* Logo centerpiece when chat is empty-ish */}
        {messages.length < 5 && (
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.05, pointerEvents: 'none' }}>
            <Sparkles size={200} />
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, x: msg.type === 'user' ? 20 : -20 }}
                animate={{ opacity: 1, x: 0 }}
                style={{
                  alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  padding: '12px 16px',
                  borderRadius: msg.type === 'user' ? '20px 20px 4px 20px' : '20px 20px 20px 4px',
                  background: msg.type === 'user' ? '#fff' : 'var(--surface)',
                  color: msg.type === 'user' ? '#000' : '#fff',
                  fontSize: '15px',
                  lineHeight: '1.4',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                }}
              >
                {msg.text}
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={chatEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer style={{ 
        padding: '16px 20px', 
        background: 'rgba(20,20,20,0.8)', 
        backdropFilter: 'blur(10px)',
        borderTop: '1px solid rgba(255,255,255,0.1)',
        zIndex: 1000,
        position: 'relative'
      }}>
        {/* Model Selector Bar */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
           <button className="btn-glass" style={{ fontSize: '12px', padding: '6px 12px', borderRadius: '100px', display: 'flex', gap: '6px' }}>
             <Sparkles size={14} /> {model} <ChevronDown size={14} />
           </button>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button className="btn-glass" style={{ padding: '12px', borderRadius: '16px' }}>
            <ImageIcon size={24} />
          </button>
          
          <div style={{ flex: 1, position: 'relative' }}>
            <input 
              type="text" 
              placeholder="Опиши свою идею..." 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              style={{
                width: '100%',
                background: 'var(--surface)',
                border: '1px solid var(--glass-border)',
                borderRadius: '16px',
                padding: '14px 16px',
                color: '#fff',
                fontSize: '15px',
                outline: 'none'
              }}
            />
          </div>

          <button 
            className="btn-primary" 
            onClick={handleSend}
            style={{ padding: '14px', borderRadius: '16px' }}
          >
            <Send size={24} />
          </button>
        </div>
      </footer>
    </div>
  );
}

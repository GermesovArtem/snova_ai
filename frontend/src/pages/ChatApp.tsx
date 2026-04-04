import { useState, useRef, useEffect } from 'react';
import { Send, Image as ImageIcon, Settings, ChevronDown, X, User } from 'lucide-react';
import { api } from '../api';

interface Message {
  id: string;
  type: 'user' | 'bot';
  text: string;
  sender?: 'user' | 'bot';
}

export default function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', type: 'bot', text: 'Привет! Я S•NOVA AI. Отправь мне фото или опиши словами, что хочешь создать. ✨' }
  ]);
  const [input, setInput] = useState('');
  const [user, setUser] = useState<any>(null);
  const [model, setModel] = useState('nano-banana-2');
  const [isLoading, setIsLoading] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchUserData();
  }, []);

  const fetchUserData = async () => {
    try {
      const res = await api.getMe();
      if (res.success) {
        setUser(res.data);
        if (res.data.model_preference) setModel(res.data.model_preference);
      }
    } catch (e) {
      console.error("Failed to fetch user data", e);
    }
  };

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    setIsLoading(true);
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
      } else {
        setMessages(prev => [...prev, { 
          id: (Date.now() + 1).toString(), 
          type: 'bot', 
          text: `Ошибка: ${res.detail || 'Неизвестная ошибка'}` 
        }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { id: 'err', type: 'bot', text: 'Ошибка связи с сервером.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const updateModel = async (newModel: string) => {
    setModel(newModel);
    setIsModelMenuOpen(false);
    try {
      await api.updateModel(newModel);
      fetchUserData();
    } catch (e) {
      console.error("Failed to update model", e);
    }
  };

  return (
    <div className="chat-container" style={{ 
      height: '100vh', width: '100vw', display: 'flex', flexDirection: 'column', 
      background: '#000', position: 'fixed', top: 0, left: 0, overflow: 'hidden', color: '#fff' 
    }}>
      
      {/* HEADER */}
      <header className="header glass" style={{ 
        height: '70px', padding: '0 20px', display: 'flex', alignItems: 'center', 
        justifyContent: 'space-between', position: 'absolute', top: 0, left: 0, right: 0, zIndex: 1000
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <img src="/vite.svg" alt="S" style={{ width: '24px' }} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '18px' }}>S•NOVA AI</div>
            <div style={{ fontSize: '12px', color: '#44ff44' }}>Online</div>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button onClick={() => setIsSettingsOpen(true)} className="glass" style={{
            width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff'
          }}>
            <Settings size={20} />
          </button>
          
          <div className="glass" style={{ padding: '8px 16px', borderRadius: '12px', fontSize: '14px', fontWeight: 700 }}>
            {user?.balance || 0} кр.
          </div>
        </div>
      </header>

      {/* CHAT AREA */}
      <main style={{ 
        position: 'absolute', top: '70px', bottom: '110px', left: 0, right: 0,
        overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px'
      }}>
        {messages.map((m) => (
          <div key={m.id} style={{
            alignSelf: m.type === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '85%', padding: '12px 16px', borderRadius: '16px',
            background: m.type === 'user' ? '#fff' : 'rgba(255,255,255,0.05)',
            color: m.type === 'user' ? '#000' : '#fff',
            border: m.type === 'user' ? 'none' : '1px solid rgba(255,255,255,0.1)',
            fontSize: '15px'
          }}>
            {m.text}
          </div>
        ))}
        {isLoading && <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '14px' }}>Думаю... ⚡️</div>}
        <div ref={chatEndRef} />
      </main>

      {/* FOOTER */}
      <footer style={{ 
        height: '110px', position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 1000,
        padding: '10px 20px', background: 'linear-gradient(to top, #000 80%, transparent)',
        display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'center'
      }}>
        
        {/* Model Selector Button */}
        <div style={{ position: 'relative' }}>
          <button 
            onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
            className="btn-glass" 
            style={{ padding: '6px 12px', borderRadius: '100px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px', color: 'rgba(255,255,255,0.7)' }}
          >
            <Send size={24} />
          </button>
        </div>
      </footer>
    </div>
  );
}

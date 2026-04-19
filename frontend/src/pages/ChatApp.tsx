import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, Download, Moon, Sun,
  X, Loader2, User, HelpCircle, Sparkles, Smartphone, History, Zap, CheckCircle2, ChevronDown, LogOut,
  Paperclip, Mic, Smile, Search, MoreVertical, ChevronLeft, MessageCircle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';

interface Message {
  id: string;
  type: 'user' | 'bot' | 'bot-confirm';
  text?: string;
  image?: string;
  isGenerating?: boolean;
  timestamp: Date;
  meta?: any; 
}

const haptic = () => { if (typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate(10); };

export default function ChatApp() {
  const [user, setUser] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem('chat_messages');
    return saved ? JSON.parse(saved) : [];
  });
  const [input, setInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  
  // UI States
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [currentModel, setCurrentModel] = useState('nano-banana-2');
  const [isBalanceModalOpen, setIsBalanceModalOpen] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [isContactsModalOpen, setIsContactsModalOpen] = useState(false);
  
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historyTasks, setHistoryTasks] = useState<any[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyDetailsTask, setHistoryDetailsTask] = useState<any>(null);
  const [activeImage, setActiveImage] = useState<string | null>(null); 
  const [historyLightboxTask, setHistoryLightboxTask] = useState<any>(null);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [showPwaPrompt, setShowPwaPrompt] = useState(false);
  const [modelConfig, setModelConfig] = useState<any>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length === 0) {
      initApp();
    }
    document.documentElement.setAttribute('data-theme', theme);
    
    fetchConfig();
    const pwaClosed = localStorage.getItem('pwa_closed');
    if (!pwaClosed) {
      setTimeout(() => setShowPwaPrompt(true), 3000);
    }

    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
    });
  }, [theme]);

  // Persist messages
  useEffect(() => {
    localStorage.setItem('chat_messages', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const initApp = async () => {
    fetchUserData();
    setMessages([{ 
      id: 'welcome', 
      type: 'bot', 
      text: `✨ **Добро пожаловать в S•NOVA AI!**\n\nЯ помогу тебе воплотить любую задумку в арт за считанные секунды.\n\n👇 **Просто отправь текст или фото ниже!**`, 
      timestamp: new Date() 
    }]);
  };

  const fetchUserData = async () => {
    try {
      const res = await api.getMe();
      if (res.success) {
        setUser(res.data);
        setCurrentModel(res.data.model_preference || 'nano-banana-2');
      }
    } catch (e) { console.error(e); }
  };

  const openHistory = async () => {
    haptic();
    setIsHistoryOpen(true);
    setIsHistoryLoading(true);
    try {
      const res = await api.getHistory();
      if (res.success) setHistoryTasks(res.data);
    } catch (e) { console.error(e); }
    setIsHistoryLoading(false);
  };

  const getModelName = (id: string) => {
    if (modelConfig?.available_models) {
      const entry = Object.entries(modelConfig.available_models).find(([name, mid]) => mid === id);
      if (entry) return entry[0];
    }
    return id.includes('pro') ? 'Nano Banana PRO' : 'Nano Banana 2';
  };

  const fetchConfig = async () => {
    try {
      const res = await api.getConfigModels();
      if (res.success) setModelConfig(res.data);
    } catch (e) { console.error("Config fetch error:", e); }
  };

  const fixUrl = (url: string) => {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    return `/${url.replace(/^\//, '')}`;
  };

  const toggleTheme = () => {
    haptic();
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  const handleInitiate = () => {
    if (!input.trim() && selectedFiles.length === 0) return;
    haptic();
    const userMsgId = Date.now().toString() + '-user';
    setMessages(prev => [...prev, {
      id: userMsgId, type: 'user', text: input, image: previews[0], timestamp: new Date()
    }]);
    
    const confirmMsgId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: confirmMsgId, type: 'bot-confirm', 
      image: previews[0], timestamp: new Date(),
      meta: { prompt: input, files: [...selectedFiles], previews: [...previews], model: currentModel }
    }]);
    setInput(''); setSelectedFiles([]); setPreviews([]);
  };

  const handleConfirmGen = async (msgId: string) => {
    haptic();
    const msg = messages.find(m => m.id === msgId);
    if (!msg) return;

    const botMsgId = Date.now().toString();
    
    // Batch update: remove confirmation bubble and add generating bubble in one go 
    // to prevent hitting 0 messages and triggering a welcome reset.
    setMessages(prev => [
      ...prev.filter(m => m.id !== msgId),
      { id: botMsgId, type: 'bot', text: `🚀 Начинаю генерацию...`, isGenerating: true, timestamp: new Date() }
    ]);

    try {
      const res = await api.generateEdit(msg.meta.prompt, msg.meta.files);
      if (res.success) pollStatus(res.data.task_uuid, botMsgId);
      else updateBotMessage(botMsgId, "❌ Ошибка: " + res.error);
    } catch (e: any) { 
      updateBotMessage(botMsgId, `❌ Ошибка соединения`); 
    }
  };

  const pollStatus = async (uuid: string, msgId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await api.checkStatus(uuid);
        if (res.success && (res.data.state === 'success' || res.data.state === 'completed')) {
          clearInterval(interval);
          updateBotMessage(msgId, `🔥 **Результат готов!**`, res.data.image_url);
          fetchUserData();
        } else if (res.data.state === 'failed' || res.data.state === 'error') {
          clearInterval(interval);
          updateBotMessage(msgId, `❌ **Ошибка:** ${res.data.error || "Генерация не удалась"}`);
          fetchUserData();
        } else if (attempts > 120) {
          clearInterval(interval);
          updateBotMessage(msgId, `⚠️ **Тайм-аут.** Проверьте историю позже.`);
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const updateBotMessage = (id: string, text: string, imageUrl?: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, text, image: imageUrl, isGenerating: false } : m));
  };

  const updateModel = async (m: string) => {
    haptic();
    setCurrentModel(m); setIsModelModalOpen(false);
    try { await api.updateModel(m); fetchUserData(); } catch (e) {}
  };

  const downloadImage = (url: string) => {
    window.open(fixUrl(url), '_blank');
  };

  const formatTime = (date: Date | string) => {
    const d = date instanceof Date ? date : new Date(date);
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="chat-container">
      
      {/* HEADER */}
      <header className="chat-header">
        <button 
          onClick={toggleTheme} 
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '10px', display: 'flex' }}
        >
          {theme === 'dark' ? <Sun size={22} /> : <Moon size={22} />}
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, justifyContent: 'center' }}>
          <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'linear-gradient(135deg, #64b5f6, #1976d2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '16px', color: '#fff' }}>
            S
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
            <span style={{ fontWeight: '600', fontSize: '15px' }}>S • NOVA | НЕЙРОФОТО</span>
            <span style={{ fontSize: '12px', color: 'var(--tg-accent)' }}>бот</span>
          </div>
        </div>
        
        <button 
          onClick={() => { localStorage.removeItem('token'); window.location.href='/'; }}
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '10px', display: 'flex' }}
        >
          <LogOut size={22} />
        </button>
      </header>

      {/* MESSAGES */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ margin: '8px auto', background: 'rgba(0,0,0,0.15)', padding: '2px 12px', borderRadius: '12px', fontSize: '12px', color: '#fff', opacity: 0.8 }}>
          {new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
        </div>

        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <div key={msg.id} className={`bubble ${msg.type === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
              
              {msg.image && (
                <div style={{ position: 'relative', marginBottom: msg.text ? '8px' : '0' }}>
                  <img 
                    src={fixUrl(msg.image)} 
                    onClick={() => setActiveImage(fixUrl(msg.image))}
                    style={{ width: '100%', borderRadius: '12px', cursor: 'pointer', display: 'block' }} 
                    alt="attachment" 
                  />
                  {!msg.isGenerating && msg.type === 'bot' && (
                    <button 
                      onClick={() => downloadImage(msg.image!)}
                      style={{ position: 'absolute', bottom: 8, right: 8, background: 'rgba(0,0,0,0.4)', border: 'none', color: '#fff', borderRadius: '50%', padding: '8px', display: 'flex' }}
                    >
                      <Download size={16} />
                    </button>
                  )}
                </div>
              )}

              {msg.type === 'bot-confirm' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ fontSize: '14px' }}>✨ <b>Подтвердите генерацию:</b></div>
                  <div style={{ fontSize: '14px', background: 'rgba(0,0,0,0.15)', padding: '10px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                    {msg.meta?.prompt || 'Без описания'}
                  </div>
                  <div style={{ fontSize: '13px', opacity: 0.8 }}>💰 Стоимость: <b>{modelConfig?.credits_per_model?.[msg.meta?.model] || 3} ⚡</b></div>
                  <button 
                    onClick={() => handleConfirmGen(msg.id)}
                    className="btn btn-primary"
                    style={{ width: '100%', padding: '12px', borderRadius: '12px', fontSize: '15px', fontWeight: 'bold' }}
                  >
                    🚀 Сгенерировать
                  </button>
                </div>
              ) : (
                <div style={{ fontSize: '15px', whiteSpace: 'pre-wrap' }}>
                  {msg.text?.split('**').map((p,i)=> i%2?<b key={i}>{p}</b>:p)}
                </div>
              )}

              <div style={{ textAlign: 'right', fontSize: '10px', opacity: 0.5, marginTop: '4px' }}>
                {formatTime(msg.timestamp)}
              </div>
            </div>
          ))}
        </AnimatePresence>
        
        {messages.some(m => m.isGenerating) && (
          <div className="bubble bubble-bot" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Loader2 className="animate-spin" size={14} />
            <span style={{ fontSize: '13px' }}>Создаю шедевр...</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </main>

      {/* FOOTER */}
      <footer className="chat-footer">
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', padding: '0 0 10px 0', overflowX: 'auto' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                <img src={src} style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: '12px', border: '1px solid var(--tg-accent)' }} alt="preview" />
                <button 
                  onClick={() => { setPreviews(p => p.filter((_, idx) => idx !== i)); setSelectedFiles(f => f.filter((_, idx) => idx !== i)); }}
                  style={{ position: 'absolute', top: -6, right: -6, background: '#ff3b30', border: 'none', borderRadius: '50%', color: '#fff', width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="floating-input-wrap">
          <Paperclip size={24} className="clickable" style={{ color: 'var(--text-muted)', padding: '4px' }} onClick={() => fileInputRef.current?.click()} />
          <div style={{ flex: 1 }}>
            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleInitiate(); } }}
              placeholder="Сообщение..."
              rows={1}
              style={{ width: '100%', background: 'none', border: 'none', color: 'inherit', fontSize: '16px', resize: 'none', padding: '10px 4px', maxHeight: '160px' }}
            />
          </div>
          <Smile size={24} className="clickable" style={{ color: 'var(--text-muted)', padding: '4px' }} />
          {input.trim() || selectedFiles.length > 0 ? (
            <Send size={24} className="clickable" style={{ color: 'var(--tg-accent)', padding: '4px' }} onClick={handleInitiate} />
          ) : (
            <Mic size={24} className="clickable" style={{ color: 'var(--text-muted)', padding: '4px' }} />
          )}
        </div>

        {/* CUSTOM KEYBOARD */}
        <div className="tg-keyboard">
          <button className="tg-key-btn" onClick={() => { haptic(); initApp(); }}><Sparkles size={20} /> Создать</button>
          <button className="tg-key-btn" onClick={() => { haptic(); setIsModelModalOpen(true); }}><Settings size={20} /> Модель</button>
          <button className="tg-key-btn" onClick={() => { haptic(); setIsBalanceModalOpen(true); }}><Zap size={20} /> Баланс</button>
          <button className="tg-key-btn" onClick={() => { haptic(); setIsContactsModalOpen(true); }}><User size={20} /> Контакты</button>
        </div>
      </footer>

      {/* HIDDEN INPUT, MODALS, etc... */}
      <input type="file" multiple ref={fileInputRef} hidden accept="image/*" onChange={e => {
        if (e.target.files) {
          const files = Array.from(e.target.files);
          setSelectedFiles(p => [...p, ...files]);
          files.forEach(f => {
            const r = new FileReader(); r.onloadend = () => setPreviews(p => [...p, r.result as string]); r.readAsDataURL(f);
          });
        }
      }} />

      <AnimatePresence>
        {isBalanceModalOpen && (
          <div className="modal-overlay" onClick={() => setIsBalanceModalOpen(false)}>
            <motion.div className="modal-content" initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 50, opacity: 0 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header" style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)' }}>
                 <span style={{ fontWeight: 'bold', fontSize: '18px' }}>💳 Пополнить баланс</span>
                 <X size={24} className="clickable" onClick={() => setIsBalanceModalOpen(false)} />
              </div>
              <div className="modal-body" style={{ padding: '24px' }}>
                <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                   <div style={{ fontSize: '36px', fontWeight: '900', color: 'var(--tg-accent)' }}>{user?.balance || 0} ⚡</div>
                   <div style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '4px' }}>Ваш текущий баланс</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {[ {id:'149', cr: 30, p:'149₽'}, {id:'299', cr: 65, p:'299₽'}, {id:'990', cr: 270, p:'990₽'} ].map(p => (
                    <button key={p.id} className="tg-key-btn" style={{ justifyContent: 'space-between', padding: '18px' }} onClick={() => api.createPayment(p.id).then(r=>r.success&&(window.location.href=r.data.payment_url))}>
                      <span style={{ fontSize: '16px' }}>{p.cr} ⚡</span> 
                      <span style={{ color: 'var(--tg-accent)', fontWeight: 'bold', fontSize: '16px' }}>{p.p}</span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        )}

        {isModelModalOpen && (
          <div className="modal-overlay" onClick={() => setIsModelModalOpen(false)}>
            <motion.div className="modal-content" initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 50, opacity: 0 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header" style={{ padding: '20px', borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between' }}>
                 <span style={{ fontWeight: 'bold', fontSize: '18px' }}>🤖 Выберите нейросеть</span>
                 <X size={24} className="clickable" onClick={() => setIsModelModalOpen(false)} />
              </div>
              <div className="modal-body" style={{ padding: '20px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '10px' }}>
                  {modelConfig?.available_models && Object.entries(modelConfig.available_models).map(([name, id]: [string, any]) => (
                    <button key={id} onClick={() => updateModel(id)} className="tg-key-btn" style={{ justifyContent: 'space-between', background: currentModel === id ? 'var(--tg-accent)' : 'var(--tg-button-light)', color: currentModel === id ? '#fff' : 'inherit' }}>
                      <span style={{ fontWeight: 'bold' }}>{name}</span>
                      <span style={{ opacity: 0.8, fontSize: '14px' }}>{modelConfig.credits_per_model?.[id]} ⚡</span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        )}

        {isContactsModalOpen && (
          <div className="modal-overlay" onClick={() => setIsContactsModalOpen(false)}>
            <motion.div className="modal-content" initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 50, opacity: 0 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header" style={{ padding: '20px', borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between' }}>
                 <span style={{ fontWeight: 'bold', fontSize: '18px' }}>📬 Контакты</span>
                 <X size={24} className="clickable" onClick={() => setIsContactsModalOpen(false)} />
              </div>
              <div className="modal-body" style={{ textAlign: 'center', padding: '30px 20px' }}>
                <div style={{ fontSize: '16px', lineHeight: 1.6, marginBottom: '24px', opacity: 0.9 }}>
                  При возникновении трудностей или предложений по работе сервиса пишите нашему администратору.
                </div>
                <button 
                  className="btn" 
                  style={{ 
                    width: '100%', 
                    padding: '16px', 
                    fontSize: '16px', 
                    borderRadius: '16px', 
                    background: '#24A1DE', 
                    color: '#fff',
                    boxShadow: '0 4px 15px rgba(36, 161, 222, 0.3)'
                  }} 
                  onClick={() => window.open('https://t.me/artemgavr1lov', '_blank')}
                >
                  <MessageCircle size={20} style={{ marginRight: '8px' }} /> Написать в Telegram
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* FULL-SCREEN IMAGE VIEW */}
      {activeImage && (
        <div className="modal-overlay" style={{ background: 'rgba(0,0,0,0.95)', zIndex: 10000 }} onClick={() => setActiveImage(null)}>
           <motion.img 
             initial={{ scale: 0.9, opacity: 0 }} 
             animate={{ scale: 1, opacity: 1 }} 
             src={activeImage} 
             style={{ maxWidth: '95%', maxHeight: '95%', borderRadius: '12px', boxShadow: '0 20px 50px rgba(0,0,0,0.5)' }} 
             alt="full view" 
           />
           <X size={32} style={{ position: 'absolute', top: 30, right: 30, color: '#fff', cursor: 'pointer' }} onClick={() => setActiveImage(null)} />
        </div>
      )}

    </div>
  );
}

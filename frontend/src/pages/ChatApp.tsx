import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, Download, Moon, Sun,
  X, Loader2, User, HelpCircle, Sparkles, Smartphone, History, Zap, CheckCircle2, ChevronDown, LogOut,
  Paperclip, Mic, Smile, Search, MoreVertical, ChevronLeft
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
    setMessages(prev => prev.filter(m => m.id !== msgId));
    const botMsgId = Date.now().toString();
    setMessages(prev => [...prev, { id: botMsgId, type: 'bot', text: `🚀 Начинаю генерацию...`, isGenerating: true, timestamp: new Date() }]);
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
      <header style={{ 
        height: '60px', 
        background: 'var(--tg-header)', 
        display: 'flex', 
        alignItems: 'center', 
        padding: '0 16px',
        boxShadow: 'var(--shadow-sm)',
        zIndex: 100
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, #64b5f6, #1976d2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '18px' }}>
            S
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontWeight: '600', fontSize: '16px' }}>S • NOVA | НЕЙРОФОТО</span>
            <span style={{ fontSize: '13px', color: 'var(--tg-accent)' }}>бот</span>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '16px', color: 'var(--text-muted)' }}>
          <Search size={20} className="clickable" />
          <MoreVertical size={20} className="clickable" onClick={toggleTheme} />
        </div>
      </header>

      {/* MESSAGES */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ margin: '8px auto', background: 'rgba(0,0,0,0.2)', padding: '2px 10px', borderRadius: '10px', fontSize: '12px', color: '#fff', opacity: 0.8 }}>
          19 апреля
        </div>

        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <div key={msg.id} className={`bubble ${msg.type === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
              
              {msg.image && (
                <div style={{ position: 'relative', marginBottom: msg.text ? '8px' : '0' }}>
                  <img 
                    src={fixUrl(msg.image)} 
                    onClick={() => setActiveImage(fixUrl(msg.image))}
                    style={{ width: '100%', borderRadius: '8px', cursor: 'pointer', display: 'block' }} 
                    alt="attachment" 
                  />
                  {!msg.isGenerating && msg.type === 'bot' && (
                    <button 
                      onClick={() => downloadImage(msg.image!)}
                      style={{ position: 'absolute', bottom: 8, right: 8, background: 'rgba(0,0,0,0.5)', border: 'none', color: '#fff', borderRadius: '50%', padding: '6px' }}
                    >
                      <Download size={16} />
                    </button>
                  )}
                </div>
              )}

              {msg.type === 'bot-confirm' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '14px' }}>✨ <b>Подтвердите генерацию:</b></div>
                  <div style={{ fontSize: '14px', background: 'rgba(0,0,0,0.1)', padding: '8px', borderRadius: '8px' }}>
                    {msg.meta?.prompt || 'Без описания'}
                  </div>
                  <div style={{ fontSize: '13px', opacity: 0.8 }}>💰 Стоимость: <b>{modelConfig?.credits_per_model?.[msg.meta?.model] || 3} ⚡</b></div>
                  <button 
                    onClick={() => handleConfirmGen(msg.id)}
                    className="btn btn-primary"
                    style={{ width: '100%', padding: '8px', borderRadius: '8px', fontSize: '14px' }}
                  >
                    🚀 Сгенерировать
                  </button>
                </div>
              ) : (
                <div style={{ fontSize: '15px', whiteSpace: 'pre-wrap' }}>
                  {msg.text?.split('**').map((p,i)=> i%2?<b key={i}>{p}</b>:p)}
                </div>
              )}

              <div style={{ textAlign: 'right', fontSize: '10px', opacity: 0.5, marginTop: '2px' }}>
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

      {/* INPUT AREA */}
      <footer style={{ background: 'var(--tg-footer)', borderTop: '1px solid var(--glass-border)' }}>
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', padding: '8px 16px', overflowX: 'auto' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                <img src={src} style={{ width: '60px', height: '60px', objectFit: 'cover', borderRadius: '8px' }} alt="preview" />
                <button 
                  onClick={() => { setPreviews(p => p.filter((_, idx) => idx !== i)); setSelectedFiles(f => f.filter((_, idx) => idx !== i)); }}
                  style={{ position: 'absolute', top: -4, right: -4, background: '#ff3b30', border: 'none', borderRadius: '50%', color: '#fff', width: '20px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', gap: '8px' }}>
          <Paperclip size={22} className="clickable" style={{ color: 'var(--text-muted)' }} onClick={() => fileInputRef.current?.click()} />
          <div style={{ flex: 1, position: 'relative' }}>
            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleInitiate(); } }}
              placeholder="Сообщение..."
              rows={1}
              style={{ width: '100%', background: 'none', border: 'none', color: 'inherit', fontSize: '16px', resize: 'none', padding: '8px 0', maxHeight: '120px' }}
            />
          </div>
          <Smile size={22} className="clickable" style={{ color: 'var(--text-muted)' }} />
          {input.trim() || selectedFiles.length > 0 ? (
            <Send size={22} className="clickable" style={{ color: 'var(--tg-accent)' }} onClick={handleInitiate} />
          ) : (
            <Mic size={22} className="clickable" style={{ color: 'var(--text-muted)' }} />
          )}
        </div>

        {/* CUSTOM KEYBOARD */}
        <div className="tg-keyboard">
          <button className="tg-key-btn" onClick={() => { haptic(); initApp(); }}><Sparkles size={18} /> Создать</button>
          <button className="tg-key-btn" onClick={() => { haptic(); setIsModelModalOpen(true); }}><Settings size={18} /> Модель</button>
          <button className="tg-key-btn" onClick={() => { haptic(); setIsBalanceModalOpen(true); }}><Zap size={18} /> Баланс</button>
          <button className="tg-key-btn" onClick={() => { haptic(); setIsContactsModalOpen(true); }}><User size={18} /> Контакты</button>
        </div>
      </footer>

      {/* HIDDEN INPUT */}
      <input type="file" multiple ref={fileInputRef} hidden accept="image/*" onChange={e => {
        if (e.target.files) {
          const files = Array.from(e.target.files);
          setSelectedFiles(p => [...p, ...files]);
          files.forEach(f => {
            const r = new FileReader(); r.onloadend = () => setPreviews(p => [...p, r.result as string]); r.readAsDataURL(f);
          });
        }
      }} />

      {/* MODALS */}
      <AnimatePresence>
        {isBalanceModalOpen && (
          <div className="modal-overlay" onClick={() => setIsBalanceModalOpen(false)}>
            <motion.div className="modal-content" initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 50, opacity: 0 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                 <span style={{ fontWeight: 'bold' }}>💳 Пополнить баланс</span>
                 <X size={20} className="clickable" onClick={() => setIsBalanceModalOpen(false)} />
              </div>
              <div className="modal-body">
                <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                   <div style={{ fontSize: '32px', marginBottom: '8px' }}>{user?.balance || 0} ⚡</div>
                   <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Ваш текущий баланс</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {[ {id:'149', cr: 30, p:'149₽'}, {id:'299', cr: 65, p:'299₽'}, {id:'990', cr: 270, p:'990₽'} ].map(p => (
                    <button key={p.id} className="tg-key-btn" style={{ justifyContent: 'space-between', padding: '16px' }} onClick={() => api.createPayment(p.id).then(r=>r.success&&(window.location.href=r.data.payment_url))}>
                      <span>{p.cr} ⚡</span> 
                      <span style={{ color: 'var(--tg-accent)', fontWeight: 'bold' }}>{p.p}</span>
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
              <div className="modal-header">
                 <span style={{ fontWeight: 'bold' }}>🤖 Выберите нейросеть</span>
                 <X size={20} className="clickable" onClick={() => setIsModelModalOpen(false)} />
              </div>
              <div className="modal-body">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '10px' }}>
                  {modelConfig?.available_models && Object.entries(modelConfig.available_models).map(([name, id]: [string, any]) => (
                    <button key={id} onClick={() => updateModel(id)} className="tg-key-btn" style={{ justifyContent: 'space-between', background: currentModel === id ? 'var(--tg-accent)' : 'var(--tg-button)', color: currentModel === id ? '#fff' : 'inherit' }}>
                      <span>{name}</span>
                      <span style={{ opacity: 0.7, fontSize: '12px' }}>{modelConfig.credits_per_model?.[id]} ⚡</span>
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
              <div className="modal-header">
                 <span style={{ fontWeight: 'bold' }}>📬 Контакты</span>
                 <X size={20} className="clickable" onClick={() => setIsContactsModalOpen(false)} />
              </div>
              <div className="modal-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '15px', lineHeight: 1.6, marginBottom: '20px' }}>
                  По всем вопросам, предложениям или при возникновении трудностей пишите нашему администратору.
                </div>
                <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => window.open('https://t.me/artemgavr1lov', '_blank')}>
                  Написать в Telegram
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* FULL-SCREEN IMAGE */}
      {activeImage && (
        <div className="modal-overlay" style={{ background: 'rgba(0,0,0,0.95)' }} onClick={() => setActiveImage(null)}>
           <img src={activeImage} style={{ maxWidth: '100%', maxHeight: '100%' }} alt="full view" />
           <X size={32} style={{ position: 'absolute', top: 20, right: 20, color: '#fff' }} className="clickable" />
        </div>
      )}

    </div>
  );
}

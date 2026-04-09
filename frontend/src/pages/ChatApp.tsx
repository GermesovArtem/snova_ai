import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, Download, Moon, Sun,
  X, Loader2, User, HelpCircle, Sparkles, Smartphone, History, Zap, CheckCircle2, ChevronDown
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
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
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

  const getCreditsLabel = (num: number) => "⚡";

  const getModelName = (id: string) => {
    if (modelConfig?.available_models) {
      const entry = Object.entries(modelConfig.available_models).find(([name, mid]) => mid === id);
      if (entry) return entry[0];
    }
    if (id === 'nano-banana-2-1k') return 'Nano Banana 2 (1K)';
    if (id === 'nano-banana-2-4k') return 'Nano Banana 2 (4K)';
    if (id === 'nano-banana-pro-2k') return 'Nano Banana PRO (2K)';
    if (id === 'nano-banana-pro-4k') return 'Nano Banana PRO (4K)';
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

  const handleInstallPwa = async () => {
    haptic();
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') setDeferredPrompt(null);
      setShowPwaPrompt(false);
    } else {
      alert("Для установки:\n\nChrome: Нажмите (⋮) -> 'Установить приложение'\nSafari: Нажмите 'Поделиться' -> 'На экран Домой'");
    }
  };

  const handleInitiate = () => {
    if (!input.trim() && selectedFiles.length === 0) return;
    haptic();
    const confirmMsgId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: confirmMsgId, type: 'bot-confirm', 
      image: previews[0], timestamp: new Date(),
      meta: { prompt: input, files: [...selectedFiles], previews: [...previews], model: currentModel }
    }]);
    setInput(''); setSelectedFiles([]); setPreviews([]);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  };

  const handleConfirmGen = async (msgId: string) => {
    haptic();
    const msg = messages.find(m => m.id === msgId);
    if (!msg) return;
    setMessages(prev => prev.filter(m => m.id !== msgId));
    const botMsgId = Date.now().toString();
    setMessages(prev => [...prev, { id: botMsgId, type: 'bot', text: `🚀 Начинаю генерацию...`, isGenerating: true, timestamp: new Date() }]);
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    try {
      const res = await api.generateEdit(msg.meta.prompt, msg.meta.files);
      if (res.success) pollStatus(res.data.task_uuid, botMsgId);
      else updateBotMessage(botMsgId, "❌ Ошибка: " + res.error);
    } catch (e: any) { 
      const errMsg = e.message || "Ошибка соединения";
      updateBotMessage(botMsgId, `❌ ${errMsg}`); 
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
          const errMsg = res.data.error || "Произошла ошибка при генерации.";
          updateBotMessage(msgId, `❌ **Ошибка:** ${errMsg}\n\nБаланс был возвращен на ваш счет.`);
          fetchUserData();
        } else if (attempts > 120) { // 6 minutes timeout
          clearInterval(interval);
          updateBotMessage(msgId, `⚠️ **Тайм-аут:** Генерация занимает слишком много времени. Пожалуйста, проверьте историю позже.`);
        }
      } catch (e) { 
        console.error("Polling error:", e);
      }
    }, 3000);
  };

  const updateBotMessage = (id: string, text: string, imageUrl?: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, text, image: imageUrl, isGenerating: false } : m));
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  };

  const updateModel = async (m: string) => {
    haptic();
    setCurrentModel(m); setIsModelMenuOpen(false);
    try { await api.updateModel(m); fetchUserData(); } catch (e) {}
  };

  const downloadImage = async (url: string) => {
    haptic();
    const fullUrl = fixUrl(url);
    window.open(fullUrl, '_blank');
  };

  // Helper to parse reference images
  const getPromptImages = (task: any): string[] => {
    if (task.prompt_images_json) {
      try { return JSON.parse(task.prompt_images_json); } catch(e) { return []; }
    }
    return task.prompt_image_url ? [task.prompt_image_url] : [];
  };

  return (
    <div className="chat-app" style={{ height: '100dvh', width: '100vw', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-color)' }}>
      
      {/* HEADER */}
      <header className="glass glass-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 18px', margin: '0', borderRadius: '0 0 24px 24px', zIndex: 100, borderTop: 'none' }}>
        <motion.button 
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={toggleTheme} 
          style={{ background: 'none', border: 'none', color: 'inherit', padding: 8, display: 'flex' }} 
          className="clickable"
        >
          {theme === 'dark' ? <Sun size={24} /> : <Moon size={24} />}
        </motion.button>
        
        <div style={{ textAlign: 'center', flex: 1, margin: '0 10px', overflow: 'hidden' }}>
          <div style={{ fontWeight: 900, fontSize: '20px', letterSpacing: '-0.8px', whiteSpace: 'nowrap', background: 'linear-gradient(90deg, #fff, #999)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>S•NOVA AI</div>
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.8 }}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', fontSize: '10px', marginTop: '2px' }}
          >
             <div className="status-dot"></div>
             <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{getModelName(currentModel)}</span>
          </motion.div>
        </div>
        
        <motion.button 
          initial={{ x: 20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setIsSettingsMenuOpen(true)}
          className="balance-pill clickable" 
          style={{ 
            padding: '8px 16px', 
            borderRadius: '20px', 
            fontSize: '16px', 
            fontWeight: 900, 
            display: 'flex', 
            alignItems: 'center', 
            gap: '6px', 
            background: 'linear-gradient(135deg, #facc15 0%, #eab308 100%)', 
            color: '#000',
            border: 'none', 
            whiteSpace: 'nowrap',
            boxShadow: '0 8px 20px rgba(250, 204, 21, 0.3)'
          }}
        >
          <span style={{ fontSize: '18px' }}>⚡</span>
          {user ? `${Math.floor(user.balance)}` : '...'}
        </motion.button>
      </header>

      {/* CHAT AREA */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '20px 15px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <AnimatePresence initial={false}>
          {messages.map((msg, index) => (
            <motion.div 
              key={msg.id || index}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              style={{ 
                alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}
            >
              <div 
                className="glass"
                style={{ 
                  padding: '14px 18px', 
                  borderRadius: msg.type === 'user' ? '22px 22px 4px 22px' : '22px 22px 22px 4px',
                  background: msg.type === 'user' 
                    ? 'linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 100%)' 
                    : 'var(--glass-bg)',
                  boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                {msg.type === 'bot' && !msg.image && (
                  <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: 'linear-gradient(to bottom, #7c3aed, #db2777)', opacity: 0.6 }}></div>
                )}
                
                {msg.image && (
                  <div style={{ position: 'relative', marginBottom: msg.text ? '12px' : '0' }}>
                    <img 
                      src={fixUrl(msg.image)} 
                      onClick={() => setActiveImage(fixUrl(msg.image))} 
                      className="clickable" 
                      style={{ width: '100%', maxHeight: '45dvh', borderRadius: '16px', objectFit: 'cover' }} 
                      alt="result"
                    />
                    {!msg.isGenerating && msg.type === 'bot' && (
                      <button 
                        onClick={() => downloadImage(msg.image!)} 
                        style={{ position: 'absolute', bottom: 10, right: 10, background: 'rgba(0,0,0,0.6)', padding: '10px', borderRadius: '50%', border: 'none', color: '#fff' }}
                        className="clickable"
                      >
                        <Download size={18} />
                      </button>
                    )}
                  </div>
                )}

                {msg.type === 'bot-confirm' && msg.meta ? (
                  <>
                    <div style={{ marginBottom: '12px' }}>✨ <b>Готовы начать генерацию?</b></div>
                    <div 
                      onClick={() => { haptic(); navigator.clipboard.writeText(msg.meta.prompt || ''); alert('Промпт скопирован!'); }}
                      className="clickable"
                      style={{ background: 'rgba(255,255,255,0.1)', padding: '12px', borderRadius: '12px', marginBottom: '12px', fontSize: '14px', border: '1px solid var(--glass-border)' }}
                    >
                       📝 {msg.meta.prompt || 'Без описания'}
                    </div>
                    <div style={{ fontSize: '13px', opacity: 0.8 }}>💰 Стоимость: <b>{
                      modelConfig?.credits_per_model?.[msg.meta.model] || 
                      (msg.meta.model.includes('pro') ? 4 : 3)
                    } ⚡</b></div>
                  </>
                ) : msg.text && (
                  <div style={{ fontSize: '15px', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                    {msg.text.split('**').map((p,i)=> i%2?<b key={i}>{p}</b>:p)}
                  </div>
                )}
                
                <div style={{ textAlign: 'right', fontSize: '10px', opacity: 0.4, marginTop: '6px' }}>
                  {new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(msg.timestamp instanceof Date ? msg.timestamp : new Date(msg.timestamp))}
                </div>

                {msg.type === 'bot-confirm' && (
                  <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <button 
                      onClick={() => handleConfirmGen(msg.id!)} 
                      className="btn-inline clickable" 
                      style={{ background: 'var(--text-color)', color: 'var(--bg-color)', fontWeight: 800, padding: '12px', borderRadius: '14px', border: 'none' }}
                    >
                      🚀 Сгенерировать
                    </button>
                    <button 
                      onClick={() => setMessages(p => p.filter(m => m.id !== msg.id))} 
                      className="btn-inline clickable"
                      style={{ padding: '10px', borderRadius: '14px', border: 'none', background: 'rgba(255,255,255,0.05)', color: 'inherit' }}
                    >
                      Отмена
                    </button>
                  </div>
                )}
              </div>
              <div style={{ fontSize: '10px', opacity: 0.5, alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start', padding: '0 5px' }}>
                {msg.type === 'user' ? 'Вы' : getModelName(msg.meta?.model || currentModel)}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {messages.some(m => m.isGenerating) && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ alignSelf: 'flex-start', display: 'flex', gap: '8px', alignItems: 'center', padding: '10px 15px' }}
          >
            <Loader2 className="animate-spin" size={18} />
            <span style={{ fontSize: '13px', opacity: 0.7 }}>S•NOVA создает...</span>
          </motion.div>
        )}
        <div ref={chatEndRef} />
      </main>

      {/* FOOTER */}
      <footer className="glass" style={{ padding: '15px', borderRadius: '24px 24px 0 0', borderBottom: 'none' }}>
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', overflowX: 'auto', paddingBottom: '5px' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                <img src={src} style={{ height: '70px', width: '70px', objectFit: 'cover', borderRadius: '12px', border: '2px solid var(--accent-color)' }} alt="preview" />
                <button 
                  onClick={() => {
                    setPreviews(p => p.filter((_, idx) => idx !== i));
                    setSelectedFiles(f => f.filter((_, idx) => idx !== i));
                  }}
                  style={{ position: 'absolute', top: '-8px', right: '-8px', background: '#ff3b30', color: '#fff', border: 'none', borderRadius: '50%', width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 2px 5px rgba(0,0,0,0.3)' }}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '10px' }}>
          <button 
            className="clickable"
            onClick={() => { haptic(); fileInputRef.current?.click(); }}
            style={{ background: 'var(--glass-bg)', border: 'none', borderRadius: '15px', width: '48px', height: '48px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'inherit' }}
          >
            <ImageIcon size={22} />
          </button>
          
          <div style={{ flex: 1, position: 'relative', display: 'flex', background: 'var(--glass-bg)', borderRadius: '20px', border: '1px solid var(--glass-border)', paddingRight: '5px', overflow: 'hidden' }}>
            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleInitiate();
                }
              }}
              placeholder="Спроси о чем угодно..."
              style={{ 
                flex: 1, 
                background: 'none', 
                border: 'none', 
                color: 'inherit', 
                padding: '12px 15px', 
                fontSize: '16px', 
                outline: 'none', 
                resize: 'none',
                maxHeight: '150px',
                minHeight: '48px'
              }}
              rows={1}
            />
            <button 
              onClick={handleInitiate}
              disabled={messages.some(m => m.isGenerating) || (!input.trim() && selectedFiles.length === 0)}
              style={{ 
                alignSelf: 'center',
                background: input.trim() ? 'var(--text-color)' : 'transparent', 
                color: input.trim() ? 'var(--bg-color)' : 'inherit', 
                border: 'none', 
                borderRadius: '15px', 
                width: '38px', 
                height: '38px', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center', 
                transition: 'all 0.2s ease',
                opacity: (messages.some(m => m.isGenerating) || (!input.trim() && selectedFiles.length === 0)) ? 0.3 : 1
              }}
            >
              {messages.some(m => m.isGenerating) ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
            </button>
          </div>
        </div>
        
        <input 
          id="fileInput"
          type="file" 
          multiple 
          ref={fileInputRef}
          accept="image/*" 
          style={{ display: 'none' }} 
          onChange={e => {
            if (e.target.files) {
              const files = Array.from(e.target.files);
              setSelectedFiles(p => [...p, ...files]);
              files.forEach(f => {
                const r = new FileReader(); r.onloadend = () => setPreviews(p => [...p, r.result as string]); r.readAsDataURL(f);
              });
            }
          }}
        />
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', marginTop: '15px', padding: '0 5px' }}>
          <button onClick={() => { haptic(); initApp(); }} className="btn-bot"><Sparkles size={18} /><br/>Создать</button>
          <button onClick={() => { haptic(); setIsModelMenuOpen(true); }} className="btn-bot"><Settings size={18} /><br/>Модель</button>
          <button onClick={openHistory} className="btn-bot"><History size={18} /><br/>История</button>
          <button onClick={() => { haptic(); setIsSettingsMenuOpen(true); }} className="btn-bot"><User size={18} /><br/>Баланс</button>
        </div>
      </footer>

      {/* FULL-SCREEN IMAGE VIEW */}
      {activeImage && (
        <div onClick={() => setActiveImage(null)} style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.98)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '10px' }}>
          <img src={activeImage} style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: '12px' }} />
          <X style={{ position: 'absolute', top: 30, right: 30, color: '#fff' }} size={35} className="clickable" />
        </div>
      )}

      {/* MODAL: HISTORY GRID */}
      {isHistoryOpen && (
        <div className="history-portal" style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'var(--bg-color)', display: 'flex', flexDirection: 'column' }}>
          <header style={{ padding: '15px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)' }}>
             <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 900 }}>Мои работы</h2>
             <button onClick={() => setIsHistoryOpen(false)} style={{ background: 'var(--glass-bg)', border: 'none', color: '#fff', padding: '8px', borderRadius: '12px' }} className="clickable">
               <X size={24} />
             </button>
          </header>
          <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
            {isHistoryLoading ? (
              <div className="history-grid">
                {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton history-item-square" />)}
              </div>
            ) : historyTasks?.length === 0 ? (
              <div style={{ textAlign: 'center', opacity: 0.5, marginTop: '150px' }}>
                 <Sparkles size={48} style={{ marginBottom: '15px', opacity: 0.2 }} />
                 <div>Ваша история пуста</div>
              </div>
            ) : (
              <div className="history-grid">
                {historyTasks.filter(t => t.image_url && t.status === 'completed').map(task => (
                  <div key={task.task_uuid || task.id} className="history-item-square clickable" onClick={() => { setHistoryLightboxTask(task); setHistoryDetailsTask(null); }}>
                    <img src={fixUrl(task.image_url)} loading="lazy" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL: HISTORY LIGHTBOX (Selected Image Details View) */}
      {historyLightboxTask && (
        <div className="lightbox-overlay" style={{ position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(0,0,0,0.95)', display: 'flex', flexDirection: 'column', padding: '20px' }}>
          <button onClick={() => setHistoryLightboxTask(null)} style={{ alignSelf: 'flex-end', background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', padding: '10px', borderRadius: '50%', marginBottom: '10px' }} className="clickable"><X size={24} /></button>
          
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
             <img src={fixUrl(historyLightboxTask.image_url)} style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: '16px', objectShadow: '0 20px 40px rgba(0,0,0,0.5)' }} />
          </div>

          <div style={{ padding: '20px 0', display: 'flex', flexDirection: 'column', gap: '10px' }}>
             <button onClick={() => downloadImage(historyLightboxTask.image_url)} className="btn btn-primary" style={{ width: '100%' }}>
               <Download size={20} /> Скачать в хорошем качестве
             </button>
             <button onClick={() => setHistoryDetailsTask(historyLightboxTask)} className="btn btn-secondary" style={{ width: '100%' }}>
               <HelpCircle size={20} /> Детали генерации
             </button>
          </div>
        </div>
      )}

      {/* MODAL: GENERATION DETAILS */}
      {historyDetailsTask && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 2500, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '450px', padding: '24px', borderRadius: '28px', background: 'var(--bg-color)', position: 'relative', overflowY: 'auto', maxHeight: '80vh' }}>
            <X onClick={() => setHistoryDetailsTask(null)} size={24} style={{ position: 'absolute', top: 20, right: 20, opacity: 0.5 }} className="clickable" />
            
            <h3 style={{ marginTop: 0, marginBottom: '20px', fontSize: '18px' }}>Детали шедевра</h3>
            
            <div style={{ marginBottom: '20px' }}>
               <div style={{ opacity: 0.4, fontSize: '12px', marginBottom: '5px', textTransform: 'uppercase', letterSpacing: '1px' }}>Промпт</div>
               <div style={{ background: 'rgba(255,255,255,0.05)', padding: '14px', borderRadius: '14px', fontSize: '14px', lineHeight: 1.5, border: '1px solid rgba(255,255,255,0.05)' }}>
                 {historyDetailsTask.prompt || 'Без описания'}
               </div>
            </div>

            <div style={{ marginBottom: '20px' }}>
               <div style={{ opacity: 0.4, fontSize: '12px', marginBottom: '5px', textTransform: 'uppercase', letterSpacing: '1px' }}>Исходные референсы</div>
               <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                  {getPromptImages(historyDetailsTask).map((url, i) => (
                    <img key={i} src={fixUrl(url)} onClick={() => setActiveImage(fixUrl(url))} className="clickable" style={{ width: '100%', aspectRatio: '1/1', borderRadius: '8px', objectFit: 'cover', background: 'rgba(255,255,255,0.05)' }} />
                  ))}
                  {getPromptImages(historyDetailsTask).length === 0 && <div style={{ fontSize: '12px', opacity: 0.3 }}>Нет референсов</div>}
               </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '20px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: '12px', opacity: 0.5 }}>
               <div>{getModelName(historyDetailsTask.model)}</div>
               <div>{historyDetailsTask.created_at ? new Date(historyDetailsTask.created_at).toLocaleString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Неизвестно'}</div>
            </div>
          </div>
        </div>
      )}

      {/* ... (Existing SELECTION & BALANCE Modals) ... */}
      {isModelMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 1500, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '420px', padding: '30px', borderRadius: '32px', background: 'var(--bg-color)' }}>
            <h3 style={{ marginBottom: '24px', textAlign: 'center' }}>🤖 Выберите нейросеть</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {modelConfig?.available_models ? (
                Object.entries(modelConfig.available_models).map(([name, id]: [string, any]) => (
                  <button key={id} onClick={() => updateModel(id)} className="clickable" style={{ padding: '20px', textAlign: 'left', borderRadius: '20px', background: currentModel === id ? 'var(--text-color)' : 'var(--glass-bg)', color: currentModel === id ? 'var(--bg-color)' : 'inherit', border: 'none' }}>
                    <div style={{ fontSize: '14px', fontWeight: 800 }}>{name}</div>
                    <div style={{ fontSize: '11px', opacity: 0.6 }}>{modelConfig.credits_per_model?.[id] || '?'} ⚡</div>
                  </button>
                ))
              ) : (
                <>
                  <button onClick={() => updateModel('nano-banana-2-1k')} className="clickable" style={{ padding: '20px', textAlign: 'left', borderRadius: '20px', background: currentModel === 'nano-banana-2-1k' ? 'var(--text-color)' : 'var(--glass-bg)', color: currentModel === 'nano-banana-2-1k' ? 'var(--bg-color)' : 'inherit', border: 'none' }}>
                    <div style={{ fontSize: '15px', fontWeight: 800 }}>Nano Banana 2 (1K)</div>
                    <div style={{ fontSize: '12px', opacity: 0.6 }}>1 ⚡</div>
                  </button>
                  <button onClick={() => updateModel('nano-banana-2-4k')} className="clickable" style={{ padding: '20px', textAlign: 'left', borderRadius: '20px', background: currentModel === 'nano-banana-2-4k' ? 'var(--text-color)' : 'var(--glass-bg)', color: currentModel === 'nano-banana-2-4k' ? 'var(--bg-color)' : 'inherit', border: 'none' }}>
                    <div style={{ fontSize: '15px', fontWeight: 800 }}>Nano Banana 2 (4K)</div>
                    <div style={{ fontSize: '12px', opacity: 0.6 }}>2 ⚡</div>
                  </button>
                </>
              )}
            </div>
            <button onClick={() => setIsModelMenuOpen(false)} style={{ width: '100%', marginTop: '20px', padding: '10px', border: 'none', background: 'none', color: 'inherit', opacity: 0.5 }} className="clickable">Отмена</button>
          </div>
        </div>
      )}

      {isSettingsMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 1500, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '420px', padding: '30px', borderRadius: '32px', background: 'var(--bg-color)' }}>
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
               <Zap size={40} fill="#facc15" style={{ marginBottom: '10px', color: '#facc15' }} />
               <h3 style={{ margin: 0 }}>Пополнить баланс</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {[ {id:'149', cr: 30, p:'149₽'}, {id:'299', cr: 65, p:'299₽'}, {id:'990', cr: 270, p:'990₽'} ].map(p => (
                <button key={p.id} onClick={() => { haptic(); api.createPayment(p.id).then(r=>r.success&&(window.location.href=r.data.payment_url)); }} className="clickable" style={{ display: 'flex', justifyContent: 'space-between', padding: '20px', borderRadius: '22px', background: 'var(--glass-bg)', border: 'none', color: 'inherit' }}>
                  <span style={{ fontWeight: 800 }}>{p.cr} ⚡</span> 
                  <span style={{ color: '#00e676', fontWeight: 900, fontSize: '16px' }}>{p.p}</span>
                </button>
              ))}
              <button onClick={() => setIsSettingsMenuOpen(false)} style={{ marginTop: '10px', padding: '10px', border: 'none', background: 'none', color: 'inherit', opacity: 0.5 }} className="clickable">Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {showPwaPrompt && (
        <div className="glass pwa-banner" style={{ position: 'fixed', bottom: 110, left: 15, right: 15, padding: '20px', borderRadius: '28px', zIndex: 5000, display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Smartphone size={32} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 900, fontSize: '15px' }}>S•NOVA AI на экран</div>
            <div style={{ fontSize: '11px', opacity: 0.8 }}>Установите приложение для работы в 1 клик</div>
          </div>
          <button onClick={handleInstallPwa} className="btn-primary" style={{ padding: '10px 18px', borderRadius: '12px', fontSize: '13px' }}>Установить</button>
          <X onClick={() => { setShowPwaPrompt(false); localStorage.setItem('pwa_closed', 'true'); }} size={18} style={{ opacity: 0.5 }} className="clickable" />
        </div>
      )}

      <style>{`
        .btn-bot { background: none; border: none; color: inherit; opacity: 0.6; font-size: 11px; display: flex; flex-direction: column; align-items: center; gap: 5px; padding: 10px 0; font-weight: 700; cursor: pointer; transition: all 0.2s; }
        .btn-bot:active { opacity: 1; transform: scale(0.9); }
        .chat-app b { font-weight: 800; color: #fff; }
        [data-theme='light'] .chat-app b { color: #000; }
        .status-dot { width: 6px; height: 6px; background-color: #00e676; border-radius: 50%; animation: blink 1.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        
        .history-grid { 
           display: grid; 
           grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); 
           gap: 8px; 
           width: 100%;
           padding-bottom: 20px;
        }
        .history-item-square { 
           aspect-ratio: 1/1; 
           border-radius: 12px; 
           overflow: hidden; 
           background: var(--glass-bg);
           border: 1px solid var(--glass-border);
           transition: transform 0.2s;
        }
        .history-item-square:active { transform: scale(0.96); }
        .history-item-square img { width: 100%; height: 100%; object-fit: cover; }

        @media (min-width: 768px) {
           .history-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; }
           .history-item-square { border-radius: 20px; }
           .history-item-square:hover { transform: scale(1.03); z-index: 10; border-color: rgba(255,255,255,0.3); }
        }

        @media (max-height: 500px) {
          .chat-app header { padding: 8px 15px; }
          .btn-bot { padding: 5px 0; }
          .status-dot { display: none; }
        }
      `}</style>
    </div>
  );
}

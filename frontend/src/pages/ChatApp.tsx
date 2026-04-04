import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, Download, Moon, Sun,
  X, Loader2, User, HelpCircle, Sparkles, Smartphone, History, Eye
} from 'lucide-react';
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
  const [messages, setMessages] = useState<Message[]>([]);
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
  const [activeImage, setActiveImage] = useState<string | null>(null); 
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [showPwaPrompt, setShowPwaPrompt] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    initApp();
    document.documentElement.setAttribute('data-theme', theme);
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setTimeout(() => setShowPwaPrompt(true), 4000);
    });
  }, [theme]);

  const initApp = async () => {
    fetchUserData();
    setMessages([{ 
      id: 'welcome', 
      type: 'bot', 
      text: `✨ **Готовы к нейро-магии?**\n\nЯ сгенерирую для тебя всё, что угодно — просто опиши идею или отправь фото! 🚀\n\n👇 Начинай писать ниже!`, 
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

  const getCreditsLabel = (num: number) => {
    const n = Math.abs(num);
    const cases = [2, 0, 1, 1, 1, 2];
    const titles = ['кредит', 'кредита', 'кредитов'];
    return titles[(n % 100 > 4 && n % 100 < 20) ? 2 : cases[(n % 10 < 5) ? n % 10 : 5]];
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
      alert("Для установки нажмите 'Поделиться' -> 'На экран Домой' (для Safari)");
    }
  };

  const handleInitiate = () => {
    if (!input.trim() && selectedFiles.length === 0) return;
    haptic();
    const confirmMsgId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: confirmMsgId, type: 'bot-confirm', 
      text: `✨ **Готовы начинать?**\n\n📝 Текст: \`${input.trim() || 'Без текста'}\`\n🤖 Модель: **${currentModel.includes('pro') ? 'Nano PRO' : 'NanoBanana 2'}**\n💰 Цена: **${currentModel.includes('pro') ? 4 : 3} кр.**`,
      image: previews[0], timestamp: new Date(),
      meta: { prompt: input, files: [...selectedFiles], previews: [...previews], model: currentModel }
    }]);
    setInput(''); setSelectedFiles([]); setPreviews([]);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
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
    } catch (e: any) { updateBotMessage(botMsgId, "❌ Ошибка связи с сервером"); }
  };

  const pollStatus = async (uuid: string, msgId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.checkStatus(uuid);
        if (res.success && (res.data.state === 'success' || res.data.state === 'completed')) {
          clearInterval(interval);
          updateBotMessage(msgId, `🔥 **Результат готов!**`, res.data.image_url);
          fetchUserData();
        } else if (res.data.state === 'failed') {
          clearInterval(interval);
          updateBotMessage(msgId, `❌ К сожалению, произошла ошибка. Кредиты возвращены.`);
          fetchUserData();
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const updateBotMessage = (id: string, text: string, imageUrl?: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, text, image: imageUrl, isGenerating: false } : m));
  };

  const updateModel = async (m: string) => {
    haptic();
    setCurrentModel(m); setIsModelMenuOpen(false);
    try { await api.updateModel(m); fetchUserData(); } catch (e) {}
  };

  const downloadImage = async (url: string) => {
    haptic();
    window.open(url, '_blank');
  };

  // Helper to fix broken localhost URLs in history
  const fixUrl = (url?: string) => {
    if (!url) return '';
    if (url.includes('localhost:8000') || url.includes('api:8000')) {
      const parts = url.split('/static/');
      return `${window.location.protocol}//${window.location.hostname}:8000/static/${parts[1]}`;
    }
    return url;
  };

  return (
    <div className="chat-app" style={{ height: '100dvh', width: '100vw', display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
      
      {/* HEADER */}
      <header className="glass" style={{ height: '70px', minHeight: '70px', padding: '0 20px', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, borderRadius: '0 0 20px 20px' }}>
        <button onClick={toggleTheme} style={{ position: 'absolute', left: '20px', background: 'none', border: 'none', color: 'inherit' }}>
          {theme === 'dark' ? <Sun size={22} /> : <Moon size={22} />}
        </button>
        <div style={{ fontWeight: 800, fontSize: '22px', letterSpacing: '-0.5px' }}>S•NOVA AI</div>
        <div className="glass" style={{ position: 'absolute', right: '15px', padding: '6px 12px', borderRadius: '14px', fontSize: '13px', fontWeight: 700, border: 'none', background: 'rgba(255,255,255,0.1)' }}>
          {user ? `${user.balance} ${getCreditsLabel(user.balance)}` : '...'}
        </div>
      </header>

      {/* CHAT AREA */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '15px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
            <div className="glass" style={{ padding: '12px 16px', borderRadius: '22px', position: 'relative', border: msg.type === 'user' ? 'none' : '' }}>
              {msg.image && (
                <div style={{ position: 'relative', marginBottom: '10px' }}>
                  <img src={fixUrl(msg.image)} onClick={() => setActiveImage(fixUrl(msg.image))} className="clickable" style={{ width: '100%', maxHeight: '40dvh', borderRadius: '16px', objectFit: 'cover' }} />
                  {!msg.isGenerating && msg.type === 'bot' && (
                    <button onClick={() => downloadImage(msg.image!)} style={{ position: 'absolute', bottom: 10, right: 10, background: 'rgba(0,0,0,0.5)', padding: '10px', borderRadius: '50%', border: 'none', color: '#fff' }}>
                      <Download size={18} />
                    </button>
                  )}
                </div>
              )}
              {msg.text && <div style={{ fontSize: '15px', lineHeight: 1.5 }}>{msg.text.split('**').map((p,i)=> i%2?<b key={i}>{p}</b>:p)}</div>}
              <div style={{ textAlign: 'right', fontSize: '10px', opacity: 0.4, marginTop: '5px' }}>{new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(msg.timestamp)}</div>

              {msg.type === 'bot-confirm' && (
                <div style={{ marginTop: '15px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <button onClick={() => handleConfirmGen(msg.id)} style={{ padding: '15px', borderRadius: '16px', background: 'var(--text-color)', color: 'var(--bg-color)', fontWeight: 800, border: 'none' }} className="clickable">🚀 Сгенерировать</button>
                  <button onClick={() => setMessages(p => p.filter(m => m.id !== msg.id))} style={{ padding: '5px', opacity: 0.5, border: 'none', background: 'none', color: 'inherit' }} className="clickable">Отмена</button>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </main>

      {/* FOOTER */}
      <footer style={{ padding: '10px', display: 'flex', flexDirection: 'column', gap: '10px', zIndex: 100 }}>
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '10px', padding: '0 10px' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative' }}>
                <img src={src} style={{ width: '55px', height: '55px', borderRadius: '14px', objectFit: 'cover' }} />
                <button onClick={() => { haptic(); setSelectedFiles(p=>p.filter((_,idx)=>idx!==i)); setPreviews(p=>p.filter((_,idx)=>idx!==i)); }} style={{ position: 'absolute', top: -5, right: -5, background: '#f44', borderRadius: '50%', color: '#fff', border: 'none', width: '20px', height: '20px' }}>×</button>
              </div>
            ))}
          </div>
        )}
        
        <div className="glass" style={{ margin: '0 10px', borderRadius: '30px', display: 'flex', alignItems: 'center', padding: '6px 18px', gap: '12px', background: 'rgba(255,255,255,0.08)' }}>
          <button onClick={() => { haptic(); fileInputRef.current?.click(); }} style={{ background: 'none', border: 'none', color: 'inherit' }} className="clickable"><ImageIcon size={22} /></button>
          <input value={input} onChange={e=>setInput(e.target.value)} onKeyPress={e=>e.key==='Enter'&&handleInitiate()} placeholder="Напиши идею..." style={{ flex: 1, background: 'none', border: 'none', color: 'inherit', padding: '12px 0', outline: 'none', fontSize: '16px' }} />
          <button onClick={handleInitiate} style={{ background: 'var(--text-color)', borderRadius: '50%', width: '38px', height: '38px', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }} className="clickable"><Send size={20} color="var(--bg-color)" /></button>
        </div>
        <input type="file" multiple ref={fileInputRef} style={{ display: 'none' }} onChange={e => {
          if (e.target.files) {
            const files = Array.from(e.target.files);
            setSelectedFiles(p => [...p, ...files]);
            files.forEach(f => {
              const r = new FileReader(); r.onloadend = () => setPreviews(p => [...p, r.result as string]); r.readAsDataURL(f);
            });
          }
        }} />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', padding: '5px 5px 15px' }}>
          <button onClick={() => { haptic(); initApp(); }} className="btn-bot"><Sparkles size={18} /><br/>Создать</button>
          <button onClick={() => { haptic(); setIsModelMenuOpen(true); }} className="btn-bot"><Settings size={18} /><br/>Модель</button>
          <button onClick={openHistory} className="btn-bot"><History size={18} /><br/>История</button>
          <button onClick={() => { haptic(); setIsSettingsMenuOpen(true); }} className="btn-bot"><User size={18} /><br/>Баланс</button>
        </div>
      </footer>

      {/* FULL-SCREEN IMAGE VIEW */}
      {activeImage && (
        <div onClick={() => setActiveImage(null)} style={{ position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(0,0,0,0.98)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '10px' }}>
          <img src={activeImage} style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: '12px' }} />
          <X style={{ position: 'absolute', top: 30, right: 30, color: '#fff' }} size={35} className="clickable" />
        </div>
      )}

      {/* MODAL: HISTORY */}
      {isHistoryOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'var(--bg-color)', display: 'flex', flexDirection: 'column' }}>
          <header style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)' }}>
            <h2 style={{ margin: 0 }}>📚 Моя история</h2>
            <X onClick={() => setIsHistoryOpen(false)} size={28} className="clickable" />
          </header>
          <div style={{ flex: 1, overflowY: 'auto', padding: '15px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {isHistoryLoading ? (
              [1,2,3].map(i => <div key={i} className="skeleton" style={{ height: '300px', width: '100%' }} />)
            ) : historyTasks.length === 0 ? (
              <div style={{ textAlign: 'center', opacity: 0.5, marginTop: '100px' }}>У вас пока нет генераций :(</div>
            ) : historyTasks.map(task => (
              <div key={task.id} className="glass" style={{ padding: '15px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ fontSize: '13px', opacity: 0.7 }}>📝 Промпт: <i>{task.prompt || 'Без текста'}</i></div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {task.image_url && (
                    <div style={{ flex: 1, position: 'relative' }}>
                      <img src={fixUrl(task.image_url)} style={{ width: '100%', borderRadius: '12px' }} />
                      <button onClick={() => downloadImage(task.image_url)} style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(0,0,0,0.5)', padding: '8px', borderRadius: '50%', color: '#fff', border: 'none' }}><Download size={14} /></button>
                    </div>
                  )}
                </div>
                <div style={{ fontSize: '10px', opacity: 0.4 }}>{new Date(task.created_at).toLocaleDateString('ru-RU')}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MODAL: MODEL SELECTION */}
      {isModelMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 1500, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', padding: '30px', borderRadius: '30px', background: 'var(--bg-color)' }}>
            <h3 style={{ marginBottom: '20px' }}>🤖 Выберите нейросеть</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button onClick={() => updateModel('nano-banana-2')} className="clickable" style={{ padding: '18px', textAlign: 'left', borderRadius: '20px', background: currentModel === 'nano-banana-2' ? 'var(--text-color)' : 'var(--glass-bg)', color: currentModel === 'nano-banana-2' ? 'var(--bg-color)' : 'inherit', border: 'none' }}>
                <b>Nano Banana 2</b><br/><small>3 кр. | Сверхбыстрые генерации</small>
              </button>
              <button onClick={() => updateModel('nano-banana-pro')} className="clickable" style={{ padding: '18px', textAlign: 'left', borderRadius: '20px', background: currentModel === 'nano-banana-pro' ? 'var(--text-color)' : 'var(--glass-bg)', color: currentModel === 'nano-banana-pro' ? 'var(--bg-color)' : 'inherit', border: 'none' }}>
                <b>Nano PRO</b><br/><small>4 кр. | Идеально для фото 4K</small>
              </button>
              <button onClick={() => setIsModelMenuOpen(false)} style={{ marginTop: '10px', padding: '10px', border: 'none', background: 'none', color: 'inherit', opacity: 0.5 }}>Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: BALANCE */}
      {isSettingsMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 1500, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', padding: '30px', borderRadius: '30px', background: 'var(--bg-color)' }}>
            <h3 style={{ marginBottom: '20px' }}>💳 Пополнить баланс</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {[ {id:'149', cr: 30, p:'149₽'}, {id:'299', cr: 65, p:'299₽'}, {id:'990', cr: 270, p:'990₽'} ].map(p => (
                <button key={p.id} onClick={() => { haptic(); api.createPayment(p.id).then(r=>r.success&&(window.location.href=r.data.payment_url)); }} className="clickable" style={{ display: 'flex', justifyContent: 'space-between', padding: '20px', borderRadius: '20px', background: 'var(--glass-bg)', border: 'none', color: 'inherit' }}>
                  <b>{p.cr} кредитов</b> <span style={{ color: '#00e676', fontWeight: 800 }}>{p.p}</span>
                </button>
              ))}
              <button onClick={() => setIsSettingsMenuOpen(false)} style={{ marginTop: '10px', padding: '10px', border: 'none', background: 'none', color: 'inherit', opacity: 0.5 }}>Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {/* PWA INSTALL PROMPT */}
      {showPwaPrompt && (
        <div className="glass pwa-banner" style={{ position: 'fixed', bottom: 100, left: 15, right: 15, padding: '20px', borderRadius: '26px', zIndex: 5000, display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Smartphone size={32} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: '15px' }}>S•NOVA AI на экран</div>
            <div style={{ fontSize: '12px', opacity: 0.8 }}>Установите приложение для работы в 1 клик</div>
          </div>
          <button onClick={handleInstallPwa} style={{ background: '#000', color: '#fff', padding: '10px 18px', borderRadius: '12px', border: 'none', fontSize: '13px', fontWeight: 800 }}>Установить</button>
          <X onClick={() => setShowPwaPrompt(false)} size={18} style={{ opacity: 0.5 }} />
        </div>
      )}

      <style>{`
        .btn-bot { background: none; border: none; color: inherit; opacity: 0.6; font-size: 11px; display: flex; flex-direction: column; align-items: center; gap: 5px; padding: 10px 0; font-weight: 600; cursor: pointer; }
        .btn-bot:active { opacity: 1; transform: scale(0.9); }
      `}</style>
    </div>
  );
}

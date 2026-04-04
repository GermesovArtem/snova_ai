import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, Download, Moon, Sun,
  X, Loader2, User, HelpCircle, Sparkles, Smartphone, LogOut
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
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  
  // UI States
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [currentModel, setCurrentModel] = useState('nano-banana-2');
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
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
      setTimeout(() => setShowPwaPrompt(true), 5000);
    });
  }, [theme]);

  const initApp = async () => {
    setIsHistoryLoading(true);
    await fetchUserData();
    await fetchHistory();
    setIsHistoryLoading(false);
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

  const fetchHistory = async () => {
    try {
      const res = await api.getHistory();
      if (res.success && res.data.length > 0) {
        const historyMsgs: Message[] = [];
        res.data.reverse().forEach((task: any) => {
          if (task.prompt || task.prompt_image_url) {
            historyMsgs.push({ id: `u-${task.id}`, type: 'user', text: task.prompt, image: task.prompt_image_url, timestamp: new Date(task.created_at) });
          }
          if (task.image_url || task.status === 'failed') {
            historyMsgs.push({ 
              id: `b-${task.id}`, 
              type: 'bot', 
              text: task.status === 'completed' ? `🔥 **Готово!**` : `❌ Ошибка генерации`, 
              image: task.image_url, 
              timestamp: new Date(task.created_at) 
            });
          }
        });
        setMessages(historyMsgs);
      } else {
        setMessages([{ id: 'welcome', type: 'bot', text: `✨ **Добро пожаловать в S•NOVA AI!**\n\nЯ помогу тебе создать любой арт или изменить фото 🚀\n\n👇 Отправь описание или фото прямо сейчас!`, timestamp: new Date() }]);
      }
    } catch (e) { console.error(e); }
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
      alert("Для установки нажмите 'Поделиться' -> 'На экран Домой' (для iOS)");
    }
  };

  const handleInitiate = () => {
    if (!input.trim() && selectedFiles.length === 0) return;
    haptic();
    const confirmMsgId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: confirmMsgId, type: 'bot-confirm', text: `✨ **Ваш промпт почти готов!**\n\n🤖 Модель: **${currentModel.includes('pro') ? 'Nano PRO' : 'NanoBanana 2'}**\n💰 Цена: **${currentModel.includes('pro') ? 4 : 3} кр.**`,
      image: previews[0], timestamp: new Date(),
      meta: { prompt: input, files: [...selectedFiles], previews: [...previews], model: currentModel }
    }]);
    setInput(''); setSelectedFiles([]); setPreviews([]);
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleConfirmGen = async (msgId: string) => {
    haptic();
    const msg = messages.find(m => m.id === msgId);
    if (!msg) return;
    setMessages(prev => prev.filter(m => m.id !== msgId));
    const botMsgId = Date.now().toString();
    setMessages(prev => [...prev, { id: botMsgId, type: 'bot', text: `🚀 Генерирую...`, isGenerating: true, timestamp: new Date() }]);
    try {
      const res = await api.generateEdit(msg.meta.prompt, msg.meta.files);
      if (res.success) pollStatus(res.data.task_uuid, botMsgId);
      else updateBotMessage(botMsgId, "❌ Ошибка: " + res.error);
    } catch (e: any) { updateBotMessage(botMsgId, "❌ Ошибка связи"); }
  };

  const pollStatus = async (uuid: string, msgId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.checkStatus(uuid);
        if (res.success && (res.data.state === 'success' || res.data.state === 'completed')) {
          clearInterval(interval);
          updateBotMessage(msgId, `🔥 **Готово!**`, res.data.image_url);
          fetchUserData();
        } else if (res.data.state === 'failed') {
          clearInterval(interval);
          updateBotMessage(msgId, `❌ Ошибка в KIE: ` + res.data.error);
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const updateBotMessage = (id: string, text: string, imageUrl?: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, text, image: imageUrl, isGenerating: false } : m));
  };

  const updateModel = async (m: string) => {
    haptic();
    setCurrentModel(m);
    setIsModelMenuOpen(false);
    try { await api.updateModel(m); fetchUserData(); } catch (e) {}
  };

  return (
    <div className="chat-app" style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      
      {/* HEADER */}
      <header className="glass" style={{ height: '64px', padding: '0 20px', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
        <button onClick={toggleTheme} className="clickable" style={{ position: 'absolute', left: '20px', background: 'none', border: 'none', color: 'inherit' }}>
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>
        <div className="logo-text" style={{ fontSize: '22px' }}>S•NOVA AI</div>
        <div className="glass" style={{ position: 'absolute', right: '20px', padding: '4px 12px', borderRadius: '14px', fontSize: '13px', fontWeight: 600 }}>
          {user ? `Баланс: ${user.balance} ${getCreditsLabel(user.balance)}` : 'Загрузка...'}
        </div>
      </header>

      {/* CHAT AREA */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {isHistoryLoading ? (
          [1,2,3].map(i => <div key={i} className="skeleton" style={{ width: i%2?'60%':'40%', height: '80px', marginBottom: '10px', alignSelf: i%2?'flex-start':'flex-end' }} />)
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="msg-appear" style={{ alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
              <div className="glass" style={{ padding: '12px 16px', borderRadius: '20px', position: 'relative' }}>
                {msg.image && (
                  <div style={{ position: 'relative', marginBottom: '10px' }}>
                    <img src={msg.image} onClick={() => { haptic(); setActiveImage(msg.image!); }} className="clickable" style={{ width: '100%', maxHeight: '320px', borderRadius: '14px', objectFit: 'cover' }} />
                    {!msg.isGenerating && msg.type === 'bot' && msg.image && (
                      <button onClick={() => { haptic(); window.open(msg.image, '_blank'); }} className="clickable" style={{ position: 'absolute', bottom: 10, right: 10, background: 'rgba(0,0,0,0.5)', padding: '8px', borderRadius: '50%', border: 'none', color: '#fff' }}>
                        <Download size={16} />
                      </button>
                    )}
                  </div>
                )}
                {msg.text && <div style={{ fontSize: '15px', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{msg.text.split('**').map((p,i)=> i%2?<b key={i}>{p}</b>:p)}</div>}
                <div style={{ textAlign: 'right', fontSize: '10px', opacity: 0.4, marginTop: '6px' }}>{new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(msg.timestamp)}</div>

                {msg.type === 'bot-confirm' && (
                  <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <button onClick={() => handleConfirmGen(msg.id)} style={{ padding: '14px', borderRadius: '14px', background: 'var(--text-color)', color: 'var(--bg-color)', fontWeight: 800, border: 'none' }} className="clickable">🚀 Сгенерировать</button>
                    <button onClick={() => setMessages(p => p.filter(m => m.id !== msg.id))} style={{ padding: '8px', opacity: 0.5, border: 'none', background: 'none', color: 'inherit' }} className="clickable">Отмена</button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={chatEndRef} />
      </main>

      {/* FOOTER */}
      <footer style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '10px', padding: '0 10px' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative' }}>
                <img src={src} style={{ width: '50px', height: '50px', borderRadius: '10px', objectFit: 'cover' }} />
                <button onClick={() => { haptic(); setSelectedFiles(p=>p.filter((_,idx)=>idx!==i)); setPreviews(p=>p.filter((_,idx)=>idx!==i)); }} style={{ position: 'absolute', top: -6, right: -6, background: '#f44', borderRadius: '50%', color: '#fff', border: 'none', width: '18px', height: '18px', fontSize: '10px' }}>×</button>
              </div>
            ))}
          </div>
        )}
        
        <div className="glass" style={{ margin: '0 10px', borderRadius: '28px', display: 'flex', alignItems: 'center', padding: '6px 18px', gap: '12px' }}>
          <button onClick={() => { haptic(); fileInputRef.current?.click(); }} style={{ background: 'none', border: 'none', color: 'inherit' }} className="clickable"><ImageIcon size={22} /></button>
          <input value={input} onChange={e=>setInput(e.target.value)} onKeyPress={e=>e.key==='Enter'&&handleInitiate()} placeholder="Опиши идею..." style={{ flex: 1, background: 'none', border: 'none', color: 'inherit', padding: '10px 0', outline: 'none', fontSize: '15px' }} />
          <button onClick={handleInitiate} style={{ background: 'var(--text-color)', borderRadius: '50%', width: '36px', height: '36px', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }} className="clickable"><Send size={18} color="var(--bg-color)" /></button>
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

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px', padding: '4px 8px 12px' }}>
          <button onClick={() => { haptic(); initApp(); }} className="btn-menu clickable"><Sparkles size={18} /><br/>Создать</button>
          <button onClick={() => { haptic(); setIsModelMenuOpen(true); }} className="btn-menu clickable"><Settings size={18} /><br/>Модель</button>
          <button onClick={() => { haptic(); setIsSettingsMenuOpen(true); }} className="btn-menu clickable"><User size={18} /><br/>Баланс</button>
          <button onClick={() => { haptic(); alert("Техподдержка: @artemgavr1lov"); }} className="btn-menu clickable"><HelpCircle size={18} /><br/>Помощь</button>
        </div>
      </footer>

      {/* MODALS */}
      {activeImage && (
        <div onClick={() => { haptic(); setActiveImage(null); }} style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.96)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <img src={activeImage} style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: '16px' }} />
          <X style={{ position: 'absolute', top: 30, right: 30, color: '#fff' }} size={32} className="clickable" />
        </div>
      )}

      {isModelMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 500, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', padding: '28px', borderRadius: '28px', background: 'var(--bg-color)' }}>
            <h3 style={{ marginBottom: '20px' }}>🤖 Выбор модели</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button onClick={() => updateModel('nano-banana-2')} className="clickable" style={{ padding: '16px', textAlign: 'left', borderRadius: '18px', background: currentModel === 'nano-banana-2' ? 'var(--text-color)' : 'var(--glass-bg)', color: currentModel === 'nano-banana-2' ? 'var(--bg-color)' : 'inherit', border: 'none' }}><b>Nano Banana 2</b><br/><small>3 кр. | Скетчи и дизайн</small></button>
              <button onClick={() => updateModel('nano-banana-pro')} className="clickable" style={{ padding: '16px', textAlign: 'left', borderRadius: '18px', background: currentModel === 'nano-banana-pro' ? 'var(--text-color)' : 'var(--glass-bg)', color: currentModel === 'nano-banana-pro' ? 'var(--bg-color)' : 'inherit', border: 'none' }}><b>Nano PRO</b><br/><small>4 кр. | Высокая детализация</small></button>
              <button onClick={() => { haptic(); setIsModelMenuOpen(false); }} style={{ marginTop: '10px', opacity: 0.5, border: 'none', background: 'none', color: 'inherit' }} className="clickable">Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {isSettingsMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 500, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', padding: '28px', borderRadius: '28px', background: 'var(--bg-color)' }}>
            <h3 style={{ marginBottom: '20px' }}>💳 Пополнение</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {[ {id:'149', cr: 30, p:'149₽'}, {id:'299', cr: 65, p:'299₽'}, {id:'990', cr: 270, p:'990₽'} ].map(p => (
                <button key={p.id} onClick={() => { haptic(); api.createPayment(p.id).then(r=>r.success&&(window.location.href=r.data.payment_url)); }} className="clickable" style={{ display: 'flex', justifyContent: 'space-between', padding: '18px', borderRadius: '18px', background: 'var(--glass-bg)', border: 'none', color: 'inherit' }}><b>{p.cr} кр.</b> <span style={{ color: '#00c853', fontWeight: 800 }}>{p.p}</span></button>
              ))}
              <button onClick={() => { haptic(); setIsSettingsMenuOpen(false); }} style={{ marginTop: '10px', opacity: 0.5, border: 'none', background: 'none', color: 'inherit' }} className="clickable">Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {showPwaPrompt && (
        <div className="glass pwa-shine" style={{ position: 'fixed', bottom: 100, left: 20, right: 20, padding: '18px', borderRadius: '24px', zIndex: 1000, display: 'flex', alignItems: 'center', gap: '14px', background: 'var(--text-color)', color: 'var(--bg-color)' }}>
          <Smartphone size={32} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: '15px' }}>S•NOVA AI на экран</div>
            <div style={{ fontSize: '12px', opacity: 0.8 }}>Установите как приложение</div>
          </div>
          <button onClick={handleInstallPwa} style={{ background: 'var(--bg-color)', color: 'var(--text-color)', padding: '10px 20px', borderRadius: '12px', border: 'none', fontSize: '13px', fontWeight: 800 }} className="clickable">Установить</button>
          <X onClick={() => { haptic(); setShowPwaPrompt(false); }} size={18} className="clickable" style={{ opacity: 0.5 }} />
        </div>
      )}

      <style>{`
        .btn-menu { background: none; border: none; color: inherit; opacity: 0.5; font-size: 11px; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 10px 0; font-weight: 500; transition: opacity 0.2s; }
        .btn-menu:hover { opacity: 1; }
      `}</style>
    </div>
  );
}

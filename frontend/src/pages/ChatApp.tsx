import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, Download, Maximize2,
  X, Loader2, User, HelpCircle, Sparkles, PlusCircle, Smartphone
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

interface UserData {
  id: number;
  name: string;
  balance: number;
  model_preference: string;
}

export default function ChatApp() {
  const [user, setUser] = useState<UserData | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // UI States
  const [currentModel, setCurrentModel] = useState('nano-banana-2');
  const [genSettings, setGenSettings] = useState({ aspect_ratio: '1:1', resolution: '4K', output_format: 'png' });
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const [activeImage, setActiveImage] = useState<string | null>(null); // Lightbox
  const [showPwaPrompt, setShowPwaPrompt] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    initApp();
    // PWA Prompt Logic
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    if (!isStandalone) {
      setTimeout(() => setShowPwaPrompt(true), 5000);
    }
  }, []);

  const initApp = async () => {
    await fetchUserData();
    await fetchHistory();
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
          // Reconstruct user and bot messages from task
          if (task.prompt || task.prompt_image_url) {
            historyMsgs.push({
              id: `user-${task.id}`,
              type: 'user',
              text: task.prompt,
              image: task.prompt_image_url,
              timestamp: new Date(task.created_at)
            });
          }
          if (task.image_url) {
            historyMsgs.push({
              id: `bot-${task.id}`,
              type: 'bot',
              text: task.status === 'completed' ? `🔥 **Готово!**` : `❌ Ошибка`,
              image: task.image_url,
              timestamp: new Date(task.created_at)
            });
          }
        });
        setMessages(historyMsgs);
      } else {
        setMessages([{
          id: 'welcome',
          type: 'bot',
          text: `✨ **Добро пожаловать в S•NOVA AI!**\n\nЗдесь ты можешь сгенерировать невероятный контент 🚀\n\n🖼 **Фото → Фото:** Отправь фотографию и напиши, что поменять.\n\n📝 **Текст → Фото:** Опиши любую идею — и я создам её с нуля!\n\n👇 **Просто отправь мне текст или фото прямо сейчас!**`,
          timestamp: new Date()
        }]);
      }
    } catch (e) { console.error(e); }
  };

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(date);
  };

  const handleInitiate = () => {
    if (!input.trim() && selectedFiles.length === 0) return;
    const confirmMsgId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: confirmMsgId,
      type: 'bot-confirm',
      text: `✨ **Ваш промпт почти готов!**\n\n📝 Текст: \`${input.trim() || 'Без текста'}\`\n🤖 Модель: **${currentModel.includes('pro') ? 'Nano PRO' : 'NanoBanana 2'}**\n💰 Стоимость: **${currentModel.includes('pro') ? 4 : 3} кр.**\n\nНачинаем генерацию?`,
      image: previews[0],
      timestamp: new Date(),
      meta: { prompt: input, files: [...selectedFiles], previews: [...previews], model: currentModel }
    }]);
    setInput(''); setSelectedFiles([]); setPreviews([]);
  };

  const handleConfirmGen = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg) return;
    setMessages(prev => prev.filter(m => m.id !== msgId));
    const botMsgId = Date.now().toString();
    setMessages(prev => [...prev, { id: botMsgId, type: 'bot', text: `🚀 Генерирую...`, isGenerating: true, timestamp: new Date() }]);
    try {
      const res = await api.generateEdit(msg.meta.prompt, msg.meta.files);
      if (res.success) pollStatus(res.data.task_uuid, botMsgId);
    } catch (e: any) { updateBotMessage(botMsgId, "❌ Ошибка"); }
  };

  const pollStatus = async (uuid: string, msgId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.checkStatus(uuid);
        if (res.success && (res.data.state === 'success' || res.data.state === 'completed')) {
          clearInterval(interval);
          updateBotMessage(msgId, `🔥 **Готово!**`, res.data.image_url);
          fetchUserData();
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const updateBotMessage = (id: string, text: string, imageUrl?: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, text, image: imageUrl, isGenerating: false } : m));
  };

  const downloadImage = async (url: string) => {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `snova_ai_${Date.now()}.png`;
      link.click();
    } catch (e) { window.open(url, '_blank'); }
  };

  const createPayment = async (packId: string) => {
    try {
      const res = await api.createPayment(packId);
      if (res.success) window.location.href = res.data.payment_url;
    } catch (e) { alert("Ошибка платежа"); }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#000', color: '#fff', fontFamily: 'Inter, sans-serif' }}>
      
      {/* HEADER (CENTERED TEXT) */}
      <header className="glass" style={{ height: '60px', padding: '0 20px', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
        <div style={{ fontWeight: 800, fontSize: '20px', letterSpacing: '1px' }}>S•NOVA AI</div>
        <div style={{ position: 'absolute', right: '20px', background: 'rgba(255,255,255,0.1)', padding: '4px 12px', borderRadius: '12px', fontSize: '13px' }}>{user?.balance || 0} кр.</div>
      </header>

      {/* CHAT AREA */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
            <div className="glass" style={{ 
              padding: '10px 14px', borderRadius: '18px', position: 'relative',
              background: msg.type === 'user' ? 'rgba(255,255,255,0.15)' : 'rgba(30,30,30,0.8)'
            }}>
              {msg.image && (
                <div style={{ position: 'relative', marginBottom: '8px' }}>
                  <img 
                    src={msg.image} 
                    onClick={() => setActiveImage(msg.image!)}
                    style={{ width: '100%', maxHeight: '280px', borderRadius: '12px', objectFit: 'cover', cursor: 'pointer' }} 
                  />
                  {!msg.isGenerating && msg.type === 'bot' && (
                    <button onClick={() => downloadImage(msg.image!)} style={{ position: 'absolute', bottom: 10, right: 10, background: 'rgba(0,0,0,0.5)', padding: '8px', borderRadius: '50%', border: 'none', color: '#fff' }}>
                      <Download size={16} />
                    </button>
                  )}
                </div>
              )}
              {msg.text && <div style={{ fontSize: '14px', lineHeight: 1.5 }}>{msg.text.split('**').map((p,i)=> i%2?<b>{p}</b>:p)}</div>}
              
              <div style={{ textAlign: 'right', fontSize: '10px', color: 'rgba(255,255,255,0.4)', marginTop: '4px' }}>{formatTime(msg.timestamp)}</div>

              {msg.type === 'bot-confirm' && (
                <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <button onClick={() => handleConfirmGen(msg.id)} style={{ padding: '12px', borderRadius: '12px', background: '#fff', color: '#000', fontWeight: 700, border: 'none' }}>🚀 Сгенерировать</button>
                  <button onClick={() => setMessages(prev => prev.filter(m => m.id !== msg.id))} style={{ padding: '8px', color: 'rgba(255,255,255,0.5)', border: 'none', background: 'none' }}>Отмена</button>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </main>

      {/* FOOTER */}
      <footer style={{ padding: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', padding: '0 10px' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative' }}>
                <img src={src} style={{ width: '45px', height: '45px', borderRadius: '8px', objectFit: 'cover' }} />
                <button onClick={() => { setSelectedFiles(p=>p.filter((_,idx)=>idx!==i)); setPreviews(p=>p.filter((_,idx)=>idx!==i)); }} style={{ position: 'absolute', top: -5, right: -5, background: '#f44', borderRadius: '50%', color: '#fff' }}><X size={8} /></button>
              </div>
            ))}
          </div>
        )}
        <div className="glass" style={{ margin: '0 10px', borderRadius: '25px', display: 'flex', alignItems: 'center', padding: '5px 15px', background: 'rgba(255,255,255,0.08)' }}>
          <button onClick={() => fileInputRef.current?.click()} style={{ background: 'none', border: 'none', color: '#fff' }}><ImageIcon size={20} /></button>
          <input value={input} onChange={e=>setInput(e.target.value)} onKeyPress={e=>e.key==='Enter'&&handleInitiate()} placeholder="Опиши идею..." style={{ flex: 1, background: 'none', border: 'none', color: '#fff', padding: '10px', outline: 'none' }} />
          <button onClick={handleInitiate} style={{ background: '#fff', borderRadius: '50%', width: '32px', height: '32px' }}><Send size={16} color="#000" /></button>
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

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', padding: '0 6px 10px' }}>
          <button onClick={() => fetchHistory()} className="btn-menu"><Sparkles size={16} /><br/>Создать</button>
          <button onClick={() => setIsModelMenuOpen(true)} className="btn-menu"><Settings size={16} /><br/>Модель</button>
          <button onClick={() => setIsSettingsMenuOpen(true)} className="btn-menu"><User size={16} /><br/>Баланс</button>
          <button onClick={() => alert("Техподдержка: @artemgavr1lov")} className="btn-menu"><HelpCircle size={16} /><br/>Помощь</button>
        </div>
      </footer>

      {/* LIGHTBOX MODAL */}
      {activeImage && (
        <div onClick={() => setActiveImage(null)} style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.95)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <img src={activeImage} style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: '12px', boxShadow: '0 0 40px rgba(0,0,0,0.5)' }} />
          <button onClick={() => setActiveImage(null)} style={{ position: 'absolute', top: 30, right: 30, color: '#fff', background: 'none', border: 'none' }}><X size={32} /></button>
          <div style={{ position: 'absolute', bottom: 40, color: 'rgba(255,255,255,0.5)', fontSize: '12px' }}>Нажми в любом месте, чтобы закрыть</div>
        </div>
      )}

      {/* BALANCE & PAYMENTS MODAL */}
      {isSettingsMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 2500, background: 'rgba(0,0,0,0.9)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', padding: '24px', borderRadius: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h3 style={{ margin: 0 }}>💳 Пополнение баланса</h3>
              <X onClick={() => setIsSettingsMenuOpen(false)} style={{ cursor: 'pointer' }} />
            </div>
            <p style={{ opacity: 0.6, fontSize: '14px' }}>Выбери пакет кредитов для мгновенного пополнения:</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {[ {id:'149', cr: 30, p:'149₽'}, {id:'299', cr: 65, p:'299₽'}, {id:'990', cr: 270, p:'990₽'} ].map(pack => (
                <button key={pack.id} onClick={() => createPayment(pack.id)} style={{ display: 'flex', justifyContent: 'space-between', padding: '16px', borderRadius: '16px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}>
                  <span><b>{pack.cr} кредитов</b></span>
                  <span style={{ color: '#0f0' }}>{pack.p}</span>
                </button>
              ))}
            </div>
            <button onClick={() => setIsSettingsMenuOpen(false)} style={{ width: '100%', marginTop: '20px', padding: '14px', borderRadius: '16px', background: '#fff', color: '#000', fontWeight: 700 }}>Закрыть</button>
          </div>
        </div>
      )}

      {/* PWA PROMPT */}
      {showPwaPrompt && (
        <div className="glass shine" style={{ position: 'fixed', bottom: 90, left: 20, right: 20, padding: '16px', borderRadius: '20px', zIndex: 4000, display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Smartphone size={32} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: '14px' }}>Установите S•NOVA AI</div>
            <div style={{ fontSize: '12px', opacity: 0.7 }}>Добавьте на главный экран за 2 клика</div>
          </div>
          <button onClick={() => setShowPwaPrompt(false)} style={{ background: '#fff', color: '#000', padding: '8px 16px', borderRadius: '12px', fontSize: '12px', fontWeight: 700 }}>Как?</button>
          <X onClick={() => setShowPwaPrompt(false)} size={16} style={{ marginLeft: '4px', opacity: 0.5 }} />
        </div>
      )}

      <style>{`
        .btn-menu { background: none; border: none; color: rgba(255,255,255,0.5); font-size: 10px; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 8px 0; }
        .btn-menu:active { color: #fff; }
        .glass { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .shine { border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 0 20px rgba(255,255,255,0.1); }
      `}</style>
    </div>
  );
}

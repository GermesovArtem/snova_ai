import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, 
  X, ChevronDown, Loader2, CheckCircle2 
} from 'lucide-react';
import { api } from '../api';

interface Message {
  id: string;
  type: 'user' | 'bot';
  text?: string;
  image?: string;
  isGenerating?: boolean;
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
  
  // Settings (Synced with bot defaults)
  const [model, setModel] = useState('nano-banana-2');
  const [settings, setSettings] = useState({
    aspect_ratio: '1:1',
    resolution: '4K',
    output_format: 'png'
  });

  // UI States
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchUserData();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, previews]);

  const fetchUserData = async () => {
    try {
      const res = await api.getMe();
      if (res.success) {
        setUser(res.data);
        setModel(res.data.model_preference || 'nano-banana-2');
        
        if (messages.length === 0) {
          const limit = (res.data.model_preference || '').includes('pro') ? 8 : 14;
          setMessages([{
            id: 'welcome',
            type: 'bot',
            text: `✨ **Добро пожаловать в S•NOVA AI!**\n\nЗдесь ты можешь сгенерировать невероятный контент 🚀\n\n🖼 **Фото → Фото:** Отправь фотографию и напиши, что поменять.\n\n📝 **Текст → Фото:** Опиши идею — и я создам её с нуля!\n\n🤖 **Твоя текущая нейросеть:** ${res.data.model_preference}\n🎁 **Баланс:** ${res.data.balance} кр.\n\n👇 **Просто отправь мне текст или фото (до ${limit} шт.) прямо сейчас!**`
          }]);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setSelectedFiles(prev => [...prev, ...files]);
      files.forEach(file => {
        const reader = new FileReader();
        reader.onloadend = () => setPreviews(prev => [...prev, reader.result as string]);
        reader.readAsDataURL(file);
      });
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    setPreviews(prev => prev.filter((_, i) => i !== index));
  };

  const getCost = () => model.includes('pro') ? 4 : 3;

  const initiateSend = () => {
    if (!input.trim() && selectedFiles.length === 0) return;
    setShowConfirm(true);
  };

  const cancelSend = () => {
    setShowConfirm(false);
  };

  const confirmAndSend = async () => {
    setShowConfirm(false);
    setIsLoading(true);

    const userMsgId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: userMsgId,
      type: 'user',
      text: input,
      image: previews[0]
    }]);

    const botMsgId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, {
      id: botMsgId,
      type: 'bot',
      text: `🚀 **Запрос подтвержден!** Начинаю генерацию (${model.includes('pro') ? 'PRO' : 'v2'})...`,
      isGenerating: true
    }]);

    try {
      const res = await api.generateEdit(input, selectedFiles);
      if (res.success && res.data.task_uuid) {
        pollStatus(res.data.task_uuid, botMsgId);
      } else {
        updateBotMessage(botMsgId, "❌ Ошибка: " + (res.error || "Неизвестная ошибка"));
      }
    } catch (e: any) {
      updateBotMessage(botMsgId, "❌ Ошибка связи: " + e.message);
    } finally {
      setInput('');
      setSelectedFiles([]);
      setPreviews([]);
      setIsLoading(false);
    }
  };

  const updateBotMessage = (id: string, text: string, imageUrl?: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, text, image: imageUrl, isGenerating: false } : m));
  };

  const pollStatus = async (uuid: string, msgId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      if (attempts > 60) {
        clearInterval(interval);
        updateBotMessage(msgId, "❌ Превышено время ожидания.");
        return;
      }

      try {
        const res = await api.checkStatus(uuid);
        if (res.success) {
          const state = res.data.state;
          const imageUrl = res.data.image_url;

          if (state === 'success' || state === 'completed') {
            clearInterval(interval);
            updateBotMessage(msgId, `🔥 **Готово!**\n\n🤖 Модель: ${model.includes('pro') ? 'Nano PRO' : 'Nano v2'}\n\n✏️ *Чтобы изменить это фото, просто отправь новый текст!*`, imageUrl);
            fetchUserData();
          } else if (state === 'failed' || state === 'error') {
            clearInterval(interval);
            updateBotMessage(msgId, "❌ Ошибка генерации: " + (res.data.error || "Unknown error"));
          }
        }
      } catch (e) {
        console.error(e);
      }
    }, 3000);
  };

  const updateModel = async (newModel: string) => {
    setModel(newModel);
    setIsModelMenuOpen(false);
    try {
      await api.updateModel(newModel);
      fetchUserData();
    } catch (e) {
      console.error(e);
    }
  };

  const toggleSetting = (key: string, val: string) => {
    setSettings(prev => ({ ...prev, [key]: val }));
  };

  return (
    <div className="chat-container" style={{ height: '100vh', width: '100vw', display: 'flex', flexDirection: 'column', background: '#000', color: '#fff', overflow: 'hidden' }}>
      <header className="glass" style={{ height: '70px', padding: '0 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', zIndex: 1000 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="logo-glow" style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#fff' }}></div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '18px' }}>S•NOVA AI</div>
            <div style={{ fontSize: '12px', color: '#44ff44', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#44ff44' }}></div> Online
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div className="glass" style={{ padding: '8px 16px', borderRadius: '12px', fontSize: '14px', fontWeight: 700 }}>
            {user?.balance || 0} кр.
          </div>
          <button onClick={() => setIsSettingsOpen(true)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}><Settings size={20} /></button>
        </div>
      </header>

      <main style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
            <div className={msg.type === 'bot' ? 'glass' : ''} style={{ padding: '12px 16px', borderRadius: '20px', background: msg.type === 'user' ? 'rgba(255,255,255,0.1)' : 'rgba(20,20,20,0.6)', border: msg.type === 'bot' ? '1px solid rgba(255,255,255,0.1)' : 'none' }}>
              {msg.image && <img src={msg.image} alt="result" style={{ width: '100%', borderRadius: '12px', marginBottom: '8px', display: 'block' }} />}
              {msg.text && (
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '15px', color: '#fff' }}>
                  {msg.text.split('**').map((part, i) => i % 2 === 1 ? <b key={i}>{part}</b> : part)}
                </div>
              )}
              {msg.isGenerating && (
                <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '10px', color: 'rgba(255,255,255,0.5)', fontSize: '14px' }}>
                  <Loader2 size={16} className="animate-spin" /> Думаю...
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </main>

      <footer style={{ padding: '10px 20px', background: 'linear-gradient(to top, #000 80%, transparent)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '10px' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                <img src={src} alt="p" style={{ width: '60px', height: '60px', borderRadius: '10px', objectFit: 'cover' }} />
                <button onClick={() => removeFile(i)} style={{ position: 'absolute', top: '-6px', right: '-6px', background: '#f44', borderRadius: '50%', color: '#fff', border: 'none', padding: '2px' }}><X size={10} /></button>
              </div>
            ))}
          </div>
        )}
        <button onClick={() => setIsModelMenuOpen(!isModelMenuOpen)} style={{ alignSelf: 'flex-start', padding: '6px 12px', borderRadius: '100px', fontSize: '12px', color: '#fff', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}>
          {model.includes('pro') ? 'Nano PRO' : 'Nano v2'} <ChevronDown size={14} />
        </button>
        <div className="glass" style={{ borderRadius: '30px', display: 'flex', alignItems: 'center', padding: '6px 12px', gap: '10px' }}>
          <button onClick={() => fileInputRef.current?.click()} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.5)', cursor: 'pointer' }}><ImageIcon size={24} /></button>
          <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && initiateSend()} placeholder="Опиши идею..." style={{ flex: 1, background: 'none', border: 'none', color: '#fff', outline: 'none' }} />
          <button onClick={initiateSend} disabled={isLoading} style={{ width: '40px', height: '40px', borderRadius: '50%', background: '#fff', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Send size={20} color="#000" /></button>
        </div>
        <input type="file" multiple ref={fileInputRef} style={{ display: 'none' }} accept="image/*" onChange={handleFileSelect} />
      </footer>

      {showConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', borderRadius: '24px', padding: '24px', background: '#111' }}>
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}><CheckCircle2 color="#44ff44" /> Всё верно?</h3>
            <div style={{ fontSize: '14px', color: 'rgba(255,255,255,0.7)', display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '10px' }}>
              <p>💰 Стоимость: <b>{getCost()} кр.</b></p>
              <p>💳 Баланс: <b>{user?.balance} кр.</b></p>
            </div>
            <div style={{ marginTop: '24px', display: 'flex', gap: '10px' }}>
              <button onClick={cancelSend} style={{ flex: 1, padding: '12px', borderRadius: '12px', background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff' }}>Назад</button>
              <button onClick={confirmAndSend} style={{ flex: 1, padding: '12px', borderRadius: '12px', background: '#fff', color: '#000', border: 'none', fontWeight: 600 }}>🚀 Создать</button>
            </div>
          </div>
        </div>
      )}

      {isModelMenuOpen && (
        <div onClick={() => setIsModelMenuOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 1500 }}>
          <div onClick={e => e.stopPropagation()} className="glass" style={{ position: 'absolute', bottom: '130px', left: '20px', width: '220px', borderRadius: '16px', padding: '10px', background: '#111' }}>
            <div onClick={() => updateModel('nano-banana-2')} style={{ padding: '12px', borderRadius: '8px', cursor: 'pointer', background: model === 'nano-banana-2' ? 'rgba(255,255,255,0.1)' : '' }}> Nano v2 (3 кр.) </div>
            <div onClick={() => updateModel('nano-banana-pro')} style={{ padding: '12px', borderRadius: '8px', cursor: 'pointer', background: model === 'nano-banana-pro' ? 'rgba(255,255,255,0.1)' : '' }}> Nano PRO (4 кр.) </div>
          </div>
        </div>
      )}

      {isSettingsOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', borderRadius: '24px', padding: '24px', background: '#111' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2>Настройки</h2>
              <button onClick={() => setIsSettingsOpen(false)} style={{ background: 'none', border: 'none', color: '#fff' }}><X size={24} /></button>
            </div>
            <div style={{ marginBottom: '24px' }}>
              <p style={{ fontSize: '10px', color: 'rgba(255,255,255,0.5)', marginBottom: '8px' }}>ФОРМАТ</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                {['1:1', '16:9', '9:16'].map(r => (
                  <button key={r} onClick={() => toggleSetting('aspect_ratio', r)} style={{ padding: '8px', borderRadius: '8px', background: settings.aspect_ratio === r ? '#fff' : 'rgba(255,255,255,0.1)', color: settings.aspect_ratio === r ? '#000' : '#fff', border: 'none' }}>{r}</button>
                ))}
              </div>
            </div>
            <button onClick={() => setIsSettingsOpen(false)} style={{ width: '100%', padding: '12px', borderRadius: '12px', background: '#fff', color: '#000', fontWeight: 600, border: 'none' }}>Сохранить</button>
            <div style={{ marginTop: '20px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textAlign: 'center' }}>S•NOVA AI v3.3 Parity Status: ACTIVE</div>
          </div>
        </div>
      )}
    </div>
  );
}

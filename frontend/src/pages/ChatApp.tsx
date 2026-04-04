import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, 
  X, ChevronDown, Loader2, CheckCircle2, User, CreditCard, HelpCircle, Sparkles
} from 'lucide-react';
import { api } from '../api';

interface Message {
  id: string;
  type: 'user' | 'bot' | 'bot-confirm';
  text?: string;
  image?: string;
  isGenerating?: boolean;
  meta?: any; // For confirmation data
}

interface UserData {
  id: number;
  name: string;
  balance: number;
  model_preference: string;
  frozen_balance?: number;
}

export default function ChatApp() {
  const [user, setUser] = useState<UserData | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // Generation Settings (State for the draft)
  const [currentModel, setCurrentModel] = useState('nano-banana-2');
  const [genSettings, setGenSettings] = useState({
    aspect_ratio: '1:1',
    resolution: '4K',
    output_format: 'png'
  });

  // UI Overlays
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  
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
        setCurrentModel(res.data.model_preference || 'nano-banana-2');
        
        if (messages.length === 0) {
          const limit = (res.data.model_preference || '').includes('pro') ? 8 : 14;
          setMessages([{
            id: 'welcome',
            type: 'bot',
            text: `✨ **Добро пожаловать в S•NOVA AI!**\n\nЗдесь ты можешь сгенерировать невероятный контент 🚀\n\n🖼 **Фото → Фото:** Отправь фотографию и напиши, что поменять (работает как магия!).\n\n📝 **Текст → Фото:** Просто опиши текстом любую безумную идею — и я создам её с нуля!\n\n🤖 **Твоя текущая нейросеть:** ${res.data.model_preference}\n🎁 **Баланс:** ${res.data.balance} кр.\n\n👇 **Просто отправь мне текст или фото (до ${limit} шт.) прямо сейчас!**`
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

  const getModelHumanName = (m: string) => m.includes('pro') ? 'Nano PRO' : 'NanoBanana 2';
  const getCost = (m: string) => m.includes('pro') ? 4 : 3;

  // STEP 1: PREPARE (Like sending images to bot)
  const handleInitiate = () => {
    if (!input.trim() && selectedFiles.length === 0) return;

    // 1. Add confirmation message to chat
    const confirmMsgId = Date.now().toString();
    const safePrompt = input.trim() || "Без текста";
    
    setMessages(prev => [...prev, {
      id: confirmMsgId,
      type: 'bot-confirm',
      text: `✨ **Ваш промпт почти готов!**\n\n📝 Текст: \`${safePrompt}\`\n📸 Фото: **${selectedFiles.length} шт.**\n🤖 Модель: **${getModelHumanName(currentModel)}**\n📐 Размер: **${genSettings.aspect_ratio}** | 💎 **${genSettings.resolution}** | 📁 **${genSettings.output_format.toUpperCase()}**\n💰 Стоимость: **${getCost(currentModel)} кр.**\n\n💳 Ваш баланс: **${user?.balance} кр.**\n\nВсё верно? Начинаем генерацию?`,
      image: previews[0], // Show one preview
      meta: { 
        prompt: input, 
        files: [...selectedFiles], 
        previews: [...previews],
        model: currentModel,
        settings: {...genSettings}
      }
    }]);

    // 2. CLEAR INPUT (Like bot)
    setInput('');
    setSelectedFiles([]);
    setPreviews([]);
  };

  // STEP 2: CONFIRM
  const handleConfirmGen = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg || !msg.meta) return;

    // Remove confirmation message, replace with "Generating"
    setMessages(prev => prev.filter(m => m.id !== msgId));
    
    const botMsgId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: botMsgId,
      type: 'bot',
      text: `🚀 **Запрос подтвержден!** Начинаю генерацию (**${getModelHumanName(msg.meta.model)}**)...`,
      isGenerating: true
    }]);

    try {
      const res = await api.generateEdit(msg.meta.prompt, msg.meta.files);
      if (res.success && res.data.task_uuid) {
        pollStatus(res.data.task_uuid, botMsgId, msg.meta.model);
      } else {
        updateBotMessage(botMsgId, "❌ Ошибка: " + (res.error || "Неизвестная ошибка"));
      }
    } catch (e: any) {
      updateBotMessage(botMsgId, "❌ Ошибка связи: " + e.message);
    }
  };

  const handleEditGen = (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg || !msg.meta) return;

    // Restore data to input
    setInput(msg.meta.prompt);
    setSelectedFiles(msg.meta.files);
    setPreviews(msg.meta.previews);
    
    // Remove confirm message
    setMessages(prev => prev.filter(m => m.id !== msgId));
  };

  const updateBotMessage = (id: string, text: string, imageUrl?: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, text, image: imageUrl, isGenerating: false } : m));
  };

  const pollStatus = async (uuid: string, msgId: string, modelUsed: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      if (attempts > 60) { clearInterval(interval); updateBotMessage(msgId, "❌ Время истекло."); return; }

      try {
        const res = await api.checkStatus(uuid);
        if (res.success) {
          const state = res.data.state;
          const imageUrl = res.data.image_url;

          if (state === 'success' || state === 'completed') {
            clearInterval(interval);
            updateBotMessage(msgId, `🔥 **Готово!**\n\n🤖 Модель: **${getModelHumanName(modelUsed)}**\n\n✏️ *Чтобы изменить это фото, просто отправь новый текст!*`, imageUrl);
            fetchUserData();
          } else if (state === 'failed' || state === 'error') {
            clearInterval(interval);
            updateBotMessage(msgId, "❌ Ошибка генерации: " + (res.data.error || "Unknown"));
          }
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const updateModel = async (newModel: string) => {
    setCurrentModel(newModel);
    setIsModelMenuOpen(false);
    try {
      await api.updateModel(newModel);
      fetchUserData();
      setMessages(prev => [...prev, { id: Date.now().toString(), type: 'bot', text: `✅ **Модель успешно обновлена!**\n\n✨ Отлично! Теперь пришлите фото и/или введите текст 👇` }]);
    } catch (e) { console.error(e); }
  };

  const toggleSetting = (key: string, val: string) => {
    setGenSettings(prev => ({ ...prev, [key]: val }));
  };

  return (
    <div className="chat-app" style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#000', color: '#fff', overflow: 'hidden' }}>
      
      {/* HEADER (Sync with Bot) */}
      <header className="glass" style={{ height: '60px', padding: '0 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', zIndex: 1000 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className="logo-glow" style={{ width: '32px', height: '32px', borderRadius: '8px', background: '#fff' }}></div>
          <div style={{ fontWeight: 700, fontSize: '18px' }}>S•NOVA AI</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className="glass" style={{ padding: '4px 10px', borderRadius: '10px', fontSize: '13px' }}>{user?.balance || 0} кр.</div>
        </div>
      </header>

      {/* CHAT AREA */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start', maxWidth: '90%' }}>
            <div className={msg.type.startsWith('bot') ? 'glass' : ''} style={{ 
              padding: '12px 16px', borderRadius: '18px', 
              background: msg.type === 'user' ? 'rgba(255,255,255,0.1)' : 'rgba(25,25,25,0.8)',
              border: msg.type.startsWith('bot') ? '1px solid rgba(255,255,255,0.1)' : 'none'
            }}>
              {msg.image && <img src={msg.image} alt="p" style={{ width: '100%', borderRadius: '12px', marginBottom: '10px' }} />}
              {msg.text && <div style={{ whiteSpace: 'pre-wrap', fontSize: '15px' }}>{msg.text.split('**').map((p,i)=> i%2?<b>{p}</b>:p)}</div>}
              
              {msg.isGenerating && (
                <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px', color: 'rgba(255,255,255,0.5)' }}>
                  <Loader2 size={16} className="animate-spin" /> Думаю...
                </div>
              )}

              {/* Bot Confirmation Inline Buttons */}
              {msg.type === 'bot-confirm' && (
                <div style={{ marginTop: '15px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <button onClick={() => handleConfirmGen(msg.id)} style={{ padding: '12px', borderRadius: '10px', background: '#fff', color: '#000', border: 'none', fontWeight: 700 }}>🚀 Сгенерировать</button>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={() => setIsSettingsMenuOpen(true)} style={{ flex: 1, padding: '10px', borderRadius: '10px', background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff' }}>⚙️ Настройки</button>
                    <button onClick={() => handleEditGen(msg.id)} style={{ flex: 1, padding: '10px', borderRadius: '10px', background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff' }}>✏️ Изменить</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </main>

      {/* INPUT AREA + REPLY KEYBOARD */}
      <footer style={{ padding: '10px', background: '#000', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        
        {/* Previews (Attachments area) */}
        {previews.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', padding: '0 10px', overflowX: 'auto' }}>
            {previews.map((src, i) => (
              <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                <img src={src} style={{ width: '50px', height: '50px', borderRadius: '8px', objectFit: 'cover' }} />
                <button onClick={() => removeFile(i)} style={{ position: 'absolute', top: -5, right: -5, background: '#f44', borderRadius: '50%', color: '#fff', border: 'none' }}><X size={10} /></button>
              </div>
            ))}
          </div>
        )}

        {/* Real Input Bar */}
        <div className="glass" style={{ margin: '0 10px', borderRadius: '25px', display: 'flex', alignItems: 'center', padding: '5px 15px', gap: '10px', background: 'rgba(255,255,255,0.05)' }}>
          <button onClick={() => fileInputRef.current?.click()} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.5)' }}><ImageIcon size={22} /></button>
          <input type="text" value={input} onChange={e=>setInput(e.target.value)} onKeyPress={e=>e.key==='Enter'&&handleInitiate()} placeholder="Опиши идею..." style={{ flex: 1, background: 'none', border: 'none', color: '#fff', outline: 'none', height: '40px' }} />
          <button onClick={handleInitiate} style={{ background: '#fff', borderRadius: '50%', width: '36px', height: '36px', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Send size={18} color="#000" /></button>
        </div>
        <input type="file" multiple ref={fileInputRef} style={{ display: 'none' }} accept="image/*" onChange={handleFileSelect} />

        {/* BOTTOM MENU (Reply Keyboard 2x2) */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', padding: '0 10px 10px' }}>
          <button onClick={() => setMessages(prev => [...prev, { id: Date.now().toString(), type: 'bot', text: `📸 Пришлите до **${currentModel.includes('pro') ? '8' : '14'} фото** для редактирования\n⌨️ Либо введите **текст**, чтобы сгенерировать новое изображение 👇` }])} style={{ padding: '12px', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: 'none', color: '#fff', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}><Sparkles size={16} /> Создать</button>
          <button onClick={() => setIsModelMenuOpen(true)} style={{ padding: '12px', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: 'none', color: '#fff', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}><Settings size={16} /> Модель</button>
          <button onClick={() => setMessages(prev => [...prev, { id: Date.now().toString(), type: 'bot', text: `👤 **Профиль**\n\n💳 Баланс: **${user?.balance} кр.**\n🤖 Модель: **${getModelHumanName(currentModel)}**\n❄️ Заморожено: **${user?.frozen_balance || 0} кр.**` }])} style={{ padding: '12px', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: 'none', color: '#fff', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}><User size={16} /> Баланс</button>
          <button onClick={() => setMessages(prev => [...prev, { id: Date.now().toString(), type: 'bot', text: `📬 **Контакты**\n\nВозникла проблема или есть предложение? Напишите нам:\n\n🛠 **Техподдержка**: @artemgavr1lov\n👔 **Менеджер**: @doloreees_s` }])} style={{ padding: '12px', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: 'none', color: '#fff', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}><HelpCircle size={16} /> Контакты</button>
        </div>
      </footer>

      {/* OVERLAY: MODEL MENU */}
      {isModelMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(0,0,0,0.9)', padding: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', padding: '24px', borderRadius: '24px' }}>
            <h3 style={{ marginBottom: '20px' }}>🤖 Управление нейросетями</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button onClick={() => updateModel('nano-banana-2')} style={{ padding: '15px', textAlign: 'left', borderRadius: '14px', background: currentModel === 'nano-banana-2' ? '#fff' : 'rgba(255,255,255,0.1)', color: currentModel === 'nano-banana-2' ? '#000' : '#fff', border: 'none' }}>
                <b>Nano Banana 2</b><br /><small>3 кр. | До 14 фото | Дизайн</small>
              </button>
              <button onClick={() => updateModel('nano-banana-pro')} style={{ padding: '15px', textAlign: 'left', borderRadius: '14px', background: currentModel === 'nano-banana-pro' ? '#fff' : 'rgba(255,255,255,0.1)', color: currentModel === 'nano-banana-pro' ? '#000' : '#fff', border: 'none' }}>
                <b>Nano PRO</b><br /><small>4 кр. | До 8 фото | Детализация лиц</small>
              </button>
              <button onClick={() => setIsModelMenuOpen(false)} style={{ marginTop: '10px', padding: '12px', color: 'rgba(255,255,255,0.5)', border: 'none', background: 'none' }}>Назад</button>
            </div>
          </div>
        </div>
      )}

      {/* OVERLAY: SETTINGS */}
      {isSettingsMenuOpen && (
        <div className="glass" style={{ position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(0,0,0,0.9)', padding: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '400px', padding: '24px', borderRadius: '24px' }}>
            <h3 style={{ marginBottom: '20px' }}>⚙️ Настройки генерации</h3>
            
            <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginBottom: '8px' }}>РАЗМЕР</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '20px' }}>
              {['1:1', '16:9', '9:16', '3:4', '4:3', '21:9'].map(r => (
                <button onClick={() => toggleSetting('aspect_ratio', r)} style={{ padding: '8px', borderRadius: '8px', border: 'none', background: genSettings.aspect_ratio === r ? '#fff' : 'rgba(255,255,255,0.1)', color: genSettings.aspect_ratio === r ? '#000' : '#fff' }}>{r}</button>
              ))}
            </div>

            <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginBottom: '8px' }}>КАЧЕСТВО</p>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
              {['1K', '2K', '4K'].map(res => (
                <button onClick={() => toggleSetting('resolution', res)} style={{ flex: 1, padding: '8px', borderRadius: '8px', border: 'none', background: genSettings.resolution === res ? '#fff' : 'rgba(255,255,255,0.1)', color: genSettings.resolution === res ? '#000' : '#fff' }}>{res}</button>
              ))}
            </div>

            <button onClick={() => setIsSettingsMenuOpen(false)} style={{ width: '100%', padding: '14px', borderRadius: '14px', background: '#fff', color: '#000', border: 'none', fontWeight: 700 }}>✅ Готово</button>
          </div>
        </div>
      )}

    </div>
  );
}

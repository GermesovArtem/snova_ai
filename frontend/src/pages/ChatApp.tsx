import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Settings, Image as ImageIcon, Download, Moon, Sun,
  X, Loader2, User, HelpCircle, Sparkles, Smartphone, History, Zap, CheckCircle2, ChevronDown, LogOut,
  Paperclip, Mic, Smile, Search, MoreVertical, ChevronLeft, MessageCircle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';

interface Message {
  id: string; // "welcome", "temp-xxx", or real DB number string
  db_id?: number; // Store the numeric ID from the server for updates/deletes
  type: 'user' | 'bot' | 'bot-confirm' | 'bot-status' | 'bot-edit-prompt';
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
  const [isBalanceModalOpen, setIsBalanceModalOpen] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [isContactsModalOpen, setIsContactsModalOpen] = useState(false);
  
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historyTasks, setHistoryTasks] = useState<any[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [editingMsgId, setEditingMsgId] = useState<string | number | null>(null);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  const [activeImage, setActiveImage] = useState<string | null>(null);
 
  const [historyLightboxTask, setHistoryLightboxTask] = useState<any>(null);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [showPwaPrompt, setShowPwaPrompt] = useState(false);
  const [modelConfig, setModelConfig] = useState<any>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    initApp();
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

  // No more localStorage persistence for messages, using server-side DB

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

    // Start with a local welcome message immediately
    const welcomeText = `✨ **Твоя нейростудия готова к новым шедеврам!**\n\nСегодня отличное время, чтобы обновить аватарку в 4K! 🚀\n\n**Что делаем сегодня?**\n📸 Просто скинь новое фото (до ${getModelLimit(currentModel)} шт.)\n⌨️ И (или) опиши свою идею текстом 👇`;
    const welcomeMsg: Message = {
      id: 'welcome-session',
      type: 'bot',
      text: welcomeText,
      timestamp: new Date()
    };
    setMessages([welcomeMsg]);

    fetchUserData();
    try {
      const res = await api.getMessages();
      if (res.success && res.data.length > 0) {
        const history = res.data.map((m: any) => ({
          id: m.id.toString(),
          db_id: m.id,
          type: m.role as any,
          text: m.text,
          image: m.image_url,
          meta: (typeof m.meta === 'string' && m.meta) ? (() => { try { return JSON.parse(m.meta); } catch(e) { return null; } })() : m.meta,
          timestamp: new Date(m.timestamp)
        }));
        setMessages([welcomeMsg, ...history]);
      }
    } catch (e) {
      console.error("History fetch error:", e);
    }

  const sendWelcome = async () => {
    const text = `✨ **Твоя нейростудия готова к новым шедеврам!**\n\nСегодня отличное время, чтобы обновить аватарку в 4K! 🚀\n\n**Что делаем сегодня?**\n📸 Просто скинь новое фото (до ${getModelLimit(currentModel)} шт.)\n⌨️ И (или) опиши свою идею текстом 👇`;
    
    // UI optimistic
    const tempId = `welcome-${Date.now()}`;
    setMessages(prev => [...prev.filter(m => m.id !== 'welcome'), {
      id: tempId,
      type: 'bot',
      text: text,
      timestamp: new Date()
    }]);

    try {
      const res = await api.saveMessage('bot', text);
      if (res.success) {
        setMessages(prev => prev.map(m => m.id === tempId ? { ...m, id: res.data.id.toString(), db_id: res.data.id } : m));
      }
    } catch (e) {
      console.error("Failed to save welcome message to DB, but keeping in UI.");
    }
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

  const getModelLimit = (model: string) => 5;

  const getModelName = (id: string) => {
    if (!id) return 'Nano Banana 2';
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
    if (url.startsWith('http') || url.startsWith('data:') || url.startsWith('blob:')) return url;
    return `/${url.replace(/^\//, '')}`;
  };

  const toggleTheme = () => {
    haptic();
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  const handleInitiate = async () => {
    if (!input.trim() && selectedFiles.length === 0) return;
    haptic();
    
    // 1. User Message (Optimistic)
    const userTempId = `user-${Date.now()}`;
    const userText = input;
    const userImage = previews[0];
    
    setMessages(prev => [...prev, {
      id: userTempId,
      type: 'user', 
      text: userText, 
      image: userImage, 
      timestamp: new Date()
    }]);

    // 2. Prepare Settings
    const isPro = currentModel.includes('pro');
    const settings = {
       aspect_ratio: isPro ? "1:1" : "auto",
       output_format: isPro ? "png" : "jpg",
       model: currentModel
    };
    
    // 3. Confirmation Bubble (Optimistic)
    const confirmTempId = `confirm-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: confirmTempId,
      type: 'bot-confirm',
      image: userImage,
      timestamp: new Date(),
      meta: { prompt: userText, files: [...selectedFiles], previews: [...previews], ...settings }
    }]);

    setInput(''); setSelectedFiles([]); setPreviews([]);

    // 4. Background Sync with DB (Wait for IDs)
    try {
      const userRes = await api.saveMessage('user', userText); // Don't send base64 to DB history
      if (userRes.success) {
        setMessages(prev => prev.map(m => m.id === userTempId ? { ...m, id: userRes.data.id.toString(), db_id: userRes.data.id } : m));
      }
      
      const confirmRes = await api.saveMessage('bot-confirm', "", undefined, { prompt: userText, ...settings });
      if (confirmRes.success) {
        setMessages(prev => prev.map(m => m.id === confirmTempId ? { ...m, id: confirmRes.data.id.toString(), db_id: confirmRes.data.id } : m));
      }
    } catch (e) {
      console.error("DB Sync failed, but UI remains updated.");
    }
  };

  const handleConfirmGen = async (msg: Message) => {
    haptic();
    const botMsgId = `status-${Date.now()}`;
    const modelName = getModelName(msg.meta.model);
    
    // Add "Request confirmed" message (Step 3)
    const statusText = `🚀 **Запрос подтвержден!** Начинаю генерацию [ **${modelName}** ]`;
    const statusRes = await api.saveMessage('bot-status', statusText);
    
    if (statusRes.success) {
      setMessages(prev => [...prev, {
        id: statusRes.data.id.toString(),
        db_id: statusRes.data.id,
        type: 'bot-status',
        text: statusText,
        isGenerating: true,
        timestamp: new Date()
      }]);
      
      try {
        const res = await api.generateEdit(msg.meta.prompt, msg.meta.files);
        if (res.success) {
          pollStatus(res.data.task_uuid, statusRes.data.id);
        } else {
          updateBotMessage(statusRes.data.id, "❌ Ошибка: " + res.error);
        }
      } catch (e: any) { 
        updateBotMessage(statusRes.data.id, `❌ Ошибка соединения`); 
      }
    }
  };

  const updateBotMessage = (dbId: number, text: string) => {
    setMessages(prev => prev.map(m => m.db_id === dbId ? { ...m, text, isGenerating: false } : m));
    api.updateMessage(dbId, text).catch(console.error);
  };

  const pollStatus = async (uuid: string, statusDbId: number) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await api.checkStatus(uuid);
        if (res.success && (res.data.state === 'success' || res.data.state === 'completed')) {
          clearInterval(interval);
          // Step 3 Deletion: Delete the "Processing" bubble
          await api.deleteMessage(statusDbId);
          setMessages(prev => prev.filter(m => m.db_id !== statusDbId));
          
          // Step 4: Show Result
          deliverResult(res.data.image_url);
          fetchUserData();
        } else if (res.data.state === 'failed' || res.data.state === 'error') {
          clearInterval(interval);
          updateBotMessage(statusDbId, `❌ **Ошибка:** ${res.data.error || "Генерация не удалась"}`);
          fetchUserData();
        } else if (attempts > 120) {
          clearInterval(interval);
          updateBotMessage(statusDbId, `⚠️ **Тайм-аут.** Проверьте историю позже.`);
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const deliverResult = async (imageUrl: string) => {
    const text = `🔥 **Результат готов!**`;
    const res = await api.saveMessage('bot', text, imageUrl);
    if (res.success) {
      setMessages(prev => [...prev, {
        id: res.data.id.toString(),
        db_id: res.data.id,
        type: 'bot',
        text: text,
        image: imageUrl,
        timestamp: new Date()
      }]);
    }
  };

  const handleRepeat = async (msg: Message) => {
    haptic();
    handleConfirmGen(msg);
  };

  const deleteMessage = async (dbId?: number, localId?: string) => {
    setMessages(prev => prev.filter(m => (dbId ? m.db_id !== dbId : true) && (localId ? m.id !== localId : true)));
    if (dbId) {
      await api.deleteMessage(dbId);
    }
  };

  const handleStartEdit = async (msg: Message) => {
    haptic();
    const text = `✏️ Чтобы изменить или дополнить эту картинку, просто отправь новый текст прямо сейчас!`;
    const res = await api.saveMessage('bot-edit-prompt', text);
    if (res.success) {
      setMessages(prev => [...prev, {
        id: res.data.id.toString(),
        db_id: res.data.id,
        type: 'bot-edit-prompt',
        text: text,
        timestamp: new Date()
      }]);
    }
  };

  const getCost = (modelId: string) => {
    if (!modelId) return 1;
    if (modelId.includes('pro-4k')) return 3;
    if (modelId.includes('pro')) return 2;
    if (modelId.includes('4k')) return 2;
    return 1;
  };

  const applySetting = async (key: string, value: string) => {
    if (!editingMsgId) return;
    const msg = messages.find(m => m.id === editingMsgId || m.db_id === editingMsgId);
    if (!msg || !msg.meta) return;

    const newMeta = { ...msg.meta, [key]: value };
    setMessages(prev => prev.map(m => (m.id === editingMsgId || m.db_id === editingMsgId) ? { ...m, meta: newMeta } : m));
    
    if (msg.db_id) {
       await api.updateMessage(msg.db_id, undefined, newMeta);
    }
    haptic();
  };

  const updateModel = async (m: string) => {
    haptic();
    setCurrentModel(m);
    try { await api.updateModel(m); fetchUserData(); } catch (e) {}
  };

  const renderText = (text: string = "") => {
    return text.split('**').map((part, i) => (
      i % 2 === 1 ? <b key={i}>{part}</b> : part
    ));
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

      {/* SETTINGS MODAL */}
      {isSettingsModalOpen && editingMsgId && (
        <div className="modal-overlay" onClick={() => setIsSettingsModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{ padding: '20px' }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>⚙️ Настройки генерации</h3>
              
              <div style={{ display: 'grid', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '14px', marginBottom: '8px', opacity: 0.7 }}>📐 Размер (Aspect Ratio)</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                    {['1:1', '16:9', '9:16', '3:4', '4:3', '21:9'].map(r => (
                      <button 
                        key={r}
                        className={`tg-key-btn ${(messages.find(m=>m.id===editingMsgId || m.db_id===editingMsgId)?.meta?.aspect_ratio === r) ? 'active' : ''}`}
                        style={{ padding: '10px', fontSize: '12px', border: (messages.find(m=>m.id===editingMsgId || m.db_id===editingMsgId)?.meta?.aspect_ratio === r) ? '2px solid var(--tg-accent)' : 'none' }}
                        onClick={() => applySetting('aspect_ratio', r)}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '14px', marginBottom: '8px', opacity: 0.7 }}>📁 Формат</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    {['png', 'jpg'].map(f => (
                      <button 
                        key={f}
                        className={`tg-key-btn ${(messages.find(m=>m.id===editingMsgId || m.db_id===editingMsgId)?.meta?.output_format === f) ? 'active' : ''}`}
                        style={{ padding: '10px', fontSize: '12px', border: (messages.find(m=>m.id===editingMsgId || m.db_id===editingMsgId)?.meta?.output_format === f) ? '2px solid var(--tg-accent)' : 'none' }}
                        onClick={() => applySetting('output_format', f)}
                      >
                        {f.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <button 
                className="tg-key-btn" 
                style={{ width: '100%', marginTop: '24px', background: 'var(--tg-accent)', color: '#fff' }}
                onClick={() => setIsSettingsModalOpen(false)}
              >
                ✅ Готово
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MESSAGES */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ margin: '8px auto', background: 'rgba(0,0,0,0.15)', padding: '2px 12px', borderRadius: '12px', fontSize: '12px', color: '#fff', opacity: 0.8 }}>
          {new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
        </div>

        <AnimatePresence initial={false}>
          {messages.filter(m => m.type !== 'user').map((msg) => (
            <div key={msg.id} className={`bubble ${msg.type === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
              
              {msg.image && (
                <div style={{ position: 'relative', marginBottom: '8px' }}>
                  <img 
                    src={fixUrl(msg.image)} 
                    alt="preview" 
                    style={{ width: '100%', maxWidth: '280px', maxHeight: '320px', objectFit: 'cover', borderRadius: '12px', cursor: 'pointer' }}
                    onClick={() => setActiveImage(fixUrl(msg.image))}
                  />
                </div>
              )}

              {msg.type === 'bot-confirm' && msg.meta && (
                <div style={{ marginTop: '10px', borderTop: '1px solid var(--glass-border)', paddingTop: '10px' }}>
                    <div style={{ fontSize: '13px', marginBottom: '10px', opacity: 0.9 }}>
                      ✨ <b>Ваш промпт почти готов!</b><br/><br/>
                      📝 Текст: <code>{msg.meta.prompt || "Без текста"}</code><br/>
                      🤖 Модель: **{getModelName(msg.meta.model)}**<br/>
                      📐 Размер: **{msg.meta.aspect_ratio}** | 📁 **{msg.meta.output_format?.toUpperCase()}**<br/>
                      💰 Стоимость: **{getCost(msg.meta.model)} ⚡️**
                    </div>
                    <div style={{ display: 'grid', gap: '6px' }}>
                      <button className="tg-key-btn" style={{ padding: '8px', background: 'var(--tg-accent)', color: '#fff' }} onClick={() => handleConfirmGen(msg)}>
                        🚀 Сгенерировать
                      </button>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                        <button className="tg-key-btn" style={{ padding: '8px' }} onClick={() => { haptic(); setEditingMsgId(msg.id); setIsSettingsModalOpen(true); }}>
                          ⚙️ Настройки
                        </button>
                        <button className="tg-key-btn" style={{ padding: '8px' }} onClick={() => { haptic(); deleteMessage(msg.db_id, msg.id); sendWelcome(); }}>
                          ❌ Отмена
                        </button>
                    </div>
                  </div>
                </div>
              )}

              {msg.type === 'bot-status' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px' }}>
                  {renderText(msg.text)}
                  <div className="loader-small"></div>
                </div>
              )}

              {msg.type === 'bot-edit-prompt' && (
                <div style={{ display: 'grid', gap: '10px' }}>
                   <div style={{ fontSize: '15px', whiteSpace: 'pre-wrap' }}>{renderText(msg.text)}</div>
                   <button className="tg-key-btn" style={{ padding: '8px' }} onClick={() => { haptic(); deleteMessage(msg.db_id, msg.id); sendWelcome(); }}>
                     ❌ Отмена
                   </button>
                </div>
              )}

              {msg.type === 'bot' && !msg.image && (
                <div style={{ fontSize: '15px', whiteSpace: 'pre-wrap' }}>
                  {renderText(msg.text)}
                </div>
              )}

              {msg.type === 'bot' && msg.image && (
                <div style={{ marginTop: '10px', display: 'grid', gap: '8px' }}>
                  <div style={{ fontSize: '15px', whiteSpace: 'pre-wrap', marginBottom: '8px' }}>
                    {renderText(msg.text)}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => window.open(msg.image, '_blank')}>
                      📥 Скачать результат
                    </button>
                    <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => handleRepeat(msg)}>
                      🔄 Повторить
                    </button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => sendWelcome()}>
                      🖼 Новая генерация
                    </button>
                    <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => handleStartEdit(msg)}>
                      ✏️ Редактировать
                    </button>
                  </div>
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
          <button className="tg-key-btn" onClick={() => { haptic(); setIsContactsModalOpen(true); }}><HelpCircle size={20} /> Шаблоны</button>
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

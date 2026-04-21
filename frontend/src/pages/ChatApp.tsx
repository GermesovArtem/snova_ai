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
  type: 'user' | 'bot' | 'bot-confirm' | 'bot-status' | 'bot-result' | 'bot-edit-prompt';
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
    fetchConfig();
    const pwaClosed = localStorage.getItem('pwa_closed');
    if (!pwaClosed) {
      setTimeout(() => setShowPwaPrompt(true), 3000);
    }

    const handleBeforeInstall = (e: any) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // No more localStorage persistence for messages, using server-side DB

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const initApp = async () => {
    // 1. Static Welcome
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
      // 2. Load History First (Foundation)
      const res = await api.getHistory();
      let history: Message[] = [];
      if (res.success && res.data.length > 0) {
        history = res.data.map((m: any) => ({
          id: m.task_uuid || m.id.toString(),
          db_id: m.id,
          type: 'bot-result',
          text: `🖼 **Результат:** ${m.prompt || 'Изображение'}\n🤖 Модель: ${getModelName(m.model)}\n📐 Размер: ${m.aspect_ratio || '1:1'} | ${m.output_format?.toUpperCase() || 'PNG'}\n💰 Стоимость: ${m.credits_cost} ⚡️`,
          image: m.image_url,
          meta: { prompt: m.prompt, model: m.model, aspect_ratio: m.aspect_ratio, output_format: m.output_format },
          timestamp: new Date(m.created_at || Date.now())
        }));
      }

      // 3. Check Active Tasks and "Reanimate" existing history bubbles
      const activeRes = await api.getActiveTasks();
      const activeTaskMap = new Map();
      if (activeRes.success) {
        activeRes.data.forEach((task: any) => {
          const targetId = task.status_message_id || task.id;
          activeTaskMap.set(targetId, task);
        });
      }

      const finalMessages = history.map(m => {
        if (m.db_id && activeTaskMap.has(m.db_id)) {
          const task = activeTaskMap.get(m.db_id);
          pollStatus(task.task_uuid, m.id); // m.id is the task_uuid or string ID
          return { ...m, isGenerating: true, text: `🚀 **Продолжаю генерацию...**` };
        }
        return m;
      });

      // deduplicate welcome
      const hasHistoryWelcome = finalMessages.some((m: any) => m.text?.includes("нейростудия готова"));
      setMessages(hasHistoryWelcome ? finalMessages : [welcomeMsg, ...finalMessages]);

    } catch (e) {
      console.error("Init app synchronization error:", e);
    }
  };

  const sendWelcome = async () => {
    const text = `✨ **Твоя нейростудия готова к новым шедеврам!**\n\nСегодня отличное время, чтобы обновить аватарку в 4K! 🚀\n\n**Что делаем сегодня?**\n📸 Просто скинь новое фото (до ${getModelLimit(currentModel)} шт.)\n⌨️ И (или) опиши свою идею текстом 👇`;
    
    // Ephemeral welcome message
    const tempId = `welcome-${Date.now()}`;
    setMessages(prev => [...prev.filter(m => m.id !== 'welcome'), {
      id: tempId,
      type: 'bot',
      text: text,
      timestamp: new Date()
    }]);

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
       output_format: "png",
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

    // 4. No DB Sync for Text Messages
    // Keep it ephemeral, DB will only store GenerationTasks
    if (selectedFiles.length > 0) {
       try {
         const uploadRes = await api.uploadImage(selectedFiles[0]);
         if (uploadRes.success) {
            const finalImageUrl = uploadRes.data.url;
            setMessages(prev => prev.map(m => [userTempId, confirmTempId].includes(m.id) ? { ...m, image: finalImageUrl, meta: { ...m.meta, s3_urls: [finalImageUrl] } } : m));
         }
       } catch (e) {
         console.error("Image upload failed during initiation:", e);
       }
    }

  const handleConfirmGen = async (msg: Message) => {
    haptic();
    const modelName = getModelName(msg.meta.model);
    
    // Add "Request confirmed" message
    const statusText = `🚀 **Запрос подтвержден!** Начинаю генерацию [ **${modelName}** ]`;
    const tempStatusId = `status-${Date.now()}`;
    
    setMessages(prev => [...prev, {
      id: tempStatusId,
      type: 'bot-status',
      text: statusText,
      isGenerating: true,
      timestamp: new Date()
    }]);
      
    try {
      if (!msg.meta?.files?.length && !msg.image) {
        alert("❌ Файл не найден. Пожалуйста, загрузите фото заново.");
        return;
      }

      // Use existing S3 URLs if available from the initiation phase
      const s3Urls = msg.meta?.s3_urls || [];
      
      const res = await api.generateEdit(
        msg.meta.prompt, 
        s3Urls.length > 0 ? [] : (msg.meta.files || []), // If we have S3 URLs, we don't need to re-upload files
        msg.meta.model, 
        msg.meta.aspect_ratio, 
        msg.meta.output_format,
        undefined, // NO status_message_id
        s3Urls[0]
      );
      if (res.success) {
        pollStatus(res.data.task_uuid, tempStatusId); // Pass local temp ID
      } else {
        alert(`Ошибка генерации: ${res.error || "Неизвестная ошибка"}`);
        // Remove the loading bubble if it failed
        setMessages(prev => prev.filter(m => m.id !== tempStatusId));
      }
    } catch (e: any) { 
      updateBotMessage(tempStatusId, `❌ Ошибка соединения`); 
    }
  };

  const updateBotMessage = (localId: string, text: string) => {
    setMessages(prev => prev.map(m => m.id === localId ? { ...m, text, isGenerating: false } : m));
  };

  const pollStatus = async (uuid: string, localStatusId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await api.checkStatus(uuid);
        if (res.success && (res.data.state === 'success' || res.data.state === 'completed')) {
          clearInterval(interval);
          // Remove status bubble locally
          setMessages(prev => prev.filter(m => m.id !== localStatusId));
          // Show result locally
          deliverResult(res.data.image_url, uuid);
          fetchUserData();
        } else if (res.data.state === 'failed' || res.data.state === 'error') {
          clearInterval(interval);
          updateBotMessage(localStatusId, `❌ **Ошибка:** ${res.data.error || "Генерация не удалась"}`);
          fetchUserData();
        } else if (attempts > 120) {
          clearInterval(interval);
          updateBotMessage(localStatusId, `⚠️ **Тайм-аут.** Проверьте историю позже.`);
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const deliverResult = async (imageUrl: string, uuid: string) => {
    const text = `🔥 **Результат готов!**`;
    // We don't save this to WebChatMessage anymore. 
    // It will be loaded from GenerationTask history on next refresh.
    setMessages(prev => [...prev, {
      id: uuid,
      type: 'bot-result',
      text: text,
      image: imageUrl,
      timestamp: new Date()
    }]);
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

  const handleCancelAndNew = async (dbId?: number, localId?: string) => {
    await deleteMessage(dbId, localId);
    if (fileInputRef.current) fileInputRef.current.value = '';
    
    // Check if the last bot message is already a welcome message
    setMessages(prev => {
      const visible = prev.filter(m => m.type !== 'user');
      const last = visible[visible.length - 1];
      if (last && (last.id === 'welcome-session' || last.id.startsWith('welcome-'))) return prev;
      
      // If not, we could show a welcome message, but usually the user wants to return to the root.
      // We'll just trigger sendWelcome if history is effectively empty or last is result.
      return prev;
    });
    haptic();
  };

  const handleStartEdit = async (msg: Message) => {
    haptic();
    const text = `✏️ Чтобы изменить или дополнить эту картинку, просто отправь новый текст прямо сейчас!`;
    const tempId = `edit-prompt-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: tempId,
      type: 'bot-edit-prompt',
      text: text,
      timestamp: new Date()
    }]);
  };

  const getCost = (modelId: string) => {
    if (!modelId) return 1;
    if (modelConfig?.credits_per_model?.[modelId]) {
      return modelConfig.credits_per_model[modelId];
    }
    // Fallback logic for basic variants if config is not yet loaded or doesn't match
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

        <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <img src="/logo.png" alt="S•NOVA AI" onClick={() => window.location.reload()} style={{ cursor: 'pointer' }} />
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
            <div key={msg.id} className="bubble bubble-bot">
              <div className="bubble-content-flex" style={{ alignItems: 'stretch' }}> {/* Stretch to match image height */}
                {msg.image && (
                  <img src={fixUrl(msg.image)} className="bubble-image-side" alt="Result" />
                )}
                
                <div className="bubble-text-side" style={{ justifyContent: 'space-between' }}> {/* Spread items vertically */}
                  <div>
                    {msg.type === 'bot-confirm' && msg.meta && (
                      <div style={{ fontSize: '13px', marginBottom: '10px', opacity: 0.9 }}>
                        ✨ <b>Ваш промпт почти готов!</b><br/><br/>
                        📝 Текст: <code>{msg.meta.prompt || "Без текста"}</code><br/>
                        🤖 Модель: {renderText(getModelName(msg.meta.model))}<br/>
                        📐 Размер: {renderText(msg.meta.aspect_ratio)} | 📁 {renderText(msg.meta.output_format?.toUpperCase())}<br/>
                        💰 Стоимость: {renderText(`${getCost(msg.meta.model)} ⚡️`)}
                      </div>
                    )}

                    {!['bot-confirm', 'bot-status'].includes(msg.type) && (
                      <div style={{ fontSize: '15px', whiteSpace: 'pre-wrap' }}>{renderText(msg.text)}</div>
                    )}
                    
                    {msg.type === 'bot-status' && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', color: 'var(--tg-accent)' }}>
                        {renderText(msg.text)}
                        <div className="loader-small"></div>
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'grid', gap: '6px', marginTop: '10px' }}>
                    {msg.type === 'bot-confirm' && (
                      <button className="tg-key-btn" style={{ padding: '8px', background: 'var(--tg-accent)', color: '#fff' }} onClick={() => handleConfirmGen(msg)}>
                        🚀 Сгенерировать
                      </button>
                    )}
                    
                    {msg.type === 'bot-confirm' && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <button className="tg-key-btn" style={{ padding: '8px', background: 'var(--tg-button)' }} onClick={() => { haptic(); setEditingMsgId(msg.id); setIsSettingsModalOpen(true); }}>
                          ⚙️ Настройки
                        </button>
                        <button className="tg-key-btn" style={{ padding: '8px', background: 'var(--tg-button)' }} onClick={() => handleCancelAndNew(msg.db_id, msg.id)}>
                          ❌ Отмена
                        </button>
                      </div>
                    )}

                    {['bot', 'bot-result'].includes(msg.type) && msg.image && (
                      <div style={{ display: 'grid', gap: '8px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                          <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => window.open(msg.image, '_blank')}>
                            📥 Скачать
                          </button>
                          <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => handleRepeat(msg)}>
                            🔄 Повтор
                          </button>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                          <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => sendWelcome()}>
                            🖼 Новая
                          </button>
                          <button className="tg-key-btn" style={{ padding: '8px', fontSize: '12px' }} onClick={() => handleStartEdit(msg)}>
                            ✏️ Правка
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

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
                  {modelConfig?.credit_packs ? (
                    Object.entries(modelConfig.credit_packs).map(([price, credits]: [string, any]) => (
                      <button key={price} className="tg-key-btn" style={{ justifyContent: 'space-between', padding: '18px' }} onClick={() => api.createPayment(price).then(r=>r.success&&(window.location.href=r.data.payment_url))}>
                        <span style={{ fontSize: '16px' }}>{credits} ⚡</span> 
                        <span style={{ color: 'var(--tg-accent)', fontWeight: 'bold', fontSize: '16px' }}>{price}₽</span>
                      </button>
                    ))
                  ) : (
                    // Fallback
                    [ {id:'149', cr: 30, p:'149₽'}, {id:'299', cr: 65, p:'299₽'}, {id:'990', cr: 270, p:'990₽'} ].map(p => (
                      <button key={p.id} className="tg-key-btn" style={{ justifyContent: 'space-between', padding: '18px' }} onClick={() => api.createPayment(p.id).then(r=>r.success&&(window.location.href=r.data.payment_url))}>
                        <span style={{ fontSize: '16px' }}>{p.cr} ⚡</span> 
                        <span style={{ color: 'var(--tg-accent)', fontWeight: 'bold', fontSize: '16px' }}>{p.p}</span>
                      </button>
                    ))
                  )}
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

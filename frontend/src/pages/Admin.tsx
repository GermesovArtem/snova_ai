import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Users, 
  Zap, 
  TrendingUp, 
  Search, 
  Plus, 
  LogOut, 
  LayoutDashboard, 
  CreditCard,
  Settings as SettingsIcon,
  ShieldCheck,
  AlertTriangle,
  RefreshCw
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import { api } from '../api';

const Admin: React.FC = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('admin_token'));
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'dashboard' | 'users'>('dashboard');

  useEffect(() => {
    if (isLoggedIn) {
      loadData();
    }
  }, [isLoggedIn]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsRes, usersRes] = await Promise.all([
        api.getAdminStats(),
        api.adminListUsers()
      ]);
      setStats(statsRes);
      setUsers(usersRes);
    } catch (err) {
      console.error(err);
      if (typeof err === 'object' && err !== null && 'message' in err && (err as any).message.includes('401')) {
        handleLogout();
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.adminLogin(username, password);
      localStorage.setItem('admin_token', res.access_token);
      setIsLoggedIn(true);
    } catch (err: any) {
      setError('Неверный логин или пароль');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    setIsLoggedIn(false);
  };

  const handleUpdateBalance = async (userId: number, amount: number) => {
    try {
      await api.adminUpdateBalance(userId, amount);
      loadData(); // Refresh
      alert('Баланс обновлен!');
    } catch (err) {
      alert('Ошибка при обновлении баланса');
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-[#0a0a0b] flex items-center justify-center p-4">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md bg-white/5 border border-white/10 p-8 rounded-3xl backdrop-blur-xl"
        >
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-gradient-to-tr from-yellow-400 to-orange-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/20">
              <ShieldCheck className="text-white w-10 h-10" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white text-center mb-2">S•NOVA Admin</h1>
          <p className="text-white/40 text-center mb-8 text-sm">Введите учетные данные для входа</p>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs uppercase tracking-widest text-white/40 mb-2 font-medium">Username</label>
              <input 
                type="text" 
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50 transition-colors"
                placeholder="admin"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-widest text-white/40 mb-2 font-medium">Password</label>
              <input 
                type="password" 
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50 transition-colors"
                placeholder="••••••••"
              />
            </div>
            {error && <p className="text-red-400 text-xs text-center">{error}</p>}
            <button 
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-yellow-400 to-orange-500 text-black font-bold py-3 rounded-xl hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
            >
              {loading ? <RefreshCw className="animate-spin w-4 h-4" /> : 'Вход в панель'}
            </button>
          </form>
        </motion.div>
      </div>
    );
  }

  const filteredUsers = users.filter(u => 
    String(u.id).includes(search) || 
    (u.name && u.name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-[#0a0a0b] text-white flex">
      {/* Sidebar */}
      <div className="w-64 border-r border-white/5 p-6 flex flex-col gap-8">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-yellow-500 rounded-lg flex items-center justify-center font-bold text-black text-xs">SN</div>
          <span className="font-bold tracking-tight">ADMIN PANEL</span>
        </div>

        <nav className="flex-1 space-y-2">
          <button 
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'dashboard' ? 'bg-white/10 text-yellow-400' : 'text-white/40 hover:bg-white/5'}`}
          >
            <LayoutDashboard size={18} />
            <span className="text-sm font-medium">Дашборд</span>
          </button>
          <button 
            onClick={() => setActiveTab('users')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'users' ? 'bg-white/10 text-yellow-400' : 'text-white/40 hover:bg-white/5'}`}
          >
            <Users size={18} />
            <span className="text-sm font-medium">Пользователи</span>
          </button>
        </nav>

        <button 
          onClick={handleLogout}
          className="flex items-center gap-3 px-4 py-3 rounded-xl text-red-400/60 hover:bg-red-400/5 transition-all text-sm font-medium"
        >
          <LogOut size={18} />
          Выйти
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-12">
        <div className="max-w-6xl mx-auto">
          
          <AnimatePresence mode="wait">
            {activeTab === 'dashboard' ? (
              <motion.div 
                key="dashboard"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-8"
              >
                <div className="flex justify-between items-end">
                  <div>
                    <h2 className="text-3xl font-bold">Обзор системы</h2>
                    <p className="text-white/40 mt-1">Основные показатели роста и активности</p>
                  </div>
                  <button onClick={loadData} className="p-2 bg-white/5 rounded-lg border border-white/10 hover:bg-white/10 transition-colors">
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                  </button>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="bg-white/5 border border-white/5 p-6 rounded-3xl">
                    <div className="flex justify-between items-start mb-4">
                      <div className="p-3 bg-blue-500/10 rounded-2xl text-blue-400">
                        <Users size={24} />
                      </div>
                      <span className="text-xs font-bold text-green-400 flex items-center gap-1">
                        <TrendingUp size={12} /> +{stats?.summary?.new_today || 0}
                      </span>
                    </div>
                    <div className="text-2xl font-bold">{stats?.summary?.total_users || 0}</div>
                    <div className="text-sm text-white/40">Всего пользователей</div>
                  </div>

                  <div className="bg-white/5 border border-white/5 p-6 rounded-3xl">
                    <div className="flex justify-between items-start mb-4">
                      <div className="p-3 bg-yellow-500/10 rounded-2xl text-yellow-400">
                        <Zap size={24} />
                      </div>
                    </div>
                    <div className="text-2xl font-bold">{stats?.summary?.total_generations || 0}</div>
                    <div className="text-sm text-white/40">Выполнено генераций</div>
                  </div>

                  <div className="bg-white/5 border border-white/5 p-6 rounded-3xl">
                    <div className="flex justify-between items-start mb-4">
                      <div className="p-3 bg-green-500/10 rounded-2xl text-green-400">
                        <CreditCard size={24} />
                      </div>
                    </div>
                    <div className="text-2xl font-bold">Активен</div>
                    <div className="text-sm text-white/40">Статус сервера</div>
                  </div>
                </div>

                {/* Charts */}
                <div className="grid grid-cols-1 gap-6">
                  <div className="bg-white/5 border border-white/5 p-8 rounded-3xl overflow-hidden">
                    <h3 className="font-bold mb-8 flex items-center gap-2">
                      <TrendingUp size={18} className="text-yellow-400" />
                      Активность за 7 дней
                    </h3>
                    <div className="h-[300px] w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={stats?.chart || []}>
                          <defs>
                            <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#eab308" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#eab308" stopOpacity={0}/>
                            </linearGradient>
                            <linearGradient id="colorGens" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#ffffff0a" />
                          <XAxis dataKey="date" stroke="#ffffff33" fontSize={12} tickLine={false} axisLine={false} />
                          <YAxis stroke="#ffffff33" fontSize={12} tickLine={false} axisLine={false} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#18181b', border: '1px solid #ffffff14', borderRadius: '12px' }}
                            itemStyle={{ fontSize: '12px' }}
                          />
                          <Area type="monotone" dataKey="users" name="Новые юзеры" stroke="#eab308" strokeWidth={3} fillOpacity={1} fill="url(#colorUsers)" />
                          <Area type="monotone" dataKey="generations" name="Генерации" stroke="#22c55e" strokeWidth={3} fillOpacity={1} fill="url(#colorGens)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div 
                key="users"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-8"
              >
                <div className="flex justify-between items-end">
                  <div>
                    <h2 className="text-3xl font-bold">Пользователи</h2>
                    <p className="text-white/40 mt-1">Всего зарегистрировано: {users.length}</p>
                  </div>
                  <div className="flex gap-4">
                    <div className="relative">
                      <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-white/20 w-4 h-4" />
                      <input 
                        type="text" 
                        placeholder="Поиск по ID или имени..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        className="bg-white/5 border border-white/10 rounded-xl pl-11 pr-4 py-3 text-sm focus:outline-none focus:border-yellow-500/50 w-64 transition-all"
                      />
                    </div>
                  </div>
                </div>

                <div className="bg-white/5 border border-white/5 rounded-3xl overflow-hidden">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-white/5 bg-white/[0.02]">
                        <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest">ID / User</th>
                        <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest">Баланс</th>
                        <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest">Дата рег.</th>
                        <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest text-right">Действия</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {filteredUsers.map(user => (
                        <tr key={user.id} className="hover:bg-white/[0.02] transition-colors group">
                          <td className="px-6 py-4">
                            <div className="font-bold text-sm text-white/80">{user.name || 'Anonymous'}</div>
                            <div className="text-xs text-white/20 font-mono tracking-tighter">{user.id}</div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-1 rounded-lg text-xs font-bold ${user.balance > 0 ? 'bg-yellow-500/10 text-yellow-500' : 'bg-red-500/10 text-red-500'}`}>
                                {int(user.balance)} кр.
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm text-white/40">
                             {new Date(user.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-6 py-4 text-right">
                             <div className="flex justify-end gap-2">
                                <button 
                                  onClick={() => {
                                    const amount = window.prompt("Сколько кредитов добавить (или вычесть, если с минусом)?", "10");
                                    if (amount) handleUpdateBalance(user.id, parseFloat(amount));
                                  }}
                                  className="p-2 bg-white/5 rounded-lg border border-white/10 text-yellow-400 hover:bg-yellow-400 hover:text-black transition-all"
                                >
                                  <Plus size={16} />
                                </button>
                             </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

const int = (v: any) => Math.floor(parseFloat(v || 0));

export default Admin;

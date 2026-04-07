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
  ShieldCheck,
  RefreshCw,
  Menu,
  X
} from 'lucide-react';
import { 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import { api } from '../api';
import './Admin.css';

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
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

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
      <div className="login-screen">
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="login-card"
        >
          <div className="login-icon-box">
            <ShieldCheck size={32} color="#000" />
          </div>
          <h1 className="login-title">S•NOVA AI</h1>
          <p className="login-subtitle">Центр управления</p>
          
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label">Логин</label>
              <input 
                type="text" 
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="admin-input"
                placeholder="admin"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Пароль</label>
              <input 
                type="password" 
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="admin-input"
                placeholder="••••••••"
              />
            </div>
            {error && <p style={{color: '#ff4d4d', fontSize: '12px', marginBottom: '15px'}}>{error}</p>}
            <button type="submit" disabled={loading} className="login-btn">
              {loading ? <RefreshCw className="spinner" size={20} /> : 'Войти в систему'}
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
    <div className="admin-container">
      {/* Sidebar Mobile Backdrop */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsSidebarOpen(false)}
            className="sidebar-backdrop"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <aside className={`admin-sidebar ${isSidebarOpen ? 'open' : ''}`}>
        <div className="admin-logo">
          <div className="logo-icon">SN</div>
          <div className="logo-text">АДМИН</div>
          <button className="sidebar-close-btn" onClick={() => setIsSidebarOpen(false)}>
            <X size={20} />
          </button>
        </div>

        <nav className="nav-links">
          <button 
            onClick={() => { setActiveTab('dashboard'); setIsSidebarOpen(false); }}
            className={`nav-link ${activeTab === 'dashboard' ? 'active' : ''}`}
          >
            <LayoutDashboard size={18} />
            Дашборд
          </button>
          <button 
            onClick={() => { setActiveTab('users'); setIsSidebarOpen(false); }}
            className={`nav-link ${activeTab === 'users' ? 'active' : ''}`}
          >
            <Users size={18} />
            Пользователи
          </button>
        </nav>

        <button onClick={handleLogout} className="nav-link logout-btn">
          <LogOut size={18} />
          Выйти
        </button>
      </aside>

      {/* Main Content */}
      <main className="admin-main">
        <div className="admin-mobile-header">
          <button className="menu-toggle-btn" onClick={() => setIsSidebarOpen(true)}>
            <Menu size={24} />
          </button>
          <div className="logo-text">S•NOVA AI</div>
        </div>

        <div className="admin-content-inner">
          <AnimatePresence mode="wait">
            {activeTab === 'dashboard' ? (
              <motion.div key="dashboard" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                <div className="header-section">
                  <div className="header-title">
                    <h2>Обзор</h2>
                    <p>Метрики производительности системы</p>
                  </div>
                  <button onClick={loadData} className="action-btn">
                    <RefreshCw size={16} className={loading ? 'spinner' : ''} />
                  </button>
                </div>

                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-icon-wrapper stat-blue"><Users size={20} /></div>
                    <div className="stat-value">{stats?.data?.total_users || 0}</div>
                    <div className="stat-label">Всего пользователей</div>
                    <div className="stat-sublabel">+{stats?.data?.new_users_today || 0} сегодня</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon-wrapper stat-yellow"><Zap size={20} /></div>
                    <div className="stat-value">{stats?.data?.total_gens || 0}</div>
                    <div className="stat-label">Генераций выполнено</div>
                    <div className="stat-sublabel">+{stats?.data?.gens_today || 0} сегодня</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon-wrapper stat-green"><CreditCard size={20} /></div>
                    <div className="stat-value">{Math.round(stats?.data?.total_revenue || 0)} ₽</div>
                    <div className="stat-label">Общая выручка</div>
                    <div className="stat-sublabel">+{Math.round(stats?.data?.revenue_today || 0)} ₽ сегодня</div>
                  </div>
                </div>

                <div className="chart-container">
                  <div className="chart-header">
                    <TrendingUp size={18} style={{color: '#facc15'}} />
                    Выручка и рост (7 дней)
                  </div>
                  <div className="chart-wrapper">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={stats?.data?.chart_data || []}>
                        <defs>
                          <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#4ade80" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#4ade80" stopOpacity={0}/>
                          </linearGradient>
                          <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#facc15" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#facc15" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="date" stroke="rgba(255,255,255,0.2)" fontSize={10} tickLine={false} axisLine={false} />
                        <YAxis stroke="rgba(255,255,255,0.2)" fontSize={10} tickLine={false} axisLine={false} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }}
                          itemStyle={{ fontSize: '11px', color: '#fff' }}
                        />
                        <Area type="monotone" dataKey="revenue" name="Выручка (₽)" stroke="#4ade80" strokeWidth={3} fillOpacity={1} fill="url(#colorRevenue)" />
                        <Area type="monotone" dataKey="new_users" name="Новые пользователи" stroke="#facc15" strokeWidth={3} fillOpacity={1} fill="url(#colorUsers)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div key="users" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                <div className="header-section flex-col-mobile">
                  <div className="header-title">
                    <h2>Пользователи</h2>
                    <p>Управление {users.length} аккаунтами</p>
                  </div>
                  <div className="search-wrapper">
                    <Search className="search-icon" size={16} />
                    <input 
                      type="text" 
                      placeholder="Поиск по ID или имени..."
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      className="admin-search"
                    />
                  </div>
                </div>

                <div className="table-container">
                  <div className="table-scroll">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>ID / ИМЯ</th>
                          <th>БАЛАНС</th>
                          <th>РЕГИСТРАЦИЯ</th>
                          <th style={{textAlign: 'right'}}>ДЕЙСТВИЯ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredUsers.map(user => (
                          <tr key={user.id}>
                            <td>
                              <div className="user-info">
                                <div className="user-name">{user.name || 'Неизвестно'}</div>
                                <div className="user-id">{user.id}</div>
                              </div>
                            </td>
                            <td>
                              <span className={`balance-badge ${user.balance > 0 ? 'balance-positive' : 'balance-zero'}`}>
                                {Math.floor(user.balance || 0)} кр.
                              </span>
                            </td>
                            <td><span style={{color: 'rgba(255,255,255,0.3)', fontSize: '13px'}}>{new Date(user.created_at).toLocaleDateString()}</span></td>
                            <td style={{textAlign: 'right'}}>
                              <button 
                                onClick={() => {
                                  const amount = window.prompt("Добавить кредиты (отрицательное — отнять):", "10");
                                  if (amount) handleUpdateBalance(user.id, parseFloat(amount));
                                }}
                                className="action-btn"
                                style={{marginLeft: 'auto'}}
                              >
                                <Plus size={16} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
};

export default Admin;

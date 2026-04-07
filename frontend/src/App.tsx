import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import ChatApp from './pages/ChatApp';
import Admin from './pages/Admin';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));

  useEffect(() => {
    // Инициализация Telegram WebApp
    if ((window as any).Telegram?.WebApp) {
      const tg = (window as any).Telegram.WebApp;
      tg.ready();
      tg.expand(); // Разворачиваем на весь экран
      tg.enableClosingConfirmation(); // Подтверждение при закрытии
      console.log("DEBUG: Telegram WebApp initialized and expanded");
    }
  }, []);

  return (
    <Router>
      <Routes>
        <Route path="/" element={isAuthenticated ? <Navigate to="/app" /> : <Landing />} />
        <Route path="/login" element={<Auth onLogin={() => setIsAuthenticated(true)} />} />
        <Route 
          path="/app" 
          element={isAuthenticated ? <ChatApp /> : <Navigate to="/login" />} 
        />
        <Route path="/adminpanel" element={<Admin />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  );
}

export default App;

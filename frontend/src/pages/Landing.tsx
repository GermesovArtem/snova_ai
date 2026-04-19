import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, Zap, Target, Palette, Cpu } from 'lucide-react';

export default function Landing() {
  const navigate = useNavigate();

  useEffect(() => {
    if (localStorage.getItem('token')) {
      navigate('/app', { replace: true });
    }
  }, [navigate]);

  return (
    <div style={{
      height: '100vh',
      width: '100vw',
      background: 'var(--bg-color)',
      color: 'var(--text-color)',
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <header style={{ 
        height: '60px', 
        background: 'var(--tg-header)', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        boxShadow: 'var(--shadow-sm)'
      }}>
        <div style={{ fontWeight: 'bold', fontSize: '18px' }}>S • NOVA AI</div>
      </header>

      <main style={{ maxWidth: '800px', margin: '0 auto', width: '100%', padding: '40px 20px' }}>
        <section style={{ textAlign: 'center', marginBottom: '60px' }}>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '20px' }}
          >
            <h1 style={{ fontSize: '48px', fontWeight: 'bold', marginBottom: '16px', lineHeight: 1.1 }}>
              Нейро-магия <br /> в твоем браузере
            </h1>
            <p style={{ fontSize: '18px', color: 'var(--text-muted)', maxWidth: '500px', margin: '0 auto' }}>
              Редактируй фото, генерируй новые миры и создавай контент за секунды. Ультимативный AI помощник теперь в вебе.
            </p>
          </motion.div>

          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => navigate('/login')}
            className="btn btn-primary"
            style={{ padding: '16px 48px', fontSize: '18px', borderRadius: '12px' }}
          >
            Начать работу <ArrowRight size={22} style={{ marginLeft: '8px' }} />
          </motion.button>
        </section>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
          <FeatureCard 
            icon={<Sparkles size={24} color="var(--tg-accent)" />}
            title="Фото → Фото"
            desc="Меняй объекты, стиль и детали на своих снимках с помощью нейросетей."
          />
          <FeatureCard 
            icon={<Palette size={24} color="var(--tg-accent)" />}
            title="Текст → Фото"
            desc="Воплощай любые идеи в высочайшем 4K качестве за считанные секунды."
          />
          <FeatureCard 
            icon={<Zap size={24} color="var(--tg-accent)" />}
            title="Fast Engine"
            desc="Мгновенная обработка на лучших видеокартах мира без очередей."
          />
          <FeatureCard 
            icon={<Cpu size={24} color="var(--tg-accent)" />}
            title="Precise Control"
            desc="Настраивай размеры, качество и формат вывода под свои задачи."
          />
        </div>
      </main>

      <footer style={{ marginTop: 'auto', padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px', borderTop: '1px solid var(--glass-border)' }}>
        © 2024 S • NOVA AI. Все права защищены.
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, desc }: any) {
  return (
    <div style={{ 
      background: 'var(--tg-header)', 
      padding: '24px', 
      borderRadius: '16px', 
      border: '1px solid var(--glass-border)',
      boxShadow: 'var(--shadow-sm)'
    }}>
      <div style={{ marginBottom: '16px' }}>{icon}</div>
      <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '8px' }}>{title}</h3>
      <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: 1.5 }}>{desc}</p>
    </div>
  );
}

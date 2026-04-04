import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, Zap, Target, Palette } from 'lucide-react';

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="landing-container" style={{
      height: '100vh',
      width: '100vw',
      background: 'radial-gradient(circle at top right, #1a1a1a, #000)',
      overflowY: 'auto',
      padding: '20px'
    }}>
      <header style={{ padding: '20px 0', display: 'flex', justifyContent: 'center' }}>
        <motion.div 
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-1px' }}
        >
          S•NOVA <span style={{ color: 'var(--accent-soft)' }}>AI</span>
        </motion.div>
      </header>

      <main style={{ maxWidth: '600px', margin: '40px auto', textAlign: 'center' }}>
        <motion.h1 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          style={{ fontSize: '42px', fontWeight: 700, marginBottom: '20px', lineHeight: 1.1 }}
        >
          Нейро-магия в твоем кармане
        </motion.h1>

        <motion.p 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          style={{ color: 'var(--accent-soft)', fontSize: '18px', marginBottom: '40px', padding: '0 20px' }}
        >
          Редактируй фото, генерируй новые миры и создавай контент за секунды. Ультимативный AI помощник теперь в вебе.
        </motion.p>

        <motion.div 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3 }}
          style={{ display: 'flex', justifyContent: 'center', gap: '12px', marginBottom: '60px' }}
        >
          <button className="btn btn-primary" onClick={() => navigate('/login')}>
            Войти <ArrowRight size={20} />
          </button>
        </motion.div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', textAlign: 'left' }}>
          <FeatureCard 
            icon={<Sparkles size={24} />} 
            title="Фото → Фото" 
            desc="Меняй объекты, стиль и детали на своих снимках."
            delay={0.4}
          />
          <FeatureCard 
            icon={<Palette size={24} />} 
            title="Текст → Фото" 
            desc="Воплощай любые идеи в высочайшем 4K качестве."
            delay={0.5}
          />
          <FeatureCard 
            icon={<Zap size={24} />} 
            title="Fast Engine" 
            desc="Мгновенная обработка на лучших видеокартах мира."
            delay={0.6}
          />
          <FeatureCard 
            icon={<Target size={24} />} 
            title="Precise Control" 
            desc="Настраивай размеры, качество и формат вывода."
            delay={0.7}
          />
        </div>
      </main>

      <footer style={{ marginTop: '80px', textAlign: 'center', color: 'rgba(255,255,255,0.3)', fontSize: '12px', paddingBottom: '40px' }}>
        © 2024 S•NOVA AI Project. <br /> All rights reserved.
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, desc, delay }: any) {
  return (
    <motion.div 
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay }}
      className="glass" 
      style={{ padding: '20px', borderRadius: '24px' }}
    >
      <div style={{ marginBottom: '12px' }}>{icon}</div>
      <div style={{ fontWeight: 600, fontSize: '16px', marginBottom: '4px' }}>{title}</div>
      <div style={{ fontSize: '13px', color: 'var(--accent-soft)', lineHeight: 1.4 }}>{desc}</div>
    </motion.div>
  );
}

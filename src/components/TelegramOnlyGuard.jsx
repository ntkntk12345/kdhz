import React from 'react';
import { ShieldAlert, Send, Lock } from 'lucide-react';
import { soundFx } from '../utils/sound';

export default function TelegramOnlyGuard() {
  const handleOpenTelegram = () => {
    soundFx.playTap();
    window.location.href = 'https://t.me/trainghiemtanthu88k_bot/trainghiem88k';
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px 16px',
      background: 'var(--bg-app)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background Orbs */}
      <div className="ambient-orb-1" style={{ width: '220px', height: '220px', top: '10%' }} />
      <div className="ambient-orb-2" style={{ width: '250px', height: '250px', bottom: '10%' }} />

      <div className="crafted-hero-card" style={{ maxWidth: '420px', width: '100%', padding: '36px 24px', zIndex: 10 }}>
        
        {/* Shield Lock Icon */}
        <div style={{
          width: '64px',
          height: '64px',
          borderRadius: '50%',
          background: 'rgba(245, 158, 11, 0.15)',
          border: '1px solid var(--border-amber)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px auto',
          boxShadow: '0 0 25px rgba(245, 158, 11, 0.3)'
        }}>
          <Lock size={30} color="var(--accent-amber-light)" />
        </div>

        <span className="hero-category-tag">
          <ShieldAlert size={14} color="var(--accent-amber-light)" />
          BẢO MẬT XÁC THỰC
        </span>

        <h2 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--text-primary)', marginBottom: '12px', letterSpacing: '-0.02em' }}>
          CHỈ TRUY CẬP QUA TELEGRAM MINI APP
        </h2>

        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '28px' }}>
          Hệ thống nhận Gifcode Tân Thủ chỉ hỗ trợ mở trực tiếp từ trong ứng dụng Telegram Bot <b>@trainghiemtanthu88k_bot</b> để bảo mật tài khoản.
        </p>

        {/* Telegram Open Button */}
        <div className="watch-video-cta-container">
          <div className="watch-video-pulse-ring" />
          <button 
            className="btn-hero-watch-video"
            onClick={handleOpenTelegram}
          >
            <Send size={20} color="#000" />
            <span>MỞ TRONG TELEGRAM (@trainghiemtanthu88k_bot)</span>
          </button>
        </div>

      </div>
    </div>
  );
}

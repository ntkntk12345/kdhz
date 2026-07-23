import React from 'react';
import { ShieldAlert, ExternalLink, RefreshCw, CheckCircle } from 'lucide-react';
import { soundFx } from '../utils/sound';
import { triggerHaptic } from '../utils/telegram';

export default function MembershipGate({ missingGroups = [], joinAllLink = '', onRecheck, isChecking }) {
  const handleJoinClick = () => {
    soundFx.playTap();
    triggerHaptic('medium');
    const targetUrl = joinAllLink || (missingGroups[0] ? `https://t.me/${missingGroups[0].replace('@', '')}` : 'https://t.me');
    if (window.Telegram?.WebApp?.openTelegramLink) {
      window.Telegram.WebApp.openTelegramLink(targetUrl);
    } else {
      window.open(targetUrl, '_blank');
    }
  };

  const handleRecheckClick = () => {
    soundFx.playTap();
    triggerHaptic('selection');
    onRecheck();
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      background: 'rgba(9, 9, 11, 0.96)',
      backdropFilter: 'blur(12px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div className="crafted-card" style={{
        maxWidth: '420px',
        width: '100%',
        textAlign: 'center',
        border: '1px solid rgba(245, 158, 11, 0.3)',
        boxShadow: '0 0 40px rgba(245, 158, 11, 0.15)'
      }}>
        <div style={{ display: 'inline-flex', padding: '16px', borderRadius: '50%', background: 'rgba(245, 158, 11, 0.1)', color: 'var(--accent-amber-light)', marginBottom: '16px' }}>
          <ShieldAlert size={42} />
        </div>

        <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-primary)', marginBottom: '8px' }}>
          YÊU CẦU THAM GIA KÊNH / NHÓM
        </h2>

        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '20px' }}>
          Để đảm bảo tính công bằng và nhận Gifcode 88K trải nghiệm, bạn cần tham gia đầy đủ các kênh chính thức trước khi sử dụng MiniApp.
        </p>

        {/* Missing Groups List */}
        {missingGroups.length > 0 && (
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', borderRadius: '10px', border: '1px solid var(--border-subtle)', padding: '12px', marginBottom: '20px', textAlign: 'left' }}>
            <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--accent-amber-light)', marginBottom: '8px', textTransform: 'uppercase' }}>
              Các kênh bạn chưa tham gia ({missingGroups.length}):
            </div>
            {missingGroups.map((grp, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-primary)', padding: '4px 0' }}>
                <span style={{ color: 'var(--accent-amber)' }}>•</span>
                <span style={{ fontFamily: 'monospace', fontWeight: '600' }}>{grp}</span>
              </div>
            ))}
          </div>
        )}

        {/* Big Join Button */}
        <button
          onClick={handleJoinClick}
          className="btn-hero-watch-video"
          style={{ width: '100%', marginBottom: '12px', justifyContent: 'center' }}
        >
          <ExternalLink size={20} color="#000" />
          <span>THAM GIA TẤT CẢ NHÓM NGAY</span>
        </button>

        {/* Recheck Button */}
        <button
          onClick={handleRecheckClick}
          disabled={isChecking}
          className="btn-primary-crafted"
          style={{ width: '100%', justifyContent: 'center', background: 'transparent', border: '1px solid var(--border-medium)', color: 'var(--text-primary)' }}
        >
          <RefreshCw size={18} className={isChecking ? 'spin-icon' : ''} />
          <span>{isChecking ? 'ĐANG KIỂM TRA LẠI...' : 'ĐÃ THAM GIA - KIỂM TRA LẠI'}</span>
        </button>
      </div>
    </div>
  );
}

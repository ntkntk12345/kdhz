import React, { useState, useEffect } from 'react';
import { Copy, Check, Gift, X } from 'lucide-react';
import confetti from 'canvas-confetti';

export default function ClaimSuccessModal({ claimResult, onClose }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    confetti({
      particleCount: 80,
      spread: 60,
      origin: { y: 0.6 }
    });
  }, []);

  const handleCopy = () => {
    if (claimResult?.code) {
      navigator.clipboard.writeText(claimResult.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  return (
    <div className="crafted-modal-backdrop">
      <div className="crafted-modal-content">
        
        {/* Header */}
        <div style={{ padding: '14px 18px', textAlign: 'right' }}>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {/* Content Box */}
        <div style={{ padding: '0 24px 28px 24px', textAlign: 'center' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '16px', background: 'var(--accent-amber-bg)', border: '1px solid var(--border-amber)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
            <Gift size={28} color="var(--accent-amber-light)" />
          </div>
          
          <h2 style={{ fontSize: '20px', fontWeight: '800', color: 'var(--text-primary)', marginBottom: '6px', letterSpacing: '-0.02em' }}>
            CHÚC MỪNG BẠN!
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '18px', lineHeight: '1.5' }}>
            Bạn đã mở khóa thành công 1 Gifcode may mắn thuộc mục <b>{claimResult?.categoryName || 'VIP'}</b>!
          </p>

          {/* Code Box */}
          <div className="code-result-box">
            <div style={{ fontSize: '10px', fontWeight: '600', color: 'var(--accent-amber-light)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
              MÃ GIFCODE CỦA BẠN:
            </div>
            <div className="code-font-text">
              {claimResult?.code || 'ERROR-CODE'}
            </div>
          </div>

          {/* Copy Button */}
          <button className="btn-primary-crafted" onClick={handleCopy} style={{ marginBottom: '12px' }}>
            {copied ? <Check size={16} /> : <Copy size={16} />}
            <span>{copied ? 'ĐÃ SAO CHÉP MÃ CODE!' : 'SAO CHÉP GIFCODE'}</span>
          </button>

          <p style={{ fontSize: '11px', color: 'var(--text-tertiary)', lineHeight: '1.5' }}>
            💡 Hướng dẫn: Dán mã code này vào mục Khuyến Mãi / Quà Tặng của hệ thống tương ứng để kích hoạt phần thưởng!
          </p>
        </div>

      </div>
    </div>
  );
}

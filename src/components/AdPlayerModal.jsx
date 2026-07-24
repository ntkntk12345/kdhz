import React, { useState, useEffect } from 'react';
import { Play, Sparkles, AlertCircle, X, Volume2, CheckCircle2 } from 'lucide-react';
import { soundFx } from '../utils/sound';

export default function AdPlayerModal({ category, targetDuration = 15, currentStep = 1, totalSteps = 3, onAdComplete, onClose }) {
  const [timeLeft, setTimeLeft] = useState(targetDuration);
  const [isCompleted, setIsCompleted] = useState(false);
  const [isClaiming, setIsClaiming] = useState(false);

  useEffect(() => {
    if (timeLeft <= 0) {
      setIsCompleted(true);
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft(prev => {
        soundFx.playCountdownTick();
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft]);

  const progressPercent = Math.min(100, Math.max(0, ((targetDuration - timeLeft) / targetDuration) * 100));

  const handleConfirmStep = async () => {
    setIsClaiming(true);
    await onAdComplete();
    setIsClaiming(false);
  };

  const providerLabel = `Video Quảng Cáo #${currentStep}`;

  return (
    <div className="crafted-modal-backdrop">
      <div className="crafted-modal-content">
        
        {/* Top Header */}
        <div style={{ padding: '14px 18px', background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>
            <Sparkles size={16} color="var(--accent-amber)" />
            <span>Quảng Cáo {currentStep}/{totalSteps}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: 'var(--accent-amber-bg)', border: '1px solid var(--border-amber)', color: 'var(--accent-amber-light)', padding: '2px 8px', borderRadius: 'var(--radius-full)', fontSize: '11px', fontWeight: '700' }}>
              Bước {currentStep}/{totalSteps}
            </span>
            {isCompleted && (
              <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            )}
          </div>
        </div>

        {/* Video Player Viewport */}
        <div className="video-player-viewport">
          
          {/* Timer Badge Top Right */}
          <div style={{ position: 'absolute', top: '12px', right: '12px', background: 'rgba(9, 9, 11, 0.85)', border: '1px solid var(--border-medium)', padding: '4px 10px', borderRadius: 'var(--radius-full)', fontSize: '11px', fontWeight: '600', color: 'var(--text-primary)', zIndex: 10, display: 'flex', alignItems: 'center', gap: '4px' }}>
            {!isCompleted ? (
              <>
                <Play size={11} fill="var(--accent-amber)" color="var(--accent-amber)" />
                <span>Còn lại: {timeLeft}s</span>
              </>
            ) : (
              <span style={{ color: '#22c55e', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={13} /> HOÀN THÀNH VIDEO {currentStep}/{totalSteps}!
              </span>
            )}
          </div>

          {/* Backdrop Viewport */}
          <div className="video-backdrop-art">
            <span style={{ background: 'var(--accent-amber-bg)', border: '1px solid var(--border-amber)', color: 'var(--accent-amber-light)', padding: '3px 10px', borderRadius: 'var(--radius-full)', fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '10px' }}>
              VIDEO {currentStep}/{totalSteps}
            </span>
            <h2 style={{ fontSize: '20px', fontWeight: '800', color: 'var(--text-primary)', marginBottom: '6px', letterSpacing: '-0.02em' }}>
              NHẬN GIFCODE TRẢI NGHIỆM
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '85%', margin: '0 auto', lineHeight: '1.5' }}>
              {currentStep < totalSteps 
                ? `Xem xong video này để tiến tới Video ${currentStep + 1}/${totalSteps}!`
                : `Video cuối cùng (${currentStep}/${totalSteps})! Sau video này bạn sẽ nhận ngay 1 Gifcode độc quyền!`
              }
            </p>
          </div>

          {/* Progress Track */}
          <div className="progress-track">
            <div className="progress-fill-bar" style={{ width: `${progressPercent}%` }}></div>
          </div>
        </div>

        {/* Modal Bottom Actions */}
        <div style={{ padding: '18px', textAlign: 'center' }}>
          {!isCompleted ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--accent-amber-light)' }}>
                <AlertCircle size={14} />
                <span>Vui lòng xem đủ {timeLeft}s đếm ngược</span>
              </div>
              <button className="btn-primary-crafted" disabled style={{ opacity: 0.6 }}>
                ⏳ ĐANG PHÁT VIDEO {currentStep}/{totalSteps} ({timeLeft}s)...
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button 
                className="btn-primary-crafted" 
                onClick={handleConfirmStep}
                disabled={isClaiming}
              >
                <Sparkles size={18} />
                <span>
                  {isClaiming 
                    ? 'ĐANG XÁC NHẬN...' 
                    : currentStep < totalSteps 
                      ? `XÁC NHẬN HOÀN THÀNH VIDEO ${currentStep}/${totalSteps}` 
                      : `HOÀN THÀNH VIDEO ${totalSteps}/${totalSteps} - BỐC CODE NGAY!`
                  }
                </span>
              </button>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

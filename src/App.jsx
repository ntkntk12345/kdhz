import React, { useState, useEffect } from 'react';
import { Gift, Video, History, Sparkles, Trophy, User, FileText, Crown, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import AdPlayerModal from './components/AdPlayerModal';
import ClaimSuccessModal from './components/ClaimSuccessModal';
import HistoryTab from './components/HistoryTab';
import { soundFx } from './utils/sound';
import { playRewardedAd } from './utils/adProvider';
import { initTelegramApp, triggerHaptic, setTelegramBackButton, getTelegramUser, isTelegramMiniApp } from './utils/telegram';
import TelegramOnlyGuard from './components/TelegramOnlyGuard';

export default function App() {
  // Active page: 'code' (Trang Nhận Code) | 'history' (Trang Lịch Sử)
  const [activeNav, setActiveNav] = useState('code'); 
  const [isTgApp, setIsTgApp] = useState(true);
  
  const [categories, setCategories] = useState([]);
  
  // 3-Video Step Progress (1, 2, or 3)
  const [videoStep, setVideoStep] = useState(1);
  const [isAdLoading, setIsAdLoading] = useState(false);
  
  // 24-Hour Cooldown State
  const [cooldownMs, setCooldownMs] = useState(0);

  // Modals
  const [showAdModal, setShowAdModal] = useState(false);
  const [claimResult, setClaimResult] = useState(null);

  // Telegram User context & Settings
  const [tgUser, setTgUser] = useState(null);
  const [recentClaims, setRecentClaims] = useState([]);
  const [adDuration, setAdDuration] = useState(15);
  const [rulesText, setRulesText] = useState('');

  useEffect(() => {
    // 1. Initialize Full Telegram WebApp SDK
    const tg = initTelegramApp();
    const isTg = isTelegramMiniApp();
    setIsTgApp(isTg);

    const parsedUser = getTelegramUser();
    if (parsedUser) {
      setTgUser(parsedUser);
    }

    // 2. Fetch categories, settings, recent claims
    fetchCategories();
    fetchSettings();
    fetchRecentClaims();
  }, []);

  // Sync Telegram Native BackButton when activeNav changes
  useEffect(() => {
    if (activeNav === 'history') {
      setTelegramBackButton(() => {
        setActiveNav('code');
      });
    } else {
      setTelegramBackButton(null);
    }
  }, [activeNav]);

  const userId = tgUser ? String(tgUser.id) : 'user-web';

  useEffect(() => {
    // Fetch 24h cooldown status for user
    fetchUserCooldown();
  }, [tgUser]);

  // Ticking countdown timer for 24h cooldown
  useEffect(() => {
    if (cooldownMs <= 0) return;

    const timer = setInterval(() => {
      setCooldownMs(prev => Math.max(0, prev - 1000));
    }, 1000);

    return () => clearInterval(timer);
  }, [cooldownMs]);

  const fetchCategories = async () => {
    try {
      const res = await fetch('/api/categories');
      const data = await res.json();
      if (data.success) {
        setCategories(data.categories || []);
      }
    } catch (err) {
      console.error('Error fetching categories:', err);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      if (data.success && data.settings) {
        if (data.settings.adDurationSeconds) setAdDuration(data.settings.adDurationSeconds);
        if (data.settings.rulesText) setRulesText(data.settings.rulesText);
      }
    } catch (err) {
      console.error('Error fetching settings:', err);
    }
  };

  const fetchRecentClaims = async () => {
    try {
      const res = await fetch('/api/claims');
      const data = await res.json();
      if (data.success) {
        setRecentClaims((data.claims || []).slice(0, 5));
      }
    } catch (err) {
      console.error('Error fetching recent claims:', err);
    }
  };

  const fetchUserCooldown = async () => {
    try {
      const res = await fetch(`/api/user/status?userId=${encodeURIComponent(userId)}`);
      const data = await res.json();
      if (data.success && data.cooldown) {
        if (!data.cooldown.canClaim) {
          setCooldownMs(data.cooldown.remainingMs || 0);
        } else {
          setCooldownMs(0);
        }
      }
    } catch (err) {
      console.error('Error fetching user cooldown:', err);
    }
  };

  // Primary active category
  const currentCategory = categories[0] || { id: 1, name: 'Tân Thủ', slug: 'tanthu', availableCodes: 99 };

  // User triggers watching Ad
  const handleStartWatchAd = async () => {
    soundFx.playTap();
    triggerHaptic('medium');
    if (cooldownMs > 0) {
      triggerHaptic('warning');
      alert('Tài khoản của bạn đang trong thời gian chờ 24h! Vui lòng quay lại sau.');
      return;
    }
    if (!currentCategory) return;
    if (currentCategory.availableCodes <= 0) {
      triggerHaptic('warning');
      alert(`Hiện tại kho Gifcode tạm thời đang được cập nhật! Vui lòng thử lại sau ít phút.`);
      return;
    }

    setIsAdLoading(true);
    // 1. Try real ad SDK (Adsgram / Monetag)
    const adResult = await playRewardedAd(videoStep);
    setIsAdLoading(false);

    if (adResult.success) {
      // Real ad SDK resolved successfully
      await handleAdStepComplete();
    } else {
      // Fallback to built-in video player modal
      setShowAdModal(true);
    }
  };

  // Callback when user completes video ad in modal
  const handleAdStepComplete = async () => {
    if (videoStep < 5) {
      // Completed Video 1/5, 2/5, 3/5, 4/5
      setShowAdModal(false);
      soundFx.playTap();
      triggerHaptic('light');
      setVideoStep(prev => prev + 1);
    } else {
      // Completed Video 5/5 (Final step to claim code)
      try {
        const username = tgUser ? (tgUser.first_name || tgUser.username) : 'Khách May Mắn';

        const res = await fetch('/api/ads/claim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            categoryId: currentCategory.id,
            userId,
            username
          })
        });
        const data = await res.json();

        if (data.success) {
          setShowAdModal(false);
          setVideoStep(1); // Reset step counter
          soundFx.playWinFanfare();
          triggerHaptic('success');
          setClaimResult(data);
          fetchCategories();
          fetchRecentClaims();
          fetchUserCooldown(); // Activate 24h cooldown
        } else {
          setShowAdModal(false);
          triggerHaptic('warning');
          if (data.remainingMs) {
            setCooldownMs(data.remainingMs);
          }
          alert(data.message || 'Lỗi bốc quà!');
        }
      } catch (err) {
        setShowAdModal(false);
        triggerHaptic('error');
        alert('Lỗi kết nối Server!');
      }
    }
  };

  const handleTabClick = (tab) => {
    soundFx.playTap();
    triggerHaptic('selection');
    setActiveNav(tab);
  };

  // Format milliseconds into HH:MM:SS
  const formatHHMMSS = (ms) => {
    const totalSeconds = Math.ceil(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const pad = (n) => (n < 10 ? '0' + n : n);
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  };

  const displayName = tgUser 
    ? (tgUser.username ? `@${tgUser.username}` : (tgUser.first_name || 'Thành viên Telegram'))
    : 'Thành viên Telegram';

  // Enforce Telegram Mini App Access Guard (browser restriction)
  if (!isTgApp) {
    return <TelegramOnlyGuard />;
  }

  return (
    <>
      {/* Top Announcement Marquee Bar */}
      <div className="top-announcement-bar">
        <div className="announcement-track">
          {recentClaims && recentClaims.length > 0 ? (
            recentClaims.map((claim, idx) => (
              <span key={claim.id || idx} className="announcement-item">
                <span className="highlight">
                  {claim.username?.startsWith('@') ? claim.username : (claim.username?.includes(' ') ? claim.username : `@${claim.username}`)}
                </span>{' '}
                vừa xem 5/5 video nhận Gifcode {claim.categoryName || 'Tân Thủ'}
              </span>
            ))
          ) : (
            <>
              <span className="announcement-item">
                📢 Chào mừng bạn đến với <span className="highlight">Hệ Thống Nhận Gifcode Tân Thủ</span>
              </span>
              <span className="announcement-item">
                🎬 Xem đủ <span className="highlight">5/5 video (3 Adsgram + 2 Monetag)</span> để nhận ngay 1 Gifcode
              </span>
              <span className="announcement-item">
                ⏳ Giới hạn: <span className="highlight">1 lượt nhận / 24h</span> mỗi tài khoản Telegram
              </span>
            </>
          )}
          <span className="announcement-item">
            Quy định: Xem đủ 5 Video (3 Adsgram + 2 Monetag) để nhận 1 Code (1 Ngày nhận 1 lần)
          </span>
        </div>
      </div>

      {/* Header Bar */}
      <header className="site-header">
        <div className="brand-identity">
          <div className="brand-logo-mark">
            <Crown size={20} />
          </div>
          <div className="brand-title-group">
            <h1>TÂN THỦ GIFCODE</h1>
            <p>Hệ thống nhận quà trải nghiệm</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className="user-badge-pill">
            <User size={13} />
            <span>{displayName}</span>
          </div>
        </div>
      </header>

      {/* Main View Body */}
      {activeNav === 'history' ? (
        <HistoryTab userId={userId} />
      ) : (
        /* TRANG NHẬN CODE */
        <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', paddingBottom: '90px' }}>
          
          {/* Animated Hero Card with Watch Video CTA */}
          <div className="crafted-hero-card">
            {/* Background Ambient Orbs */}
            <div className="ambient-orb-1" />
            <div className="ambient-orb-2" />

            <span className="hero-category-tag">
              <Sparkles size={14} color="var(--accent-amber-light)" />
              Sự Kiện Tri Ân Thành Viên
            </span>

            <h2 className="hero-display-title">NHẬN GIFCODE TRẢI NGHIỆM</h2>
            
            <p className="hero-description-text">
              Xem đủ 5 video quảng cáo (3 Adsgram + 2 Monetag) để bốc ngay 1 Gifcode độc quyền! (Giới hạn 1 lượt / 24h).
            </p>

            {/* 5-Video Step Progress Tracker */}
            {cooldownMs <= 0 && (
              <div className="video-step-progress-wrapper">
                <div className="step-tracker-header">
                  <span>TIẾN TRÌNH XEM VIDEO</span>
                  <span>BƯỚC {videoStep}/5</span>
                </div>
                <div className="step-dots-row">
                  <div className={`step-dot-item ${videoStep > 1 ? 'completed' : videoStep === 1 ? 'active' : ''}`} />
                  <div className={`step-dot-item ${videoStep > 2 ? 'completed' : videoStep === 2 ? 'active' : ''}`} />
                  <div className={`step-dot-item ${videoStep > 3 ? 'completed' : videoStep === 3 ? 'active' : ''}`} />
                  <div className={`step-dot-item ${videoStep > 4 ? 'completed' : videoStep === 4 ? 'active' : ''}`} />
                  <div className={`step-dot-item ${videoStep === 5 ? 'active' : ''}`} />
                </div>
              </div>
            )}

            {/* Prominent Action / Cooldown View */}
            {cooldownMs > 0 ? (
              <div className="cooldown-active-card">
                <Clock size={28} color="var(--accent-amber-light)" style={{ marginBottom: '8px' }} />
                <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '6px' }}>
                  ĐÃ NHẬN GIFCODE HÔM NAY
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5', maxWidth: '85%', margin: '0 auto' }}>
                  Mỗi tài khoản chỉ được nhận 1 code mỗi 24h. Lượt xem video tiếp theo sẽ mở sau:
                </p>
                <div className="countdown-timer-display">
                  {formatHHMMSS(cooldownMs)}
                </div>
              </div>
            ) : (
              <div className="watch-video-cta-container">
                <div className="watch-video-pulse-ring" />
                <button 
                  className="btn-hero-watch-video" 
                  onClick={handleStartWatchAd}
                >
                  <Video size={22} color="#000" />
                  <span>
                    {videoStep === 1 && 'XEM VIDEO 1/5 (Adsgram)'}
                    {videoStep === 2 && 'XEM VIDEO 2/5 (Adsgram)'}
                    {videoStep === 3 && 'XEM VIDEO 3/5 (Adsgram)'}
                    {videoStep === 4 && 'XEM VIDEO 4/5 (Monetag Pop)'}
                    {videoStep === 5 && 'XEM VIDEO 5/5 (Monetag - BỐC CODE)'}
                  </span>
                </button>
              </div>
            )}

            {/* Live System Status Tag */}
            <div style={{ marginTop: '18px', display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <span className="live-pulse-dot" />
              <span>
                {cooldownMs > 0 ? 'Đang trong thời gian chờ 24h' : `Đang ở lượt xem ${videoStep}/5`}
              </span>
            </div>
          </div>

          {/* Rules Card */}
          {rulesText && (
            <div className="crafted-card">
              <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--accent-amber-light)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <FileText size={16} />
                <span>QUY ĐỊNH & THỂ LỆ NHẬN CODE</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.6', whiteSpace: 'pre-line' }}>
                {`1. Cần xem đủ 5 video (3 Adsgram + 2 Monetag) để nhận 1 Gifcode.\n2. Mỗi tài khoản chỉ được nhận 1 Gifcode trong vòng 24 giờ.\n3. Thời gian đếm ngược 24h bắt đầu ngay sau khi nhận code thành công.\n\n${rulesText}`}
              </div>
            </div>
          )}

          {/* Recent Claims Feed */}
          <div className="crafted-card">
            <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Trophy size={16} color="var(--accent-amber)" />
              <span>NHẬN CODE GẦN ĐÂY</span>
            </div>

            {recentClaims.length === 0 ? (
              <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', textAlign: 'center', padding: '12px' }}>
                Chưa có lượt nhận code gần đây. Bấm XEM VIDEO phía trên để nhận ngay!
              </div>
            ) : (
              recentClaims.map((claim, i) => {
                const formattedUser = claim.username?.startsWith('@')
                  ? claim.username
                  : (claim.username?.includes(' ') ? claim.username : `@${claim.username}`);
                return (
                  <div key={claim.id || i} className="feed-row-item">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div className="feed-avatar">
                        {formattedUser.replace('@', '')[0]?.toUpperCase() || 'T'}
                      </div>
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-primary)' }}>
                          {formattedUser}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                          Đã xem đủ 5/5 video & nhận quà
                        </div>
                      </div>
                    </div>

                    <div className="feed-code-tag">
                      {claim.code ? (claim.code.substring(0, 6) + '***') : 'VIPCODE***'}
                    </div>
                  </div>
                );
              })
            )}
          </div>

        </div>
      )}

      {/* Crafted Bottom Navigation Dock: STRICTLY 2 TABS */}
      <nav className="crafted-bottom-dock">
        
        {/* Tab 1: NHẬN CODE */}
        <button
          className={`dock-item-button ${activeNav === 'code' ? 'active' : ''}`}
          onClick={() => handleTabClick('code')}
        >
          <Gift size={20} />
          <span>Nhận Code</span>
          {activeNav === 'code' && <div className="dock-active-dot" />}
        </button>

        {/* Tab 2: LỊCH SỬ */}
        <button
          className={`dock-item-button ${activeNav === 'history' ? 'active' : ''}`}
          onClick={() => handleTabClick('history')}
        >
          <History size={20} />
          <span>Lịch Sử</span>
          {activeNav === 'history' && <div className="dock-active-dot" />}
        </button>

      </nav>

      {/* Ad Player Modal */}
      {showAdModal && (
        <AdPlayerModal 
          category={currentCategory}
          targetDuration={adDuration}
          currentStep={videoStep}
          totalSteps={5}
          onAdComplete={handleAdStepComplete}
          onClose={() => setShowAdModal(false)}
        />
      )}

      {/* Claim Success Modal */}
      {claimResult && (
        <ClaimSuccessModal 
          claimResult={claimResult}
          onClose={() => setClaimResult(null)}
        />
      )}
    </>
  );
}

import React, { useState, useEffect } from 'react';
import { Gift, Video, History, Sparkles, Trophy, User, FileText, Crown, Clock, CheckCircle2, AlertTriangle, Users, Copy, Check } from 'lucide-react';
import AdPlayerModal from './components/AdPlayerModal';
import ClaimSuccessModal from './components/ClaimSuccessModal';
import HistoryTab from './components/HistoryTab';
import MembershipGate from './components/MembershipGate';
import { soundFx } from './utils/sound';
import { playRewardedAd } from './utils/adProvider';
import { initTelegramApp, triggerHaptic, setTelegramBackButton, getTelegramUser, isTelegramMiniApp } from './utils/telegram';
import TelegramOnlyGuard from './components/TelegramOnlyGuard';
import { getBrowserFingerprint } from './utils/fingerprint';

export default function App() {
  // Active page: 'code' (Trang Nhận Code) | 'history' (Trang Lịch Sử)
  const [activeNav, setActiveNav] = useState('code'); 
  const [isTgApp, setIsTgApp] = useState(true);
  
  const [categories, setCategories] = useState([]);
  
  // 5-Video Step Progress (1..5)
  const [videoStep, setVideoStep] = useState(1);
  const [isAdLoading, setIsAdLoading] = useState(false);
  
  // 24-Hour Cooldown State
  const [cooldownMs, setCooldownMs] = useState(0);

  // 15s Inter-Ad Rest Cooldown (between each video)
  const [interAdCooldown, setInterAdCooldown] = useState(0);

  // Membership Gate State
  const [membershipAllowed, setMembershipAllowed] = useState(true);
  const [missingGroups, setMissingGroups] = useState([]);
  const [joinAllLink, setJoinAllLink] = useState('');
  const [isCheckingMembership, setIsCheckingMembership] = useState(false);

  // Referral Stats
  const [refStats, setRefStats] = useState({ total: 0, completed: 0, pending: 0, rewardsEarned: 0, rewardCount: 3 });
  const [copiedRefLink, setCopiedRefLink] = useState(false);

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

  const userId = tgUser ? String(tgUser.id) : 'user-web';

  useEffect(() => {
    // Fetch 24h cooldown status, membership check & referral stats
    if (userId) {
      fetchUserCooldown();
      checkMembership();
      fetchReferralStats();
    }
  }, [tgUser]);

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

  // Ticking countdown timer for 24h cooldown
  useEffect(() => {
    if (cooldownMs <= 0) return;

    const timer = setInterval(() => {
      setCooldownMs(prev => Math.max(0, prev - 1000));
    }, 1000);

    return () => clearInterval(timer);
  }, [cooldownMs]);

  // Ticking countdown timer for 15s inter-ad cooldown
  useEffect(() => {
    if (interAdCooldown <= 0) return;

    const timer = setInterval(() => {
      setInterAdCooldown(prev => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [interAdCooldown]);

  const checkMembership = async () => {
    setIsCheckingMembership(true);
    try {
      const res = await fetch(`/api/user/membership?userId=${encodeURIComponent(userId)}`);
      const data = await res.json();
      if (data.success) {
        setMembershipAllowed(data.allowed);
        setMissingGroups(data.missingGroups || []);
        if (data.joinAllLink) setJoinAllLink(data.joinAllLink);
      }
    } catch (err) {
      console.error('Error checking membership:', err);
    } finally {
      setIsCheckingMembership(false);
    }
  };

  const fetchReferralStats = async () => {
    try {
      const res = await fetch(`/api/user/referral?userId=${encodeURIComponent(userId)}`);
      const data = await res.json();
      if (data.success) {
        setRefStats(data);
      }
    } catch (err) {
      console.error('Error fetching referral stats:', err);
    }
  };

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
        if (data.settings.joinAllLink) setJoinAllLink(data.settings.joinAllLink);
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
    if (interAdCooldown > 0) {
      triggerHaptic('warning');
      alert(`Vui lòng nghỉ ${interAdCooldown}s trước khi xem video tiếp theo!`);
      return;
    }
    if (!currentCategory) return;
    if (currentCategory.availableCodes <= 0) {
      triggerHaptic('warning');
      alert(`Hiện tại kho Gifcode tạm thời đang được cập nhật! Vui lòng thử lại sau ít phút.`);
      return;
    }

    setIsAdLoading(true);

    // 0. IP & Fingerprint Security Check
    try {
      const fp = getBrowserFingerprint();
      const viewRes = await fetch('/api/ads/view', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, step: videoStep, fingerprint: fp })
      });
      const viewData = await viewRes.json();
      if (viewData.blocked) {
        setIsAdLoading(false);
        triggerHaptic('warning');
        alert(viewData.message || 'Phát hiện sử dụng nhiều tài khoản trên 1 thiết bị/IP!');
        return;
      }
    } catch (e) {
      console.warn('IP/Fingerprint check note:', e);
    }

    // 1. Try real ad SDK (Adsgram / Monetag)
    const adResult = await playRewardedAd(videoStep, userId);
    setIsAdLoading(false);

    if (adResult.success) {
      // Real ad SDK resolved successfully
      await handleAdStepComplete();
    } else {
      // If Adsgram was skipped or closed early by the user
      if (adResult.provider === 'adsgram' && adResult.error && adResult.error !== 'SDK_NOT_LOADED') {
        triggerHaptic('warning');
        alert('Vui lòng xem hết quảng cáo Adsgram để nhận tính điểm và bốc Gifcode!');
        return;
      }
      // Fallback to built-in video player modal if SDK not active/available in environment
      setShowAdModal(true);
    }
  };

  // Callback when user completes video ad in modal
  const handleAdStepComplete = async () => {
    // Record video step completion on server for referral tracking & security
    try {
      const fp = getBrowserFingerprint();
      await fetch('/api/ads/view', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, step: videoStep, fingerprint: fp })
      });
      fetchReferralStats();
    } catch (e) {
      console.warn('Error recording ad step completion:', e);
    }

    if (videoStep < 5) {
      // Completed Video 1/5, 2/5, 3/5, 4/5 → start 15s inter-ad rest
      setShowAdModal(false);
      soundFx.playTap();
      triggerHaptic('light');
      setInterAdCooldown(15); // 15s rest before next video
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

  const handleCopyRefLink = () => {
    soundFx.playTap();
    triggerHaptic('light');
    const refLink = `https://t.me/Gg88gk88_bot?start=ref_${userId}`;
    navigator.clipboard.writeText(refLink);
    setCopiedRefLink(true);
    setTimeout(() => setCopiedRefLink(false), 2500);
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
                vừa nhận Gifcode thành công 🎁
              </span>
            ))
          ) : (
            <>
              <span className="announcement-item">
                📢 Chào mừng bạn đến với <span className="highlight">Hệ Thống Nhận Gifcode Tân Thủ</span>
              </span>
              <span className="announcement-item">
                🎬 Xem đủ <span className="highlight">5/5 video</span> để nhận ngay 1 Gifcode
              </span>
              <span className="announcement-item">
                ⏳ Giới hạn: <span className="highlight">1 lượt nhận / 24h</span> mỗi tài khoản Telegram
              </span>
            </>
          )}
          <span className="announcement-item">
            Quy định: Xem đủ 5 Video quảng cáo để nhận 1 Code (1 Ngày nhận 1 lần)
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
              Xem đủ 5 video quảng cáo để bốc ngay 1 Gifcode độc quyền! (Giới hạn 1 lượt / 24h).
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
            ) : interAdCooldown > 0 ? (
              /* 15s Inter-Ad Rest Cooldown UI */
              <div className="cooldown-active-card" style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.25)' }}>
                <div style={{ fontSize: '36px', marginBottom: '4px' }}>⏳</div>
                <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--accent-amber-light)', marginBottom: '6px' }}>
                  NGHỈ NGƠI TRƯỚC VIDEO {videoStep}/5
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5', maxWidth: '85%', margin: '0 auto 10px' }}>
                  Video {videoStep - 1}/5 xem xong! Chờ {interAdCooldown}s để xem tiếp video {videoStep}/5.
                </p>
                <div className="countdown-timer-display" style={{ fontSize: '28px' }}>
                  {String(interAdCooldown).padStart(2, '0')}s
                </div>
              </div>
            ) : (
              <div className="watch-video-cta-container">
                <div className="watch-video-pulse-ring" />
                <button 
                  className="btn-hero-watch-video" 
                  onClick={handleStartWatchAd}
                  disabled={isAdLoading}
                >
                  <Video size={22} color="#000" />
                  <span>
                    {isAdLoading && 'Đang tải quảng cáo...'}
                    {!isAdLoading && `XEM VIDEO ${videoStep}/5`}
                  </span>
                </button>
              </div>
            )}

            {/* Live System Status Tag */}
            <div style={{ marginTop: '18px', display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <span className="live-pulse-dot" />
              <span>
                {cooldownMs > 0
                  ? 'Đang trong thời gian chờ 24h'
                  : interAdCooldown > 0
                  ? `Nghỉ ${interAdCooldown}s trước video ${videoStep}/5`
                  : `Đang ở lượt xem ${videoStep}/5`}
              </span>
            </div>
          </div>

          {/* Referral Card */}
          <div className="crafted-card">
            <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--accent-amber-light)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <Users size={16} />
              <span>MỜI BẠN BÈ - NHẬN THÊM GIFCODE</span>
            </div>

            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '12px' }}>
              Mời <b>3 người bạn</b> tham gia & xem đủ video → Nhận ngay 1 Gifcode thưởng (không tốn lượt 24h)!
            </p>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <div style={{ flex: 1, background: 'var(--bg-app)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '8px 12px', fontSize: '11px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>
                https://t.me/Gg88gk88_bot?start=ref_{userId}
              </div>
              <button
                onClick={handleCopyRefLink}
                className="btn-primary-crafted"
                style={{ padding: '8px 14px', fontSize: '12px', whiteSpace: 'nowrap' }}
              >
                {copiedRefLink ? <Check size={14} /> : <Copy size={14} />}
                <span>{copiedRefLink ? 'Đã chép' : 'Sao chép'}</span>
              </button>
            </div>

            {/* Progress bar for referrals */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '6px' }}>
              <span>Đã hoàn thành: <b>{refStats.completed}</b> / {refStats.rewardCount} người</span>
              <span>Đã thưởng: <b>{refStats.rewardsEarned}</b> code</span>
            </div>
            <div className="progress-track" style={{ height: '6px' }}>
              <div className="progress-fill-bar" style={{ width: `${Math.min(100, (refStats.completed % refStats.rewardCount) / refStats.rewardCount * 100)}%` }} />
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
                {`1. Cần xem đủ 5 video quảng cáo để nhận 1 Gifcode.\n2. Mỗi tài khoản chỉ được nhận 1 Gifcode trong vòng 24 giờ.\n3. Thời gian đếm ngược 24h bắt đầu ngay sau khi nhận code thành công.\n\n${rulesText}`}
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
                          Đã nhận Gifcode thành công 🎁
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

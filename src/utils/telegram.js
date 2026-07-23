/**
 * Telegram WebApp Integration Utilities
 */

export const getTg = () => {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    return window.Telegram.WebApp;
  }
  return null;
};

/**
 * Initialize Telegram WebApp environment
 */
export const initTelegramApp = () => {
  const tg = getTg();
  if (!tg) return null;

  try {
    tg.ready();
    tg.expand();
    
    // Enable confirmation before closing miniapp
    if (typeof tg.enableClosingConfirmation === 'function') {
      tg.enableClosingConfirmation();
    }

    // Set Theme colors to match dark mode UI
    if (typeof tg.setHeaderColor === 'function') {
      tg.setHeaderColor('#09090b');
    }
    if (typeof tg.setBackgroundColor === 'function') {
      tg.setBackgroundColor('#09090b');
    }
  } catch (err) {
    console.warn('Error initializing Telegram WebApp SDK:', err);
  }

  return tg;
};

/**
 * Trigger native Telegram Haptic Vibrations
 * @param {'light'|'medium'|'heavy'|'rigid'|'soft'|'success'|'warning'|'error'|'selection'} type 
 */
export const triggerHaptic = (type = 'light') => {
  const tg = getTg();
  if (!tg || !tg.HapticFeedback) return;

  try {
    if (['success', 'warning', 'error'].includes(type)) {
      tg.HapticFeedback.notificationOccurred(type);
    } else if (type === 'selection') {
      tg.HapticFeedback.selectionChanged();
    } else {
      tg.HapticFeedback.impactOccurred(type);
    }
  } catch (err) {
    // Ignore haptic errors if unsupported
  }
};

let currentBackCallback = null;

/**
 * Manage Telegram Native BackButton API
 */
export const setTelegramBackButton = (onBackClick = null) => {
  const tg = getTg();
  if (!tg || !tg.BackButton) return;

  try {
    if (currentBackCallback) {
      tg.BackButton.offClick(currentBackCallback);
      currentBackCallback = null;
    }

    if (onBackClick) {
      currentBackCallback = () => {
        triggerHaptic('light');
        onBackClick();
      };
      tg.BackButton.onClick(currentBackCallback);
      tg.BackButton.show();
    } else {
      tg.BackButton.hide();
    }
  } catch (err) {
    console.warn('Error setting Telegram BackButton:', err);
  }
};

/**
 * Get Telegram User Profile
 */
export const getTelegramUser = () => {
  const tg = getTg();
  if (!tg || !tg.initDataUnsafe?.user) return null;
  return tg.initDataUnsafe.user;
};

/**
 * Check if app is running inside actual Telegram MiniApp environment
 */
export const isTelegramMiniApp = () => {
  const tg = getTg();
  if (!tg) return false;
  
  // Telegram WebApp provides initData or platform when launched from Telegram client
  const hasInitData = Boolean(tg.initData && tg.initData.trim().length > 0);
  const hasPlatform = Boolean(tg.platform && tg.platform !== 'unknown');
  
  return hasInitData || hasPlatform;
};

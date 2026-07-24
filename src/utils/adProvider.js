/**
 * Ad Provider Utility for Adsgram & Monetag Rewarded Ads (5-Video Sequence)
 * Step 1: Adsgram blockId "39426"
 * Step 2: Adsgram blockId "39427"
 * Step 3: Adsgram blockId "39426"
 * Step 4: Monetag In-App Interstitial #1
 * Step 5: Monetag In-App Interstitial #2
 */

export const ADSGRAM_BLOCKS = ['39426', '39427'];

export async function playRewardedAd(stepIndex = 1, userId = null) {
  // Always prioritize real Telegram numeric user ID from WebApp SDK
  let tgUserId = null;
  if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
    tgUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
  } else if (userId && userId !== 'user-web' && userId !== 'user-anon') {
    tgUserId = String(userId);
  }

  // Steps 1, 2, 3: Adsgram Network (numeric blockId + userId)
  if (stepIndex >= 1 && stepIndex <= 3) {
    const blockId = (stepIndex === 2) ? '39427' : '39426';

    if (typeof window !== 'undefined' && window.Adsgram) {
      try {
        const initParams = {
          blockId: String(blockId),
          debug: false
        };

        // Pass Telegram User ID to Adsgram for revenue attribution
        if (tgUserId) {
          initParams.userId = String(tgUserId);
        }

        console.log(`🎬 [Adsgram] Calling window.Adsgram.init with params:`, JSON.stringify(initParams));

        const AdController = window.Adsgram.init(initParams);
        const result = await AdController.show();
        
        console.log(`✅ [Adsgram] Ad completed successfully for Step ${stepIndex}:`, result);
        return { success: true, provider: 'adsgram', blockId, stepIndex, details: result };
      } catch (err) {
        console.warn(`❌ [Adsgram] Step ${stepIndex} (${blockId}) error or skipped:`, err);
        return { 
          success: false, 
          provider: 'adsgram', 
          blockId, 
          stepIndex, 
          error: err,
          message: typeof err === 'string' ? err : (err?.description || err?.message || 'Quảng cáo bị bỏ qua hoặc lỗi tải')
        };
      }
    } else {
      console.warn('⚠️ window.Adsgram SDK not detected on window context');
      return { success: false, provider: 'adsgram', error: 'SDK_NOT_LOADED' };
    }
  }

  // Steps 4, 5: Monetag Network — Single-play inApp Interstitial
  if (stepIndex >= 4 && stepIndex <= 5) {
    if (typeof window !== 'undefined' && typeof window.show_11375549 === 'function') {
      try {
        console.log(`🎬 [Monetag] Launching inApp interstitial for Step ${stepIndex}/5...`);

        await window.show_11375549({
          type: 'inApp',
          inAppSettings: {
            frequency: 24,
            capping: 1,
            interval: 60,
            timeout: 5,
            everyPage: false
          }
        });

        console.log(`✅ [Monetag] inApp ad completed for Step ${stepIndex}`);
        return { success: true, provider: 'monetag', zone: '11375549', stepIndex };
      } catch (err) {
        console.warn(`❌ [Monetag] Step ${stepIndex} error:`, err);
        return { success: false, provider: 'monetag', error: err };
      }
    } else {
      console.warn('⚠️ window.show_11375549 Monetag SDK not detected on window object');
      return { success: false, provider: 'monetag', error: 'SDK_NOT_LOADED' };
    }
  }

  return { success: false, fallbackRequired: true };
}


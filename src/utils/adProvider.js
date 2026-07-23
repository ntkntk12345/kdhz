/**
 * Ad Provider Utility for Adsgram & Monetag Rewarded Ads (5-Video Sequence)
 * Step 1: Adsgram int-39406
 * Step 2: Adsgram int-39407
 * Step 3: Adsgram int-39406
 * Step 4: Monetag In-App Interstitial #1 (show_11375549 - inApp)
 * Step 5: Monetag In-App Interstitial #2 (show_11375549 - inApp)
 *
 * NOTE: 'pop' format is popunder/directlink and opens a new browser tab.
 * It does NOT work inside Telegram Mini App. Always use inApp format.
 */

export const ADSGRAM_BLOCKS = ['int-39406', 'int-39407'];

export async function playRewardedAd(stepIndex = 1) {
  // Steps 1, 2, 3: Adsgram Network (using int-39406 & int-39407)
  if (stepIndex >= 1 && stepIndex <= 3) {
    const blockId = (stepIndex === 2) ? 'int-39407' : 'int-39406';

    if (typeof window !== 'undefined' && window.Adsgram) {
      try {
        console.log(`🎬 [Adsgram] Launching Block ID "${blockId}" for Step ${stepIndex}/5...`);
        
        const AdController = window.Adsgram.init({ blockId, debug: false });
        const result = await AdController.show();
        
        console.log(`✅ [Adsgram] Ad completed for Step ${stepIndex}:`, result);
        return { success: true, provider: 'adsgram', blockId, stepIndex, details: result };
      } catch (err) {
        console.warn(`❌ [Adsgram] Step ${stepIndex} (${blockId}) skipped or error:`, err);
      }
    } else {
      console.warn('⚠️ window.Adsgram SDK not detected on window context');
    }
  }

  // Steps 4, 5: Monetag Network — using inApp interstitial (NOT 'pop' directlink)
  if (stepIndex >= 4 && stepIndex <= 5) {
    if (typeof window !== 'undefined' && typeof window.show_11375549 === 'function') {
      try {
        console.log(`🎬 [Monetag] Launching inApp interstitial for Step ${stepIndex}/5...`);

        // Always use inApp format — works inside Telegram Mini App
        // 'pop' format opens a new browser tab (directlink) — NOT suitable for Telegram
        await window.show_11375549({
          type: 'inApp',
          inAppSettings: {
            frequency: 1,
            capping: 0,
            interval: 0,
            timeout: 5,
            everyPage: true
          }
        });

        console.log(`✅ [Monetag] inApp ad completed for Step ${stepIndex}`);
        return { success: true, provider: 'monetag', zone: '11375549', stepIndex };
      } catch (err) {
        console.warn(`❌ [Monetag] Step ${stepIndex} error:`, err);
      }
    } else {
      console.warn('⚠️ window.show_11375549 Monetag SDK not detected on window object');
    }
  }

  // Fallback to internal video player modal if real SDK is skipped or unavailable
  return { success: false, fallbackRequired: true };
}

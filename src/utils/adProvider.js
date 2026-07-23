/**
 * Ad Provider Utility for Adsgram & Monetag Rewarded Ads (5-Video Sequence)
 * Step 1: Adsgram int-39406
 * Step 2: Adsgram int-39407
 * Step 3: Adsgram int-39406
 * Step 4: Monetag Rewarded Pop (show_11375549('pop'))
 * Step 5: Monetag In-App Interstitial (show_11375549)
 */

export const ADSGRAM_BLOCKS = ['int-39406', 'int-39407'];

export async function playRewardedAd(stepIndex = 1) {
  // Steps 1, 2, 3: Adsgram Network (using strictly int-39406 & int-39407)
  if (stepIndex >= 1 && stepIndex <= 3) {
    const blockId = (stepIndex === 2) ? 'int-39407' : 'int-39406';

    if (typeof window !== 'undefined' && window.Adsgram) {
      try {
        console.log(`🎬 [Adsgram] Launching Block ID "${blockId}" for Step ${stepIndex}/5...`);
        
        // Initialize Adsgram controller with official SDK syntax: window.Adsgram.init({ blockId })
        const AdController = window.Adsgram.init({ blockId, debug: false });
        const result = await AdController.show();
        
        console.log(`✅ [Adsgram] Ad completed for Step ${stepIndex}:`, result);
        return { success: true, provider: 'adsgram', blockId, stepIndex, details: result };
      } catch (err) {
        console.warn(`❌ [Adsgram] Step ${stepIndex} (${blockId}) skipped or error:`, err);
      }
    } else {
      console.warn('⚠️ window.Adsgram SDK script not detected on window context');
    }
  }

  // Steps 4, 5: Monetag Network
  if (stepIndex >= 4 && stepIndex <= 5) {
    if (typeof window !== 'undefined' && typeof window.show_11375549 === 'function') {
      try {
        console.log(`🎬 [Monetag] Launching Monetag Step ${stepIndex}/5...`);
        if (stepIndex === 4) {
          // Monetag Rewarded Popup
          await window.show_11375549('pop');
        } else {
          // Monetag In-App Interstitial
          await window.show_11375549({
            type: 'inApp',
            inAppSettings: {
              frequency: 2,
              capping: 0.1,
              interval: 30,
              timeout: 5,
              everyPage: false
            }
          });
        }
        console.log(`✅ [Monetag] Ad completed for Step ${stepIndex}`);
        return { success: true, provider: 'monetag', zone: '11375549', stepIndex };
      } catch (err) {
        console.warn(`❌ [Monetag] Step ${stepIndex} error:`, err);
      }
    } else {
      console.warn('⚠️ window.show_11375549 Monetag SDK function not detected on window object');
    }
  }

  // Fallback to internal video player modal if real SDK is skipped or unavailable
  return { success: false, fallbackRequired: true };
}

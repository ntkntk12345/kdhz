/**
 * Ad Provider Utility for Adsgram & Monetag Rewarded Ads (5-Video Sequence)
 * Step 1: Adsgram Block 36871
 * Step 2: Adsgram Block 39407
 * Step 3: Adsgram Block 36871
 * Step 4: Monetag Rewarded Pop (show_11375549('pop'))
 * Step 5: Monetag In-App Interstitial (show_11375549)
 */

export const ADSGRAM_BLOCKS = ['36871', '39407', '39406'];

export async function playRewardedAd(stepIndex = 1) {
  // Steps 1, 2, 3: Adsgram Network
  if (stepIndex >= 1 && stepIndex <= 3) {
    if (typeof window !== 'undefined' && window.Adsgram) {
      try {
        // Select Adsgram blockId (36871 for step 1 & 3, 39407 for step 2)
        const blockId = (stepIndex === 2) ? '39407' : '36871';
        
        // Initialize Adsgram controller with Block ID
        const AdController = window.Adsgram.init({ blockId, debug: false });
        const result = await AdController.show();
        
        return { success: true, provider: 'adsgram', blockId, stepIndex, details: result };
      } catch (err) {
        console.warn(`Adsgram Step ${stepIndex} error or skipped:`, err);
      }
    }
  }

  // Steps 4, 5: Monetag Network
  if (stepIndex >= 4 && stepIndex <= 5) {
    if (typeof window !== 'undefined' && typeof window.show_11375549 === 'function') {
      try {
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
        return { success: true, provider: 'monetag', zone: '11375549', stepIndex };
      } catch (err) {
        console.warn(`Monetag Step ${stepIndex} error:`, err);
      }
    }
  }

  // Fallback to internal video player modal if real SDK is skipped or unavailable
  return { success: false, fallbackRequired: true };
}

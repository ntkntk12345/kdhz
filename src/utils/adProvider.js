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
  // Steps 1, 2, 3: Adsgram Network
  if (stepIndex >= 1 && stepIndex <= 3) {
    if (typeof window !== 'undefined' && window.Adsgram) {
      try {
        const blockId = (stepIndex === 2) ? ADSGRAM_BLOCKS[1] : ADSGRAM_BLOCKS[0];
        const AdController = window.Adsgram.init({ blockId });
        const result = await AdController.show();
        return { success: true, provider: 'adsgram', blockId, stepIndex, details: result };
      } catch (err) {
        console.warn(`Adsgram Step ${stepIndex} error:`, err);
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

  // Fallback to simulated ad modal if real SDK fails or is uninitialized
  return { success: false, fallbackRequired: true };
}

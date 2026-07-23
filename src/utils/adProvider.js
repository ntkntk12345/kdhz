/**
 * Ad Provider Utility for Adsgram & Monetag Rewarded Ads
 */

export const ADSGRAM_BLOCKS = ['int-39406', 'int-39407'];

export async function playRewardedAd(stepIndex = 1) {
  // 1. Try Adsgram SDK if available in Telegram Mini App
  if (typeof window !== 'undefined' && window.Adsgram) {
    try {
      // Select blockId (int-39406 for step 1 & 3, int-39407 for step 2)
      const blockId = (stepIndex === 2) ? ADSGRAM_BLOCKS[1] : ADSGRAM_BLOCKS[0];
      const AdController = window.Adsgram.init({ blockId });
      
      const result = await AdController.show();
      // Adsgram resolves when ad is successfully watched till end
      return { success: true, provider: 'adsgram', blockId, details: result };
    } catch (err) {
      console.warn('Adsgram playback skipped or error:', err);
    }
  }

  // 2. Try Monetag SDK if available
  if (typeof window !== 'undefined' && typeof window.show_11375549 === 'function') {
    try {
      await window.show_11375549();
      return { success: true, provider: 'monetag', zone: '11375549' };
    } catch (err) {
      console.warn('Monetag playback error:', err);
    }
  }

  // 3. Fallback required if real SDKs are unavailable or fail
  return { success: false, fallbackRequired: true };
}

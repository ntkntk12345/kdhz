/**
 * Client-Side Pure JS Browser & Device Fingerprinting
 * Combines canvas rendering, userAgent, screen dimensions, timeZone, and language.
 */

export function getBrowserFingerprint() {
  try {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 200;
    canvas.height = 50;

    ctx.textBaseline = 'top';
    ctx.font = '14px "Arial"';
    ctx.fillStyle = '#f60';
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = '#069';
    ctx.fillText('MiniAppFingerprint#88', 2, 15);
    ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
    ctx.fillText('MiniAppFingerprint#88', 4, 17);

    const canvasDataUrl = canvas.toDataURL();
    
    const components = [
      navigator.userAgent,
      navigator.language,
      screen.colorDepth,
      `${screen.width}x${screen.height}`,
      new Date().getTimezoneOffset(),
      canvasDataUrl.slice(-50)
    ];

    const str = components.join('|||');
    
    // Simple fast DJB2 hash
    let hash = 5381;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) + hash) + str.charCodeAt(i);
      hash = hash & hash; // Convert to 32bit integer
    }

    return 'fp_' + Math.abs(hash).toString(16);
  } catch (err) {
    return 'fp_fallback_' + Math.random().toString(36).substring(2, 9);
  }
}

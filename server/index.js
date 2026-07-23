import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { db } from './db.js';
import { setupTelegramBot } from './bot.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 80;

// Enable trust proxy for Cloudflare CDN / Reverse Proxy
app.set('trust proxy', true);

app.use(cors());
app.use(express.json());

// Helper: get real client IP (respects Cloudflare headers)
function getClientIp(req) {
  return req.headers['cf-connecting-ip']
    || req.headers['x-forwarded-for']?.split(',')[0]?.trim()
    || req.socket?.remoteAddress
    || 'unknown';
}

// ─── SECURITY MIDDLEWARE ──────────────────────────────────────────────────────
app.use((req, res, next) => {
  const lowerUrl = req.url.toLowerCase();

  const isForbiddenFile =
    lowerUrl.includes('/server/') ||
    lowerUrl.endsWith('.sqlite') ||
    lowerUrl.endsWith('.sqlite3') ||
    lowerUrl.endsWith('.db') ||
    lowerUrl.endsWith('.env') ||
    lowerUrl.endsWith('.py') ||
    lowerUrl.includes('settings.json') ||
    lowerUrl.includes('data.json') ||
    lowerUrl.includes('.git');

  if (isForbiddenFile) {
    return res.status(403).json({
      error: '403 Forbidden',
      message: 'Access Denied: Direct file access and database downloads are strictly forbidden.'
    });
  }

  // Cloudflare & Telegram WebApp embedding compatible headers
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Content-Security-Policy', "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://t.me https://*.t.me;");
  res.setHeader('X-Frame-Options', 'ALLOW-FROM https://web.telegram.org');

  next();
});

// ─── ADMIN MIDDLEWARE ─────────────────────────────────────────────────────────
function requireAdminToken(req, res, next) {
  const token = req.headers['x-admin-token'] || req.query.token;
  const settings = db.getSettings();
  if (!token || token !== settings.adminPassword) {
    return res.status(401).json({ success: false, error: 'Unauthorized' });
  }
  next();
}

// ─── PUBLIC API ENDPOINTS ─────────────────────────────────────────────────────

// 1. Get Active Categories with code count summary
app.get('/api/categories', async (req, res) => {
  try {
    const categories = await db.getCategories();
    const counts = await db.getCodeCounts();

    const result = categories.map(cat => ({
      ...cat,
      availableCodes: counts[cat.id]?.available || 0,
      totalCodes: counts[cat.id]?.total || 0
    }));

    res.json({ success: true, categories: result });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 2. Claim Gifcode after watching 5 Ads
app.post('/api/ads/claim', async (req, res) => {
  try {
    const { categoryId, userId, username } = req.body;

    if (!categoryId) {
      return res.status(400).json({ success: false, message: 'Vui lòng chọn danh mục!' });
    }

    const result = await db.claimRandomCode(categoryId, userId, username);
    if (!result.success) {
      return res.status(400).json(result);
    }

    res.json(result);
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 3. Record ad view + IP & Fingerprint check (called before each video)
app.post('/api/ads/view', async (req, res) => {
  try {
    const { userId, step, fingerprint } = req.body;
    const ip = getClientIp(req);

    if (!userId) return res.status(400).json({ success: false, message: 'Missing userId' });

    // IP check
    const ipCheck = await db.checkIpLimit(ip, userId);
    if (ipCheck.blocked) {
      return res.json({
        success: false,
        blocked: true,
        reason: 'ip_limit',
        message: '⚠️ Phát hiện nhiều tài khoản sử dụng cùng 1 thiết bị/mạng! Vui lòng thử lại sau.'
      });
    }

    // Fingerprint check
    if (fingerprint) {
      const fpCheck = await db.checkFingerprint(fingerprint, userId);
      if (fpCheck.blocked) {
        return res.json({
          success: false,
          blocked: true,
          reason: 'fingerprint_duplicate',
          message: '⚠️ Phát hiện thiết bị này đã được sử dụng bởi tài khoản khác!'
        });
      }
    }

    // Record IP view
    await db.recordIpView(ip, userId, step || 1);

    res.json({ success: true, ip, step });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 4. Get User / Recent Claims
app.get('/api/claims', async (req, res) => {
  try {
    const { userId } = req.query;
    const claims = await db.getClaims(userId || null);
    res.json({ success: true, claims });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 5. Get User Cooldown Status (24-Hour Limit)
app.get('/api/user/status', async (req, res) => {
  try {
    const { userId } = req.query;
    const cooldown = await db.getUserCooldown(userId);
    res.json({ success: true, cooldown });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 6. Check Group Membership
app.get('/api/user/membership', async (req, res) => {
  try {
    const { userId } = req.query;
    const config = db.getMembershipConfig();

    if (!config.requiredGroups || config.requiredGroups.length === 0) {
      return res.json({ success: true, allowed: true, missingGroups: [] });
    }

    if (!userId) {
      return res.json({ success: true, allowed: false, missingGroups: config.requiredGroups, joinAllLink: config.joinAllLink });
    }

    const settings = db.getSettings();
    const botToken = settings.botToken;
    const missingGroups = [];

    for (const group of config.requiredGroups) {
      try {
        const resp = await fetch(`https://api.telegram.org/bot${botToken}/getChatMember?chat_id=${encodeURIComponent(group)}&user_id=${userId}`);
        const data = await resp.json();
        const status = data?.result?.status;
        if (!status || ['left', 'kicked', 'banned'].includes(status)) {
          missingGroups.push(group);
        }
      } catch {
        missingGroups.push(group); // Assume not member if API fails
      }
    }

    res.json({
      success: true,
      allowed: missingGroups.length === 0,
      missingGroups,
      joinAllLink: config.joinAllLink
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 7. Referral stats for a user
app.get('/api/user/referral', async (req, res) => {
  try {
    const { userId } = req.query;
    if (!userId) return res.status(400).json({ success: false });
    const stats = await db.getReferralStats(userId);
    res.json({ success: true, ...stats });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 8. Record referral when user joins via referral link (called by MiniApp)
app.post('/api/user/referral', async (req, res) => {
  try {
    const { referrerId, referredId, referredUsername } = req.body;
    if (!referrerId || !referredId) return res.status(400).json({ success: false });
    await db.recordReferral(referrerId, referredId, referredUsername);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 9. Get Public Settings
app.get('/api/settings', (req, res) => {
  try {
    const settings = db.getSettings();
    res.json({
      success: true,
      settings: {
        adDurationSeconds: settings.adDurationSeconds || 15,
        dailyLimitPerUser: settings.dailyLimitPerUser || 10,
        rulesText: settings.rulesText || '',
        joinAllLink: settings.joinAllLink || '',
        requiredGroups: settings.requiredGroups || []
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── ADMIN API ENDPOINTS ──────────────────────────────────────────────────────

// Admin: Login check
app.post('/api/admin/login', (req, res) => {
  const { password } = req.body;
  const settings = db.getSettings();
  if (password === settings.adminPassword) {
    res.json({ success: true, token: settings.adminPassword });
  } else {
    res.status(401).json({ success: false, message: 'Sai mật khẩu!' });
  }
});

// Admin: Get dashboard stats
app.get('/api/admin/stats', requireAdminToken, async (req, res) => {
  try {
    const stats = await db.getAdminStats();
    res.json({ success: true, ...stats });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: Get all categories
app.get('/api/admin/categories', requireAdminToken, async (req, res) => {
  try {
    const categories = await db.getAllCategories();
    const counts = await db.getCodeCounts();
    const result = categories.map(cat => ({
      ...cat,
      available: counts[cat.id]?.available || 0,
      total: counts[cat.id]?.total || 0,
      used: counts[cat.id]?.used || 0
    }));
    res.json({ success: true, categories: result });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: Add codes to a category
app.post('/api/admin/codes', requireAdminToken, async (req, res) => {
  try {
    const { categoryId, codes } = req.body;
    if (!categoryId || !codes) return res.status(400).json({ success: false });
    const codesArr = codes.split('\n').map(c => c.trim()).filter(c => c.length > 0);
    const added = await db.addCodes(categoryId, codesArr);
    res.json({ success: true, added });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: List all codes (paginated)
app.get('/api/admin/codes', requireAdminToken, async (req, res) => {
  try {
    const { categoryId } = req.query;
    const codes = await db.getCodes(categoryId || null);
    res.json({ success: true, codes });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: Delete a code
app.delete('/api/admin/codes/:id', requireAdminToken, async (req, res) => {
  try {
    await db.deleteCode(req.params.id);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: Get settings
app.get('/api/admin/settings', requireAdminToken, (req, res) => {
  const settings = db.getSettings();
  res.json({ success: true, settings });
});

// Admin: Update settings (joinAllLink, requiredGroups, etc.)
app.post('/api/admin/settings', requireAdminToken, (req, res) => {
  try {
    const updated = db.updateSettings(req.body);
    res.json({ success: true, settings: updated });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: Add category
app.post('/api/admin/categories', requireAdminToken, async (req, res) => {
  try {
    const { name, description, icon } = req.body;
    const cat = await db.addCategory(name, description, icon);
    res.json({ success: true, category: cat });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: Delete category
app.delete('/api/admin/categories/:id', requireAdminToken, async (req, res) => {
  try {
    await db.deleteCategory(req.params.id);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── SERVE ADMIN PANEL ────────────────────────────────────────────────────────
const adminPath = path.join(__dirname, '../public/admin');
app.use('/admin', express.static(adminPath));
app.get('/admin', (req, res) => {
  res.sendFile(path.join(adminPath, 'index.html'));
});

// ─── SERVE PRODUCTION SPA ─────────────────────────────────────────────────────
const distPath = path.join(__dirname, '../dist');
app.use(express.static(distPath));

app.use((req, res) => {
  res.sendFile(path.join(distPath, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ [FULL PORT 80] Server đang lắng nghe trên 0.0.0.0:${PORT} (Chấp nhận tất cả kết nối từ Cloudflare Proxy!)`);
  setupTelegramBot();
});

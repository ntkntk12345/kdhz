import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';
import { db, dbInstance } from './db.js';

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

// 1. Get Active Categories with code count summary & overall code stats
app.get('/api/categories', async (req, res) => {
  try {
    const categories = await db.getCategories();
    const counts = await db.getCodeCounts();
    const globalStats = await db.getTotalCodeStats();

    const result = categories.map(cat => ({
      ...cat,
      availableCodes: counts[cat.id]?.available || 0,
      totalCodes: counts[cat.id]?.total || 0
    }));

    res.json({
      success: true,
      categories: result,
      totalAvailable: globalStats.available,
      totalAll: globalStats.total,
      totalUsed: globalStats.used
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Helper: Send Telegram Referral Notification from server
async function sendReferralNotification(referrerId, referredUsername) {
  try {
    const settings = db.getSettings();
    const botToken = settings.botToken;
    const stats = await db.getReferralStats(referrerId);
    const completed = stats.completed;
    const rewardCount = stats.rewardCount || 3;
    const displayUser = referredUsername ? (referredUsername.startsWith('@') ? referredUsername : `@${referredUsername}`) : 'Bạn mới';

    let text = '';
    if (completed > 0 && completed % rewardCount === 0) {
      text = `🎉 <b>CHÚC MỪNG BẠN ĐÃ MỜI THÀNH CÔNG ĐỦ ${completed} BẠN!</b> 🎁\n\n` +
             `Bạn vừa mời thành công bạn <b>${displayUser}</b> xem video & bốc Gifcode thành công (Đạt mốc ${rewardCount} người)!\n\n` +
             `🎁 <b>Bạn nhận được 1 lượt Gifcode thưởng đặc biệt!</b>\n` +
             `👉 Bấm nút <b>"🎁 MỞ MINI APP NHẬN CODE 88K"</b> trên Bot để bốc thưởng ngay!`;
    } else {
      const currentInStep = completed % rewardCount;
      const remaining = rewardCount - currentInStep;
      text = `🎉 <b>Chúc mừng bạn! Người bạn ${displayUser} vừa xem đủ video & bốc Gifcode thành công!</b> ❤️\n\n` +
             `📊 Tiến trình: <b>${currentInStep}/${rewardCount}</b> người (Tổng đã bốc code: <b>${completed}</b> người).\n` +
             `🎁 Mời thêm <b>${remaining} người</b> nữa để nhận ngay 1 Gifcode thưởng!`;
    }

    await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: referrerId,
        text,
        parse_mode: 'HTML'
      })
    });
  } catch (e) {
    console.warn('Error sending referral notification from server:', e.message);
  }
}

// 2. Claim Gifcode after watching 5 Ads
app.post('/api/ads/claim', async (req, res) => {
  try {
    const { categoryId, userId, username } = req.body;
    const ip = getClientIp(req);

    const targetCatId = categoryId || 'cat-tanthu';
    const result = await db.claimRandomCode(targetCatId, userId, username, ip);
    if (!result.success) {
      return res.status(400).json(result);
    }

    // Check if user was referred & complete referral notification when code is claimed
    if (userId && userId !== 'user-anon' && userId !== 'user-web') {
      const completedRef = await db.markReferralCompleted(userId);
      if (completedRef && completedRef.referrerId) {
        sendReferralNotification(completedRef.referrerId, completedRef.referredUsername || username);
      }
    }

    res.json(result);
  } catch (err) {
    console.error('❌ [Claim Endpoint Error]:', err);
    res.status(500).json({ success: false, message: err.message || 'Lỗi xử lý server!', error: err.message });
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

// 3.1 Adsgram Webhook / Postback Endpoint for Server-to-Server reward verification
app.get('/api/adsgram/postback', async (req, res) => {
  try {
    const { userId, userid, user_id, blockId, block_id, reward } = req.query;
    const targetUserId = userId || userid || user_id;

    console.log(`📡 [Adsgram Postback Received] userId: ${targetUserId}, blockId: ${blockId || block_id}, reward: ${reward}`);

    if (targetUserId) {
      // Record ad view from Adsgram server
      await db.recordIpView('adsgram-postback', String(targetUserId), 1);
    }

    res.status(200).send('OK');
  } catch (err) {
    console.error('❌ [Adsgram Postback Error]:', err);
    res.status(500).send('ERROR');
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

// 6. Check Group Membership (Bot handles channel verification)
app.get('/api/user/membership', (req, res) => {
  res.json({
    success: true,
    allowed: true,
    missingGroups: []
  });
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

// ─── SERVE PRODUCTION SPA ─────────────────────────────────────────────────────
const distPath = path.join(__dirname, '../dist');
app.use(express.static(distPath));

app.use((req, res) => {
  res.sendFile(path.join(distPath, 'index.html'));
});

// Launch Python Telegram Bot Process
function launchPythonBot() {
  console.log('🚀 [Python Bot] Đang kết nối Telegram Bot bằng Python (bot.py)...');
  const botProcess = spawn('python', [path.join(__dirname, 'bot.py')], { stdio: 'inherit' });

  botProcess.on('exit', (code) => {
    console.warn(`⚠️ [Python Bot] Bot process stopped (code ${code}). Restarting in 3s...`);
    setTimeout(launchPythonBot, 3000);
  });
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ [FULL PORT 80] Server đang lắng nghe trên 0.0.0.0:${PORT} (Chấp nhận tất cả kết nối từ Cloudflare Proxy!)`);
  launchPythonBot();
});


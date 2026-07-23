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

// 403 FORBIDDEN SECURITY HARDENING MIDDLEWARE
// Protect backend database, environment files, and settings while serving web bundle
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

// Public API Endpoints with SQLite Async Handlers

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

// 2. Claim Gifcode after watching 3 Ads
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

// 3. Get User / Recent Claims
app.get('/api/claims', async (req, res) => {
  try {
    const { userId } = req.query;
    const claims = await db.getClaims(userId || null);
    res.json({ success: true, claims });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 4. Get User Cooldown Status (24-Hour Limit)
app.get('/api/user/status', async (req, res) => {
  try {
    const { userId } = req.query;
    const cooldown = await db.getUserCooldown(userId);
    res.json({ success: true, cooldown });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 5. Get Public Settings
app.get('/api/settings', (req, res) => {
  try {
    const settings = db.getSettings();
    res.json({
      success: true,
      settings: {
        adDurationSeconds: settings.adDurationSeconds || 15,
        dailyLimitPerUser: settings.dailyLimitPerUser || 10,
        rulesText: settings.rulesText || ''
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Serve Production SPA Web App on Port 80
const distPath = path.join(__dirname, '../dist');
app.use(express.static(distPath));

app.use((req, res) => {
  res.sendFile(path.join(distPath, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ [FULL PORT 80] Server đang lắng nghe trên 0.0.0.0:${PORT} (Chấp nhận tất cả kết nối từ Cloudflare Proxy!)`);
  setupTelegramBot();
});

import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { db } from './db.js';
import { setupTelegramBot } from './bot.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

// 403 FORBIDDEN SECURITY HARDENING MIDDLEWARE
// Strictly block any direct file downloads, source code inspection, or database access
app.use((req, res, next) => {
  const forbiddenExtensions = [
    '.sqlite', '.sqlite3', '.db', '.json', '.env', '.py', '.js', '.jsx', '.ts', '.tsx', '.log', '.git', '.config', '.lock', '.yml', '.yaml'
  ];

  const lowerUrl = req.url.toLowerCase();

  // Block direct file downloads or sensitive routes
  if (forbiddenExtensions.some(ext => lowerUrl.endsWith(ext) || lowerUrl.includes(ext + '?'))) {
    return res.status(403).json({
      error: '403 Forbidden',
      message: 'Access Denied: Direct file access and downloads are strictly forbidden.'
    });
  }

  // Anti-sniffing & Frame security headers
  res.setHeader('X-Content-Type-Options', 'nosniff');
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

// 2. Claim Gifcode after watching Ad
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

// 3b. Get User Cooldown Status
app.get('/api/user/status', async (req, res) => {
  try {
    const { userId } = req.query;
    const cooldown = await db.getUserCooldown(userId);
    res.json({ success: true, cooldown });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 4. Get Public Settings (Ad countdown time, rulesText)
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

// Admin API Endpoints
const authAdmin = (req, res, next) => {
  const token = req.headers['x-admin-password'];
  const settings = db.getSettings();
  if (!token || token !== settings.adminPassword) {
    return res.status(401).json({ success: false, message: 'Mật khẩu Admin không chính xác!' });
  }
  next();
};

app.post('/api/admin/login', (req, res) => {
  const { password } = req.body;
  const settings = db.getSettings();
  if (password === settings.adminPassword) {
    res.json({ success: true, message: 'Đăng nhập Admin thành công!' });
  } else {
    res.status(401).json({ success: false, message: 'Mật khẩu không đúng!' });
  }
});

app.post('/api/admin/categories', authAdmin, async (req, res) => {
  try {
    const { id, name, description, icon, active } = req.body;

    if (!name || name.trim() === '') {
      return res.status(400).json({ success: false, message: 'Tên danh mục không được trống!' });
    }

    if (id) {
      const updated = await db.updateCategory(id, { name, description, icon, active });
      return res.json({ success: true, message: 'Cập nhật danh mục thành công!', category: updated });
    } else {
      const created = await db.addCategory(name, description, icon);
      return res.json({ success: true, message: 'Thêm danh mục mới thành công!', category: created });
    }
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.delete('/api/admin/categories/:id', authAdmin, async (req, res) => {
  try {
    const { id } = req.params;
    await db.deleteCategory(id);
    res.json({ success: true, message: 'Đã xóa danh mục thành công!' });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get('/api/admin/codes', authAdmin, async (req, res) => {
  try {
    const { categoryId } = req.query;
    const codes = await db.getCodes(categoryId || null);
    const counts = await db.getCodeCounts();
    res.json({ success: true, codes, counts });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post('/api/admin/codes/add', authAdmin, async (req, res) => {
  try {
    const { categoryId, codesText } = req.body;

    if (!categoryId) {
      return res.status(400).json({ success: false, message: 'Vui lòng chọn danh mục!' });
    }

    if (!codesText || codesText.trim() === '') {
      return res.status(400).json({ success: false, message: 'Danh sách code không được trống!' });
    }

    const codeList = codesText
      .split(/[\n,]+/)
      .map(c => c.trim())
      .filter(c => c.length > 0);

    const addedCount = await db.addCodes(categoryId, codeList);

    res.json({
      success: true,
      message: `Đã nạp thành công ${addedCount} Gifcode mới vào hệ thống!`,
      addedCount
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.delete('/api/admin/codes/:id', authAdmin, async (req, res) => {
  try {
    const { id } = req.params;
    await db.deleteCode(id);
    res.json({ success: true, message: 'Đã xóa code!' });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Admin: Update settings (including rulesText)
app.post('/api/admin/settings', authAdmin, (req, res) => {
  try {
    const newSettings = db.updateSettings(req.body);
    res.json({ success: true, message: 'Đã cập nhật cài đặt quy định thành công!', settings: newSettings });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

const distPath = path.join(__dirname, '../dist');
app.use(express.static(distPath));

app.listen(PORT, () => {
  console.log(`✅ [Server Backend] API đang chạy tại cổng http://localhost:${PORT}`);
  setupTelegramBot();
});

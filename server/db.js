import sqlite3 from 'sqlite3';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DB_PATH = path.join(__dirname, 'database.sqlite');
const SETTINGS_FILE = path.join(__dirname, 'settings.json');

// Initialize SQLite database
const sqlite = sqlite3.verbose();
export const dbInstance = new sqlite.Database(DB_PATH, (err) => {
  if (err) {
    console.error('❌ Error opening SQLite database:', err.message);
  } else {
    console.log('✅ Connected to SQLite database: database.sqlite');
  }
});

// Helper for Promisified Queries
const dbRun = (query, params = []) => new Promise((resolve, reject) => {
  dbInstance.run(query, params, function(err) {
    if (err) reject(err);
    else resolve(this);
  });
});

const dbAll = (query, params = []) => new Promise((resolve, reject) => {
  dbInstance.all(query, params, (err, rows) => {
    if (err) reject(err);
    else resolve(rows);
  });
});

const dbGet = (query, params = []) => new Promise((resolve, reject) => {
  dbInstance.get(query, params, (err, row) => {
    if (err) reject(err);
    else resolve(row);
  });
});

// Initialize SQLite Database Tables & Default Seed Data
const initDb = async () => {
  try {
    await dbRun(`
      CREATE TABLE IF NOT EXISTS categories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        active INTEGER DEFAULT 1,
        icon TEXT DEFAULT '🎁',
        description TEXT
      )
    `);

    await dbRun(`
      CREATE TABLE IF NOT EXISTS gifcodes (
        id TEXT PRIMARY KEY,
        category_id TEXT NOT NULL,
        code TEXT NOT NULL,
        is_used INTEGER DEFAULT 0,
        used_by TEXT,
        used_at TEXT,
        created_at TEXT NOT NULL
      )
    `);

    await dbRun(`
      CREATE TABLE IF NOT EXISTS claims (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        username TEXT,
        category_id TEXT,
        category_name TEXT,
        code TEXT,
        claimed_at TEXT NOT NULL
      )
    `);

    // Referral tracking table
    await dbRun(`
      CREATE TABLE IF NOT EXISTS referrals (
        id TEXT PRIMARY KEY,
        referrer_id TEXT NOT NULL,
        referred_id TEXT NOT NULL,
        referred_username TEXT,
        completed INTEGER DEFAULT 0,
        completed_at TEXT,
        created_at TEXT NOT NULL
      )
    `);

    // IP view tracking table (anti-abuse)
    await dbRun(`
      CREATE TABLE IF NOT EXISTS ip_views (
        id TEXT PRIMARY KEY,
        ip TEXT NOT NULL,
        user_id TEXT NOT NULL,
        step INTEGER DEFAULT 1,
        viewed_at TEXT NOT NULL
      )
    `);

    // Browser fingerprint tracking table (anti-abuse)
    await dbRun(`
      CREATE TABLE IF NOT EXISTS fingerprints (
        id TEXT PRIMARY KEY,
        fingerprint TEXT NOT NULL,
        user_id TEXT NOT NULL,
        last_seen TEXT NOT NULL
      )
    `);

    // Seed default categories if empty
    const catCount = await dbGet('SELECT COUNT(*) as count FROM categories');
    if (catCount.count === 0) {
      await dbRun(`INSERT INTO categories (id, name, slug, active, icon, description) VALUES 
        ('cat-tanthu', 'Tân Thủ', 'tanthu', 1, '🔰', 'Tân Thủ GIFCODE - Code trải nghiệm độc quyền cho thành viên mới'),
        ('cat-gifcode', 'GIFCODE', 'gifcode', 1, '🎁', 'GIFCODE VIP - Thưởng Gifcode ngẫu nhiên 50K - 500K')
      `);
    }

    // Seed default gifcodes if empty
    const codeCount = await dbGet('SELECT COUNT(*) as count FROM gifcodes');
    if (codeCount.count === 0) {
      const now = new Date().toISOString();
      await dbRun(`INSERT INTO gifcodes (id, category_id, code, is_used, created_at) VALUES 
        ('code-1', 'cat-tanthu', 'TANTHU-NEWVIP-88K', 0, ?),
        ('code-2', 'cat-tanthu', 'TANTHU-START999-50K', 0, ?),
        ('code-3', 'cat-gifcode', 'GIFCODE-LUCKY777-100K', 0, ?),
        ('code-4', 'cat-gifcode', 'GIFCODE-SUPER999-200K', 0, ?)
      `, [now, now, now, now]);
    }
  } catch (err) {
    console.error('Error initializing SQLite tables:', err.message);
  }
};

initDb();

// Default Settings Reader & Writer (stored safely in JSON)
const defaultSettings = {
  botToken: '8988870338:AAH2jR6Mh60UWxXj_9F_yODIf89yqhXc3HA',
  adminPassword: 'admin123',
  miniappUrl: 'https://daovangcoin.com/',
  adDurationSeconds: 15,
  dailyLimitPerUser: 10,
  adminTelegramIds: ['5301275536'],
  requiredGroups: [],         // ['@groupusername1', '@groupusername2']
  joinAllLink: '',            // Link tham gia tất cả nhóm
  referralRewardCount: 3,     // Cần mời bao nhiêu bạn để nhận 1 code
  referralMinVideos: 3,       // Bạn bè cần xem tối thiểu bao nhiêu video
  maxIpViews: 5,              // 1 IP tối đa xem bao nhiêu lần (khác user)
  rulesText: '1. Mỗi lượt xem đủ video quảng cáo sẽ nhận ngay 1 Gifcode may mắn ngẫu nhiên.\n2. Mỗi mã Gifcode chỉ được sử dụng 1 lần cho tài khoản tương ứng.\n3. Vui lòng dán mã code vào mục Khuyến Mãi để nhận thưởng lập tức.\n4. Nghiêm cấm sử dụng công cụ gian lận, hệ thống sẽ tự động khóa tài khoản vi phạm.'
};

function readSettings() {
  try {
    if (!fs.existsSync(SETTINGS_FILE)) {
      fs.writeFileSync(SETTINGS_FILE, JSON.stringify(defaultSettings, null, 2), 'utf-8');
      return defaultSettings;
    }
    const raw = fs.readFileSync(SETTINGS_FILE, 'utf-8');
    const parsed = JSON.parse(raw);
    // Merge with defaults to ensure new keys exist
    return { ...defaultSettings, ...parsed };
  } catch (err) {
    return defaultSettings;
  }
}

function writeSettings(data) {
  try {
    fs.writeFileSync(SETTINGS_FILE, JSON.stringify(data, null, 2), 'utf-8');
  } catch (err) {
    console.error('Error writing settings file:', err);
  }
}

export const db = {
  isAdminTelegram: (telegramId) => {
    const settings = readSettings();
    const allowed = settings.adminTelegramIds || ['5301275536'];
    return allowed.map(String).includes(String(telegramId));
  },

  addAdminTelegramId: (telegramId) => {
    const settings = readSettings();
    if (!settings.adminTelegramIds) settings.adminTelegramIds = [];
    const idStr = String(telegramId);
    if (!settings.adminTelegramIds.includes(idStr)) {
      settings.adminTelegramIds.push(idStr);
      writeSettings(settings);
    }
    return settings.adminTelegramIds;
  },

  getCategories: () => {
    return new Promise((resolve) => {
      dbInstance.all('SELECT * FROM categories WHERE active = 1', [], (err, rows) => {
        if (err) resolve([]);
        else resolve(rows || []);
      });
    });
  },

  getAllCategories: () => {
    return dbAll('SELECT * FROM categories');
  },

  addCategory: async (name, description = '', icon = '🎁') => {
    const slug = name.toLowerCase().replace(/[^a-z0-9]/g, '');
    const id = `cat-${Date.now()}`;
    await dbRun(
      'INSERT INTO categories (id, name, slug, active, icon, description) VALUES (?, ?, ?, 1, ?, ?)',
      [id, name, slug, icon || '🎁', description || `Mục ${name}`]
    );
    return { id, name, slug, active: 1, icon, description };
  },

  updateCategory: async (id, updates) => {
    const fields = [];
    const params = [];
    if (updates.name) {
      fields.push('name = ?');
      params.push(updates.name);
      fields.push('slug = ?');
      params.push(updates.name.toLowerCase().replace(/[^a-z0-9]/g, ''));
    }
    if (updates.description !== undefined) {
      fields.push('description = ?');
      params.push(updates.description);
    }
    if (updates.icon !== undefined) {
      fields.push('icon = ?');
      params.push(updates.icon);
    }
    if (updates.active !== undefined) {
      fields.push('active = ?');
      params.push(updates.active ? 1 : 0);
    }
    if (fields.length === 0) return null;
    params.push(id);
    await dbRun(`UPDATE categories SET ${fields.join(', ')} WHERE id = ?`, params);
    return dbGet('SELECT * FROM categories WHERE id = ?', [id]);
  },

  deleteCategory: async (id) => {
    await dbRun('DELETE FROM categories WHERE id = ?', [id]);
    return true;
  },

  getCodes: async (categoryId = null) => {
    if (categoryId) {
      return dbAll('SELECT * FROM gifcodes WHERE category_id = ?', [categoryId]);
    }
    return dbAll('SELECT * FROM gifcodes');
  },

  getCodeCounts: async () => {
    const categories = await dbAll('SELECT * FROM categories');
    const counts = {};

    for (const cat of categories) {
      const totalRow = await dbGet('SELECT COUNT(*) as total FROM gifcodes WHERE category_id = ?', [cat.id]);
      const availRow = await dbGet('SELECT COUNT(*) as available FROM gifcodes WHERE category_id = ? AND is_used = 0', [cat.id]);
      const total = totalRow ? totalRow.total : 0;
      const available = availRow ? availRow.available : 0;
      counts[cat.id] = { available, total, used: total - available };
    }

    return counts;
  },

  addCodes: async (categoryId, codesArray) => {
    const now = new Date().toISOString();
    let count = 0;
    for (const codeStr of codesArray) {
      const clean = codeStr.trim();
      if (clean.length > 0) {
        const id = `code-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
        await dbRun(
          'INSERT INTO gifcodes (id, category_id, code, is_used, created_at) VALUES (?, ?, ?, 0, ?)',
          [id, categoryId, clean, now]
        );
        count++;
      }
    }
    return count;
  },

  addCodesBySlugOrName: async (targetSlugOrName, codesArray) => {
    const searchKey = targetSlugOrName.toLowerCase().trim();
    let category = await dbGet('SELECT * FROM categories WHERE slug = ? OR LOWER(name) = ?', [searchKey, searchKey]);

    if (!category) {
      const catName = targetSlugOrName.toUpperCase();
      const catId = `cat-${Date.now()}`;
      await dbRun('INSERT INTO categories (id, name, slug, active, icon, description) VALUES (?, ?, ?, 1, "🎰", ?)', [
        catId, catName, searchKey, `Mục ${catName}`
      ]);
      category = { id: catId, name: catName, slug: searchKey };
    }

    const addedCount = await db.addCodes(category.id, codesArray);
    const availRow = await dbGet('SELECT COUNT(*) as available FROM gifcodes WHERE category_id = ? AND is_used = 0', [category.id]);

    return {
      success: true,
      categoryName: category.name,
      addedCount,
      availableCount: availRow ? availRow.available : 0
    };
  },

  // Add codes to first active category (default)
  addCodesToDefault: async (codesArray) => {
    let category = await dbGet('SELECT * FROM categories WHERE active = 1 ORDER BY id LIMIT 1');
    if (!category) {
      category = { id: 'cat-tanthu', name: 'Tân Thủ' };
    }
    const addedCount = await db.addCodes(category.id, codesArray);
    const availRow = await dbGet('SELECT COUNT(*) as available FROM gifcodes WHERE category_id = ? AND is_used = 0', [category.id]);
    return {
      success: true,
      categoryName: category.name,
      addedCount,
      availableCount: availRow ? availRow.available : 0
    };
  },

  deleteCode: async (codeId) => {
    await dbRun('DELETE FROM gifcodes WHERE id = ?', [codeId]);
    return true;
  },

  getUserCooldown: async (userId) => {
    if (!userId) return { canClaim: true, remainingMs: 0, lastClaimedAt: null };

    const latest = await dbGet('SELECT * FROM claims WHERE user_id = ? ORDER BY claimed_at DESC LIMIT 1', [userId]);
    if (!latest) return { canClaim: true, remainingMs: 0, lastClaimedAt: null };

    const lastTime = new Date(latest.claimed_at).getTime();
    const now = Date.now();
    const cooldownMs = 24 * 60 * 60 * 1000; // 24 hours
    const elapsed = now - lastTime;

    if (elapsed < cooldownMs) {
      return {
        canClaim: false,
        remainingMs: cooldownMs - elapsed,
        lastClaimedAt: latest.claimed_at
      };
    }

    return { canClaim: true, remainingMs: 0, lastClaimedAt: latest.claimed_at };
  },

  claimRandomCode: async (categoryId, userId, username) => {
    // 1. Validate 24h cooldown
    if (userId && userId !== 'user-web') {
      const cooldown = await db.getUserCooldown(userId);
      if (!cooldown.canClaim) {
        const remainingSeconds = Math.ceil(cooldown.remainingMs / 1000);
        const hours = Math.floor(remainingSeconds / 3600);
        const minutes = Math.floor((remainingSeconds % 3600) / 60);
        const seconds = remainingSeconds % 60;
        return {
          success: false,
          message: `Mỗi tài khoản chỉ được nhận 1 Gifcode mỗi 24h! Vui lòng thử lại sau ${hours}h ${minutes}m ${seconds}s.`,
          remainingMs: cooldown.remainingMs
        };
      }
    }

    // 2. Find available unused code from SQLite
    const availableCodes = await dbAll('SELECT * FROM gifcodes WHERE category_id = ? AND is_used = 0', [categoryId]);
    if (!availableCodes || availableCodes.length === 0) {
      return { success: false, message: 'Đã hết Gifcode cho mục này! Vui lòng quay lại sau.' };
    }

    const randomIndex = Math.floor(Math.random() * availableCodes.length);
    const selected = availableCodes[randomIndex];
    const now = new Date().toISOString();

    // Mark code as used
    await dbRun('UPDATE gifcodes SET is_used = 1, used_by = ?, used_at = ? WHERE id = ?', [
      userId || 'Anonymous', now, selected.id
    ]);

    const category = await dbGet('SELECT * FROM categories WHERE id = ?', [categoryId]);
    const categoryName = category ? category.name : 'Tân Thủ';

    // Record claim in SQLite
    const claimId = `claim-${Date.now()}`;
    await dbRun(
      'INSERT INTO claims (id, user_id, username, category_id, category_name, code, claimed_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
      [claimId, userId || 'user-anon', username || 'Khách may mắn', categoryId, categoryName, selected.code, now]
    );

    // Mark referral as completed if bạn bè đủ điều kiện
    if (userId && userId !== 'user-anon' && userId !== 'user-web') {
      await db.markReferralCompleted(userId);
    }

    const newClaim = {
      id: claimId,
      userId: userId || 'user-anon',
      username: username || 'Khách may mắn',
      categoryId,
      categoryName,
      code: selected.code,
      claimedAt: now
    };

    return {
      success: true,
      code: selected.code,
      categoryName,
      claim: newClaim
    };
  },

  getClaims: async (userId = null) => {
    if (userId) {
      const rows = await dbAll('SELECT * FROM claims WHERE user_id = ? ORDER BY claimed_at DESC', [userId]);
      return rows.map(r => ({ ...r, categoryName: r.category_name, claimedAt: r.claimed_at, userId: r.user_id }));
    }
    const rows = await dbAll('SELECT * FROM claims ORDER BY claimed_at DESC LIMIT 50');
    return rows.map(r => ({ ...r, categoryName: r.category_name, claimedAt: r.claimed_at, userId: r.user_id }));
  },

  // ─── REFERRAL SYSTEM ─────────────────────────────────────────────────────────

  // Ghi nhận lượt mời khi bạn bè join qua referral link
  recordReferral: async (referrerId, referredId, referredUsername) => {
    if (String(referrerId) === String(referredId)) return null; // không tự giới thiệu chính mình

    // Check xem đã có record chưa
    const existing = await dbGet('SELECT * FROM referrals WHERE referred_id = ?', [String(referredId)]);
    if (existing) return existing; // mỗi user chỉ được mời 1 lần

    const id = `ref-${Date.now()}`;
    const now = new Date().toISOString();
    await dbRun(
      'INSERT INTO referrals (id, referrer_id, referred_id, referred_username, completed, created_at) VALUES (?, ?, ?, ?, 0, ?)',
      [id, String(referrerId), String(referredId), referredUsername || '', now]
    );
    return { id, referrerId, referredId, completed: 0 };
  },

  // Đánh dấu referral là hoàn thành khi bạn bè xem đủ video
  markReferralCompleted: async (referredId) => {
    const settings = readSettings();
    const minVideos = settings.referralMinVideos || 3;

    // Đếm số video đã xem của referred user
    const viewCount = await dbGet('SELECT COUNT(*) as cnt FROM ip_views WHERE user_id = ?', [String(referredId)]);
    const totalViews = viewCount ? viewCount.cnt : 0;

    if (totalViews >= minVideos) {
      const now = new Date().toISOString();
      await dbRun(
        'UPDATE referrals SET completed = 1, completed_at = ? WHERE referred_id = ? AND completed = 0',
        [now, String(referredId)]
      );
    }
  },

  // Lấy thống kê referral của 1 user
  getReferralStats: async (userId) => {
    const settings = readSettings();
    const rewardCount = settings.referralRewardCount || 3;

    const refs = await dbAll('SELECT * FROM referrals WHERE referrer_id = ?', [String(userId)]);
    const completed = refs.filter(r => r.completed === 1).length;
    const pending = refs.filter(r => r.completed === 0).length;
    const rewardsEarned = Math.floor(completed / rewardCount);

    return { total: refs.length, completed, pending, rewardsEarned, rewardCount };
  },

  // ─── IP TRACKING ─────────────────────────────────────────────────────────────

  // Ghi nhận 1 lượt xem video theo IP
  recordIpView: async (ip, userId, step) => {
    const id = `ipv-${Date.now()}-${Math.random().toString(36).substr(2,5)}`;
    const now = new Date().toISOString();
    await dbRun(
      'INSERT INTO ip_views (id, ip, user_id, step, viewed_at) VALUES (?, ?, ?, ?, ?)',
      [id, ip, String(userId), step || 1, now]
    );
  },

  // Kiểm tra IP có bị chặn không
  checkIpLimit: async (ip, userId) => {
    const settings = readSettings();
    const maxViews = settings.maxIpViews || 5;

    // Đếm số user KHÁC nhau đã dùng IP này
    const distinctUsers = await dbGet(
      'SELECT COUNT(DISTINCT user_id) as cnt FROM ip_views WHERE ip = ? AND user_id != ?',
      [ip, String(userId)]
    );
    const otherUsers = distinctUsers ? distinctUsers.cnt : 0;

    if (otherUsers >= maxViews) {
      return { blocked: true, reason: 'ip_limit', otherUsers };
    }
    return { blocked: false };
  },

  // ─── FINGERPRINT TRACKING ────────────────────────────────────────────────────

  // Kiểm tra fingerprint có bị chặn không
  checkFingerprint: async (fingerprint, userId) => {
    if (!fingerprint) return { blocked: false };

    const existing = await dbGet(
      'SELECT * FROM fingerprints WHERE fingerprint = ? AND user_id != ?',
      [fingerprint, String(userId)]
    );

    if (existing) {
      return { blocked: true, reason: 'fingerprint_duplicate', originalUserId: existing.user_id };
    }

    // Upsert fingerprint record
    const now = new Date().toISOString();
    const existing2 = await dbGet('SELECT * FROM fingerprints WHERE fingerprint = ? AND user_id = ?', [fingerprint, String(userId)]);
    if (existing2) {
      await dbRun('UPDATE fingerprints SET last_seen = ? WHERE fingerprint = ? AND user_id = ?', [now, fingerprint, String(userId)]);
    } else {
      const id = `fp-${Date.now()}`;
      await dbRun('INSERT INTO fingerprints (id, fingerprint, user_id, last_seen) VALUES (?, ?, ?, ?)', [id, fingerprint, String(userId), now]);
    }

    return { blocked: false };
  },

  // ─── MEMBERSHIP CHECK ────────────────────────────────────────────────────────

  // Lấy danh sách nhóm bắt buộc và link join all từ settings
  getMembershipConfig: () => {
    const settings = readSettings();
    return {
      requiredGroups: settings.requiredGroups || [],
      joinAllLink: settings.joinAllLink || ''
    };
  },

  // ─── ADMIN STATS ─────────────────────────────────────────────────────────────

  getAdminStats: async () => {
    const categories = await dbAll('SELECT * FROM categories');
    const stats = [];

    for (const cat of categories) {
      const total = await dbGet('SELECT COUNT(*) as cnt FROM gifcodes WHERE category_id = ?', [cat.id]);
      const available = await dbGet('SELECT COUNT(*) as cnt FROM gifcodes WHERE category_id = ? AND is_used = 0', [cat.id]);
      const used = await dbGet('SELECT COUNT(*) as cnt FROM gifcodes WHERE category_id = ? AND is_used = 1', [cat.id]);
      stats.push({
        id: cat.id,
        name: cat.name,
        slug: cat.slug,
        total: total ? total.cnt : 0,
        available: available ? available.cnt : 0,
        used: used ? used.cnt : 0
      });
    }

    const totalClaims = await dbGet('SELECT COUNT(*) as cnt FROM claims');
    const todayStr = new Date().toISOString().slice(0, 10);
    const todayClaims = await dbGet(`SELECT COUNT(*) as cnt FROM claims WHERE claimed_at LIKE '${todayStr}%'`);
    const totalReferrals = await dbGet('SELECT COUNT(*) as cnt FROM referrals WHERE completed = 1');

    return {
      categories: stats,
      totalClaims: totalClaims ? totalClaims.cnt : 0,
      todayClaims: todayClaims ? todayClaims.cnt : 0,
      completedReferrals: totalReferrals ? totalReferrals.cnt : 0
    };
  },

  getSettings: () => {
    return readSettings();
  },

  updateSettings: (newSettings) => {
    const current = readSettings();
    const updated = { ...current, ...newSettings };
    writeSettings(updated);
    return updated;
  }
};

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
  rulesText: '1. Mỗi lượt xem đủ video quảng cáo sẽ nhận ngay 1 Gifcode may mắn ngẫu nhiên.\n2. Mỗi mã Gifcode chỉ được sử dụng 1 lần cho tài khoản tương ứng.\n3. Vui lòng dán mã code vào mục Khuyến Mãi để nhận thưởng lập tức.\n4. Nghiêm cấm sử dụng công cụ gian lận, hệ thống sẽ tự động khóa tài khoản vi phạm.'
};

function readSettings() {
  try {
    if (!fs.existsSync(SETTINGS_FILE)) {
      fs.writeFileSync(SETTINGS_FILE, JSON.stringify(defaultSettings, null, 2), 'utf-8');
      return defaultSettings;
    }
    const raw = fs.readFileSync(SETTINGS_FILE, 'utf-8');
    return JSON.parse(raw);
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

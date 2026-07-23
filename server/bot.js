import TelegramBot from 'node-telegram-bot-api';
import { db } from './db.js';

export function setupTelegramBot() {
  const token = '8988870338:AAH2jR6Mh60UWxXj_9F_yODIf89yqhXc3HA';

  try {
    const bot = new TelegramBot(token, { polling: true });

    console.log('🚀 [Telegram Bot] Bot Telegram đã kết nối thành công với Token mới!');

    // Handle polling errors gracefully
    bot.on('polling_error', (error) => {
      if (error.code !== 'ETELEGRAM') {
        console.warn('⚠️ Telegram Bot Polling Note:', error.message || error);
      }
    });

    // Track pending /addcode sessions (chatId -> waiting state)
    const pendingAddCode = new Map();

    // ──────────────────────────────────────────────────────────────────
    // /start — Welcome + Open MiniApp + Referral tracking
    // ──────────────────────────────────────────────────────────────────
    bot.onText(/\/start(?:\s+(.+))?/, async (msg, match) => {
      const chatId = msg.chat.id;
      const userId = String(msg.from?.id);
      const firstName = msg.from?.first_name || 'Bạn';
      const username = msg.from?.username || msg.from?.first_name || 'user';
      const param = match[1] ? match[1].trim() : '';

      // Handle referral link: /start ref_USERID
      if (param.startsWith('ref_')) {
        const referrerId = param.replace('ref_', '');
        if (referrerId && referrerId !== userId) {
          await db.recordReferral(referrerId, userId, username);
          console.log(`🔗 [Referral] User ${userId} joined via referral from ${referrerId}`);
        }
      }

      const currentSettings = db.getSettings();
      const rawWebappUrl = currentSettings.miniappUrl || 'https://daovangcoin.com/';
      const joinAllLink = currentSettings.joinAllLink || '';
      const requiredGroups = currentSettings.requiredGroups || [];

      try {
        const categories = await db.getCategories();
        const activeCategories = categories.filter(c => c.active);
        const catListStr = activeCategories.map(c => `• <b>${c.name}</b>: ${c.description || 'Xem ad nhận code'}`).join('\n');

        // Build referral link for this user
        const botUsername = (await bot.getMe()).username;
        const referralLink = `https://t.me/${botUsername}?start=ref_${userId}`;

        let welcomeText = `👋 <b>Xin chào ${firstName}!</b>\n\n` +
          `🎁 <b>NHẬN CODE TRẢI NGHIỆM MIỄN PHÍ 88K</b> 🎁\n\n` +
          `Các danh mục hỗ trợ:\n${catListStr}\n\n` +
          `👥 <b>Mời bạn bè:</b> Mời 3 người bạn xem đủ video → nhận thêm 1 Code miễn phí!\n` +
          `🔗 Link mời của bạn: <code>${referralLink}</code>\n\n` +
          `👇 Nhấn nút bên dưới để mở <b>Mini App Nhận Code</b> ngay!`;

        const inlineButtons = [
          [{ text: '🎁 MỞ MINI APP NHẬN CODE', web_app: { url: rawWebappUrl } }],
          [{ text: '📋 Code đã nhận', callback_data: 'my_claims' }],
          [{ text: '👥 Thống kê mời bạn', callback_data: 'my_referrals' }]
        ];

        if (joinAllLink) {
          inlineButtons.splice(1, 0, [{ text: '📢 THAM GIA TẤT CẢ NHÓM', url: joinAllLink }]);
        }

        bot.sendMessage(chatId, welcomeText, {
          parse_mode: 'HTML',
          reply_markup: { inline_keyboard: inlineButtons }
        }).catch(err => {
          console.error('❌ Error sending /start response:', err.message);
        });
      } catch (err) {
        console.error('Error handling /start command:', err);
      }
    });

    // ──────────────────────────────────────────────────────────────────
    // /admin — Xác thực admin
    // ──────────────────────────────────────────────────────────────────
    bot.onText(/\/admin(?:\s+(.+))?/, (msg, match) => {
      const chatId = msg.chat.id;
      const senderId = msg.from?.id;
      const inputPass = match[1] ? match[1].trim() : '';

      const currentSettings = db.getSettings();
      if (inputPass === currentSettings.adminPassword || String(senderId) === '5301275536') {
        db.addAdminTelegramId(senderId);
        bot.sendMessage(chatId,
          `✅ <b>XÁC NHẬN ADMIN THÀNH CÔNG!</b>\n\n` +
          `Telegram ID <code>${senderId}</code> đã được ủy quyền.\n\n` +
          `<b>Lệnh Admin:</b>\n` +
          `• <code>/addcode</code> — Nạp gifcode vào kho\n` +
          `• <code>/thongke</code> — Thống kê kho code\n\n` +
          `🌐 <b>Admin Panel:</b> <a href="https://daovangcoin.com/admin">daovangcoin.com/admin</a>`,
          { parse_mode: 'HTML' }
        );
      } else {
        bot.sendMessage(chatId, '❌ <b>Sai mật khẩu Admin!</b>', { parse_mode: 'HTML' });
      }
    });

    // ──────────────────────────────────────────────────────────────────
    // /addcode — Nạp code qua hội thoại 2 bước
    // ──────────────────────────────────────────────────────────────────
    bot.onText(/\/addcode$/, async (msg) => {
      const chatId = msg.chat.id;
      const senderId = msg.from?.id;

      // Auto-authorize default Admin
      if (String(senderId) === '5301275536') db.addAdminTelegramId(senderId);

      if (!db.isAdminTelegram(senderId)) {
        bot.sendMessage(chatId, '⛔ <i>Lệnh này chỉ dành cho Admin! Gửi /admin <mat_khau> để mở khóa.</i>', { parse_mode: 'HTML' });
        return;
      }

      // Lấy danh sách danh mục để hiện inline keyboard
      const categories = await db.getAllCategories();
      const catButtons = categories.map(c => ([{
        text: `${c.icon || '🎁'} ${c.name} (còn lại: ?)`,
        callback_data: `addcode_cat_${c.id}`
      }]));

      // Lưu state đang chờ chọn danh mục
      pendingAddCode.set(chatId, { step: 'choose_category' });

      bot.sendMessage(chatId,
        `📦 <b>NẠP GIFCODE VÀO KHO</b>\n\nChọn danh mục bạn muốn nạp code vào:`,
        {
          parse_mode: 'HTML',
          reply_markup: { inline_keyboard: catButtons }
        }
      );
    });

    // ──────────────────────────────────────────────────────────────────
    // /thongke — Thống kê kho code
    // ──────────────────────────────────────────────────────────────────
    bot.onText(/\/thongke/, async (msg) => {
      const chatId = msg.chat.id;
      const senderId = msg.from?.id;

      if (String(senderId) === '5301275536') db.addAdminTelegramId(senderId);

      if (!db.isAdminTelegram(senderId)) {
        bot.sendMessage(chatId, '⛔ <i>Lệnh này chỉ dành cho Admin!</i>', { parse_mode: 'HTML' });
        return;
      }

      try {
        const stats = await db.getAdminStats();

        let text = `📊 <b>THỐNG KÊ KHO GIFCODE</b>\n\n`;
        for (const cat of stats.categories) {
          text += `${cat.name}:\n`;
          text += `  • Tổng: <b>${cat.total}</b> | Còn lại: <b>${cat.available}</b> | Đã phát: <b>${cat.used}</b>\n\n`;
        }
        text += `──────────────────\n`;
        text += `📋 Tổng lượt nhận code: <b>${stats.totalClaims}</b>\n`;
        text += `📅 Hôm nay: <b>${stats.todayClaims}</b> lượt\n`;
        text += `👥 Referral hoàn thành: <b>${stats.completedReferrals}</b>`;

        bot.sendMessage(chatId, text, { parse_mode: 'HTML' });
      } catch (err) {
        bot.sendMessage(chatId, `❌ Lỗi lấy thống kê: ${err.message}`);
      }
    });

    // ──────────────────────────────────────────────────────────────────
    // Message handler — Nhận code từ Admin sau khi chọn danh mục
    // ──────────────────────────────────────────────────────────────────
    bot.on('message', async (msg) => {
      if (!msg.text || msg.text.startsWith('/')) return;

      const chatId = msg.chat.id;
      const senderId = msg.from?.id;
      const text = msg.text.trim();

      const pending = pendingAddCode.get(chatId);

      // Chờ admin gửi danh sách code sau khi đã chọn danh mục
      if (pending && pending.step === 'waiting_codes' && db.isAdminTelegram(senderId)) {
        const codes = text.split('\n').map(c => c.trim()).filter(c => c.length > 0);

        if (codes.length === 0) {
          bot.sendMessage(chatId, '❌ Không tìm thấy code hợp lệ! Mỗi dòng 1 code.');
          return;
        }

        try {
          const addedCount = await db.addCodes(pending.categoryId, codes);
          const availRow = await (async () => {
            const { dbInstance } = await import('./db.js');
            return new Promise((resolve) => {
              dbInstance.get('SELECT COUNT(*) as cnt FROM gifcodes WHERE category_id = ? AND is_used = 0', [pending.categoryId], (err, row) => resolve(row || { cnt: 0 }));
            });
          })();

          pendingAddCode.delete(chatId);

          bot.sendMessage(chatId,
            `✅ <b>NẠP GIFCODE THÀNH CÔNG!</b>\n\n` +
            `📌 Danh mục: <b>${pending.categoryName}</b>\n` +
            `➕ Đã nạp: <b>${addedCount} code mới</b>\n` +
            `📦 Kho hiện tại: <b>${availRow.cnt} code khả dụng</b>`,
            { parse_mode: 'HTML' }
          );
        } catch (err) {
          pendingAddCode.delete(chatId);
          bot.sendMessage(chatId, `❌ Lỗi nạp code: ${err.message}`);
        }
      }
    });

    // ──────────────────────────────────────────────────────────────────
    // Callback query handler
    // ──────────────────────────────────────────────────────────────────
    bot.on('callback_query', async (query) => {
      const chatId = query.message.chat.id;
      const userId = String(query.from.id);
      const data = query.data;

      // Chọn danh mục để nạp code
      if (data.startsWith('addcode_cat_')) {
        if (!db.isAdminTelegram(Number(userId))) {
          bot.answerCallbackQuery(query.id, { text: '⛔ Không có quyền!' });
          return;
        }

        const catId = data.replace('addcode_cat_', '');
        const categories = await db.getAllCategories();
        const cat = categories.find(c => c.id === catId);

        if (!cat) {
          bot.answerCallbackQuery(query.id, { text: '❌ Không tìm thấy danh mục!' });
          return;
        }

        // Lưu state chờ nhận code
        pendingAddCode.set(chatId, {
          step: 'waiting_codes',
          categoryId: catId,
          categoryName: cat.name
        });

        bot.answerCallbackQuery(query.id);
        bot.sendMessage(chatId,
          `✅ Đã chọn danh mục: <b>${cat.name}</b>\n\n` +
          `📝 Bây giờ hãy gửi danh sách code, <b>mỗi dòng 1 code</b>:\n\n` +
          `<i>Ví dụ:\nCODE001\nCODE002\nCODE003</i>`,
          { parse_mode: 'HTML' }
        );
        return;
      }

      // Xem code đã nhận
      if (data === 'my_claims') {
        try {
          const claims = await db.getClaims(userId);
          if (!claims || claims.length === 0) {
            bot.answerCallbackQuery(query.id, { text: 'Bạn chưa nhận code nào. Hãy mở MiniApp xem ad nhận code ngay!' });
          } else {
            let text = `🎁 <b>DANH SÁCH CODE BẠN ĐÃ NHẬN:</b>\n\n`;
            claims.slice(0, 10).forEach((c, idx) => {
              text += `${idx + 1}. <b>${c.categoryName || 'Tân Thủ'}</b>: <code>${c.code}</code>\n   🕒 ${new Date(c.claimedAt || c.claimed_at).toLocaleString('vi-VN')}\n`;
            });
            bot.sendMessage(chatId, text, { parse_mode: 'HTML' });
            bot.answerCallbackQuery(query.id);
          }
        } catch (err) {
          bot.answerCallbackQuery(query.id, { text: 'Lỗi tải danh sách code!' });
        }
        return;
      }

      // Thống kê mời bạn
      if (data === 'my_referrals') {
        try {
          const stats = await db.getReferralStats(userId);
          const settings = db.getSettings();
          const botUsername = (await bot.getMe()).username;
          const referralLink = `https://t.me/${botUsername}?start=ref_${userId}`;

          const text = `👥 <b>THỐNG KÊ MỜI BẠN BÈ</b>\n\n` +
            `🔗 Link mời của bạn:\n<code>${referralLink}</code>\n\n` +
            `📊 Tổng đã mời: <b>${stats.total}</b>\n` +
            `✅ Hoàn thành (xem đủ video): <b>${stats.completed}</b>\n` +
            `⏳ Chờ hoàn thành: <b>${stats.pending}</b>\n\n` +
            `🎁 Cần mời đủ <b>${stats.rewardCount}</b> người hoàn thành → nhận 1 Code thưởng\n` +
            `🏆 Code thưởng đã kiếm được: <b>${stats.rewardsEarned}</b>`;

          bot.sendMessage(chatId, text, { parse_mode: 'HTML' });
          bot.answerCallbackQuery(query.id);
        } catch (err) {
          bot.answerCallbackQuery(query.id, { text: 'Lỗi tải thống kê referral!' });
        }
        return;
      }

      bot.answerCallbackQuery(query.id);
    });

    return bot;
  } catch (err) {
    console.error('❌ Lỗi khởi tạo Telegram Bot:', err.message);
    return null;
  }
}

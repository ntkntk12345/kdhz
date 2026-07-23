import TelegramBot from 'node-telegram-bot-api';
import { db } from './db.js';

export function setupTelegramBot() {
  const token = '8988870338:AAH2jR6Mh60UWxXj_9F_yODIf89yqhXc3HA';

  try {
    const bot = new TelegramBot(token, { polling: true });

    console.log('🚀 [Telegram Bot] Bot Telegram đã kết nối thành công với Token mới!');

    // Handle polling errors gracefully to prevent crashing
    bot.on('polling_error', (error) => {
      // Ignore transient polling conflicts or internet reconnects
      if (error.code !== 'ETELEGRAM') {
        console.warn('⚠️ Telegram Bot Polling Note:', error.message || error);
      }
    });

    // 1. Handle /start command for users
    bot.onText(/\/start/, async (msg) => {
      const chatId = msg.chat.id;
      const firstName = msg.from?.first_name || 'Bạn';
      const currentSettings = db.getSettings();
      const rawWebappUrl = currentSettings.miniappUrl || 'https://daovangcoin.com/';

      try {
        const categories = await db.getCategories();
        const activeCategories = categories.filter(c => c.active);
        const catListStr = activeCategories.map(c => `• <b>${c.name}</b>: ${c.description || 'Xem ad nhận code'}`).join('\n');

        const welcomeText = `👋 <b>Xin chào ${firstName}!</b>\n\n` +
          `🎁 <b>NHẬN CODE TRẢI NGHIỆM MIỄN PHÍ 88K</b> 🎁\n\n` +
          `Các danh mục hỗ trợ:\n${catListStr}\n\n` +
          `👇 Nhấn nút bên dưới để mở <b>Mini App Nhận Code 88K</b> ngay!`;

        // Telegram WebApp inline button
        const inlineButton = { text: '🎁 MỞ MINI APP NHẬN CODE 88K', web_app: { url: rawWebappUrl } };

        bot.sendMessage(chatId, welcomeText, {
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [inlineButton],
              [
                { text: '📋 Code đã nhận', callback_data: 'my_claims' }
              ]
            ]
          }
        }).catch(err => {
          console.error('❌ Error sending Telegram /start response:', err.message);
        });
      } catch (err) {
        console.error('Error handling /start command:', err);
      }
    });

    // 2. Handle Admin authentication: /admin <password>
    bot.onText(/\/admin(?:\s+(.+))?/, (msg, match) => {
      const chatId = msg.chat.id;
      const senderId = msg.from?.id;
      const inputPass = match[1] ? match[1].trim() : '';

      const currentSettings = db.getSettings();
      if (inputPass === currentSettings.adminPassword || String(senderId) === '5301275536') {
        db.addAdminTelegramId(senderId);
        bot.sendMessage(chatId, `✅ <b>XÁC NHẬN ADMIN THÀNH CÔNG!</b>\n\nTelegram ID <code>${senderId}</code> của bạn đã được ủy quyền nạp code bằng các lệnh:\n\n• <code>/addcode CODE1 CODE2 CODE3</code> (Nạp vào Tân Thủ)\n• <code>/addcode gifcode CODE1 CODE2 CODE3</code> (Nạp vào GIFCODE)\n• <code>/addcode_tanthu CODE1 CODE2 CODE3</code>`, { parse_mode: 'HTML' });
      } else {
        bot.sendMessage(chatId, '❌ <b>Sai mật khẩu Admin!</b> Vui lòng nhập: <code>/admin <mat_khau></code>', { parse_mode: 'HTML' });
      }
    });

    // 3. Handle Admin Code Insertion: /addcode, /code, /addcode_tanthu, /addcode_gifcode
    bot.on('message', async (msg) => {
      if (!msg.text) return;
      const text = msg.text.trim();

      if (text.startsWith('/addcode') || text.startsWith('/code')) {
        const senderId = msg.from?.id;

        // Auto-authorize default Admin ID 5301275536
        if (String(senderId) === '5301275536') {
          db.addAdminTelegramId(senderId);
        }

        // Check if sender is authorized Admin
        if (!db.isAdminTelegram(senderId) && String(senderId) !== '5301275536') {
          bot.sendMessage(msg.chat.id, '⛔ <i>Lệnh này chỉ dành riêng cho Admin! Gửi /admin <mat_khau> để mở khóa.</i>', { parse_mode: 'HTML' });
          return;
        }

        // Parse command & payload
        const firstSpaceIndex = text.indexOf(' ');
        let command = firstSpaceIndex !== -1 ? text.substring(0, firstSpaceIndex) : text;
        const rawContent = firstSpaceIndex !== -1 ? text.substring(firstSpaceIndex + 1).trim() : '';

        if (!rawContent) {
          bot.sendMessage(msg.chat.id, `⚠️ <b>HƯỚNG DẪN NẠP GIFCODE ADMIN:</b>\n\n• Nạp code Tân Thủ:\n<code>/addcode CODE1 CODE2 CODE3</code>\n\n• Nạp code GIFCODE VIP:\n<code>/addcode gifcode CODE1 CODE2 CODE3</code>`, { parse_mode: 'HTML' });
          return;
        }

        let targetSlug = 'tanthu';
        let codesToInsert = [];

        // Check if command specifies category suffix e.g. /addcode_gifcode
        if (command.includes('_gifcode')) {
          targetSlug = 'gifcode';
          codesToInsert = rawContent.split(/[\n,\s]+/).map(c => c.trim()).filter(c => c.length > 0);
        } else if (command.includes('_tanthu')) {
          targetSlug = 'tanthu';
          codesToInsert = rawContent.split(/[\n,\s]+/).map(c => c.trim()).filter(c => c.length > 0);
        } else {
          // Check if first word of rawContent is a known category slug
          const parts = rawContent.split(/\s+/);
          const possibleSlug = parts[0].toLowerCase();
          if (['gifcode', 'tanthu'].includes(possibleSlug)) {
            targetSlug = possibleSlug;
            codesToInsert = parts.slice(1).join(' ').split(/[\n,\s]+/).map(c => c.trim()).filter(c => c.length > 0);
          } else {
            // Default to 'tanthu'
            codesToInsert = rawContent.split(/[\n,\s]+/).map(c => c.trim()).filter(c => c.length > 0);
          }
        }

        if (codesToInsert.length === 0) {
          bot.sendMessage(msg.chat.id, '❌ Danh sách Gifcode rỗng!');
          return;
        }

        try {
          const result = await db.addCodesBySlugOrName(targetSlug, codesToInsert);

          const replyMsg = `✅ <b>NẠP GIFCODE THÀNH CÔNG (SQLITE)!</b>\n\n` +
            `📌 Mục: <b>${result.categoryName}</b>\n` +
            `➕ Đã nạp mới: <b>${result.addedCount} code</b>\n` +
            `📦 Tổng kho hiện tại: <b>${result.availableCount} code khả dụng</b>`;

          bot.sendMessage(msg.chat.id, replyMsg, { parse_mode: 'HTML' });
        } catch (err) {
          bot.sendMessage(msg.chat.id, `❌ Lỗi nạp code: ${err.message}`);
        }
      }
    });

    // 4. Callback query handler
    bot.on('callback_query', async (query) => {
      const chatId = query.message.chat.id;
      const userId = String(query.from.id);

      if (query.data === 'my_claims') {
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
      }
    });

    return bot;
  } catch (err) {
    console.error('❌ Lỗi khởi tạo Telegram Bot:', err.message);
    return null;
  }
}

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

    // Track pending input states (chatId -> { action, categoryId, etc. })
    const pendingState = new Map();

    function extractMessageHtml(msg) {
      const text = msg.text || msg.caption || '';
      const entities = msg.entities || msg.caption_entities;
      if (!entities || entities.length === 0 || !text) return text;

      try {
        const buf = Buffer.from(text, 'utf16le');
        const insertions = {};

        entities.forEach(entity => {
          const startByte = entity.offset * 2;
          const endByte = (entity.offset + entity.length) * 2;

          let openTag = '', closeTag = '';
          if (entity.type === 'bold') { openTag = '<b>'; closeTag = '</b>'; }
          else if (entity.type === 'italic') { openTag = '<i>'; closeTag = '</i>'; }
          else if (entity.type === 'code') { openTag = '<code>'; closeTag = '</code>'; }
          else if (entity.type === 'pre') { openTag = '<pre>'; closeTag = '</pre>'; }
          else if (entity.type === 'underline') { openTag = '<u>'; closeTag = '</u>'; }
          else if (entity.type === 'strikethrough') { openTag = '<s>'; closeTag = '</s>'; }
          else if (entity.type === 'text_link') { openTag = `<a href="${entity.url}">`; closeTag = '</a>'; }

          if (openTag && closeTag) {
            if (!insertions[startByte]) insertions[startByte] = [];
            insertions[startByte].push(openTag);

            if (!insertions[endByte]) insertions[endByte] = [];
            insertions[endByte].unshift(closeTag);
          }
        });

        const resultChunks = [];
        for (let i = 0; i < buf.length; i += 2) {
          if (insertions[i]) {
            insertions[i].forEach(tag => resultChunks.push(Buffer.from(tag, 'utf16le')));
          }
          resultChunks.push(buf.slice(i, i + 2));
        }
        if (insertions[buf.length]) {
          insertions[buf.length].forEach(tag => resultChunks.push(Buffer.from(tag, 'utf16le')));
        }

        return Buffer.concat(resultChunks).toString('utf16le');
      } catch (err) {
        return text;
      }
    }

    // Helper: Check Telegram Group Membership for a User
    async function checkUserMembership(userId) {
      const settings = db.getSettings();
      const groups = settings.requiredGroups || [];
      
      if (!groups || groups.length === 0) {
        return { isSubscribed: true, missingGroups: [] };
      }

      const missingGroups = [];
      for (const grp of groups) {
        try {
          const member = await bot.getChatMember(grp, userId);
          const status = member?.status;
          if (!status || !['member', 'administrator', 'creator'].includes(status)) {
            missingGroups.push(grp);
          }
        } catch (err) {
          // If bot is not admin or channel private, assume missing
          console.warn(`⚠️ Cannot check membership for ${grp}:`, err.message);
          missingGroups.push(grp);
        }
      }

      return {
        isSubscribed: missingGroups.length === 0,
        missingGroups
      };
    }

    // Helper: Build Main Reply Keyboard (Fixed menu below chat input)
    function buildMainMenuKeyboard(userId) {
      const settings = db.getSettings();
      const rawWebappUrl = settings.miniappUrl || 'https://daovangcoin.com/';
      const joinAllLink = settings.joinAllLink || '';
      const isAdmin = db.isAdminTelegram(userId) || String(userId) === '5301275536';

      const keyboard = [];

      // Row 1: Big MiniApp WebApp Button
      keyboard.push([
        { text: '🎁 MỞ MINI APP NHẬN CODE 88K', web_app: { url: rawWebappUrl } }
      ]);

      // Row 2: Join All Groups (if link exists)
      if (joinAllLink) {
        keyboard.push([
          { text: '📢 THAM GIA TẤT CẢ NHÓM', url: joinAllLink }
        ]);
      }

      // Row 3: Claims & Referrals
      keyboard.push([
        { text: '📋 Code đã nhận' },
        { text: '👥 Thống kê mời bạn' }
      ]);

      // Row 4: Admin Panel & Stock Stats (ONLY IF ADMIN)
      if (isAdmin) {
        keyboard.push([
          { text: '📦 Thống kê kho code' },
          { text: '⚙️ BẢNG ĐIỀU KHIỂN ADMIN' }
        ]);
      }

      return {
        keyboard,
        resize_keyboard: true,
        is_persistent: true
      };
    }

    // Helper: Build Admin Interactive Panel Inline Keyboard
    function buildAdminPanelKeyboard() {
      return {
        inline_keyboard: [
          [
            { text: '➕ Nạp Code', callback_data: 'admin_add_code' },
            { text: '🗑️ Xóa Code', callback_data: 'admin_del_code' }
          ],
          [
            { text: '📊 Thống Kê Kho', callback_data: 'admin_stats' },
            { text: '📂 Quản Lý Danh Mục', callback_data: 'admin_cats' }
          ],
          [
            { text: '📢 Quản Lý Nhóm', callback_data: 'admin_groups' },
            { text: '🔗 Đổi Link Join All', callback_data: 'admin_set_link' }
          ]
        ]
      };
    }

    // Send or Edit Admin Panel Message
    async function sendAdminPanel(chatId, messageId = null) {
      const settings = db.getSettings();
      const groups = settings.requiredGroups || [];
      const link = settings.joinAllLink || 'Chưa thiết lập';
      const stats = await db.getAdminStats();

      let text = `⚙️ <b>BẢNG ĐIỀU KHIỂN QUẢN TRỊ (ADMIN PANEL)</b>\n\n`;
      text += `📦 <b>THỐNG KÊ KHO CODE:</b>\n`;
      stats.categories.forEach(c => {
        text += `• <b>${c.name}</b>: Còn <b>${c.available}</b> / Tổng <b>${c.total}</b> (Đã phát ${c.used})\n`;
      });
      text += `\n📋 <b>Tổng lượt bốc code:</b> ${stats.totalClaims}\n`;
      text += `📢 <b>Nhóm bắt buộc (${groups.length}):</b> ${groups.join(', ') || 'Chưa có'}\n`;
      text += `🔗 <b>Link Join All:</b> ${link}\n\n`;
      text += `👇 <i>Chọn thao tác quản lý bên dưới:</i>`;

      if (messageId) {
        bot.editMessageText(text, {
          chat_id: chatId,
          message_id: messageId,
          parse_mode: 'HTML',
          reply_markup: buildAdminPanelKeyboard()
        }).catch(() => {});
      } else {
        bot.sendMessage(chatId, text, {
          parse_mode: 'HTML',
          reply_markup: buildAdminPanelKeyboard()
        }).catch(() => {});
      }
    }

    async function sendPresetOrFallback(chatId, presetKey, fallbackHtml) {
      const settings = db.getSettings();
      const presets = settings.presetMessages || {};
      const presetData = presets[String(presetKey)];

      if (presetData) {
        if (typeof presetData === 'object' && presetData !== null) {
          const savedChat = presetData.chat_id;
          const savedMsg = presetData.message_id;
          const savedHtml = presetData.html || '';

          if (savedChat && savedMsg) {
            try {
              await bot.copyMessage(chatId, savedChat, savedMsg);
              return true;
            } catch (err) {}
          }

          if (savedHtml) {
            try {
              await bot.sendMessage(chatId, savedHtml, { parse_mode: 'HTML' });
              return true;
            } catch (err) {}
          }
        } else if (typeof presetData === 'string') {
          try {
            await bot.sendMessage(chatId, String(presetData), { parse_mode: 'HTML' });
            return true;
          } catch (err) {}
        }
      }

      if (fallbackHtml) {
        await bot.sendMessage(chatId, fallbackHtml, { parse_mode: 'HTML' });
      }
      return false;
    }

    // Send Welcome Message after membership verification passes
    async function sendWelcomeAfterSubscribed(chatId, userId, firstName) {
      const currentSettings = db.getSettings();
      const presets = currentSettings.presetMessages || {};

      // Preset 1 → tin nhắn chào mừng
      const preset1 = presets['1'];
      let welcomeText = '';
      if (preset1) {
        welcomeText = typeof preset1 === 'object' ? (preset1.html || '') : String(preset1);
      } else {
        const botMe = await bot.getMe();
        const referralLink = `https://t.me/${botMe.username}?start=ref_${userId}`;
        welcomeText = `👋 <b>Xin chào ${firstName}!</b>\n\n` +
          `🎁 <b>NHẬN CODE TRẢI NGHIỆM MIỄN PHÍ 88K</b> 🎁\n\n` +
          `👥 <b>Mời bạn bè:</b> Mời 3 người bạn xem đủ video → nhận thêm 1 Code miễn phí!\n` +
          `🔗 Link mời của bạn:\n<code>${referralLink}</code>\n\n` +
          `👇 Nhấn nút menu <b>"🎁 MỞ MINI APP NHẬN CODE 88K"</b> ở dưới khung chat để bắt đầu!`;
      }

      if (welcomeText) {
        bot.sendMessage(chatId, welcomeText, { parse_mode: 'HTML' }).catch(() => {
          bot.sendMessage(chatId, welcomeText);
        });
      }

      // Preset 2 → thay "👇 Hoặc chọn các chức năng khác bên dưới:"
      const preset2 = presets['2'];
      const menuText = preset2
        ? (typeof preset2 === 'object' ? (preset2.html || '') : String(preset2))
        : '👇 Hoặc chọn các chức năng khác bên dưới:';

      bot.sendMessage(chatId, menuText, {
        parse_mode: 'HTML',
        reply_markup: buildMainMenuKeyboard(userId)
      }).catch(() => {
        bot.sendMessage(chatId, menuText, { reply_markup: buildMainMenuKeyboard(userId) });
      });
    }

    // Send Group Membership Gate Message
    function sendMembershipGateMessage(chatId, missingGroups) {
      const settings = db.getSettings();
      const joinAllLink = settings.joinAllLink || '';
      const presets = settings.presetMessages || {};

      // Preset 5 → tin nhắn yêu cầu tham gia kênh
      const preset5 = presets['5'];
      if (preset5) {
        const html5 = typeof preset5 === 'object' ? (preset5.html || '') : String(preset5);
        if (html5) {
          bot.sendMessage(chatId, html5, { parse_mode: 'HTML' }).catch(() => bot.sendMessage(chatId, html5));
          return;
        }
      }

      let text = `‼️ <b>VUI LÒNG THAM GIA ĐẦY ĐỦ CÁC KÊNH / NHÓM BẮT BUỘC</b> ‼️\n\n` +
        `Để mở khóa Mini App & Nhận Gifcode 88K, bạn cần tham gia đầy đủ các kênh chính thức bên dưới:\n\n`;

      missingGroups.forEach((g, idx) => {
        text += `${idx + 1}. <b>${g}</b>\n`;
      });

      text += `\n👇 <i>Bấm từng nút kênh bên dưới để tham gia và bấm "Xác Minh Ngay":</i>`;

      const inlineKeyboard = [];

      // 1. Individual button for EACH missing group/channel (like mb66.py)
      missingGroups.forEach((grp, idx) => {
        const cleanName = grp.replace('@', '');
        const grpUrl = grp.startsWith('http') ? grp : `https://t.me/${cleanName}`;
        inlineKeyboard.push([
          { text: `📢 KÊNH ${idx + 1}: ${grp}`, url: grpUrl }
        ]);
      });

      // 2. Link Join All Button (if set)
      if (joinAllLink) {
        inlineKeyboard.push([
          { text: '🌐 THAM GIA TẤT CẢ NHÓM (LINK TỔNG)', url: joinAllLink }
        ]);
      }

      // 3. Re-verify Button
      inlineKeyboard.push([
        { text: '🔄 ĐÃ THAM GIA - XÁC MINH NGAY', callback_data: 'check_membership_again' }
      ]);

      bot.sendMessage(chatId, text, {
        parse_mode: 'HTML',
        reply_markup: { inline_keyboard: inlineKeyboard }
      });
    }

    // ──────────────────────────────────────────────────────────────────
    // /start — Check Membership FIRST (like mb66.py) + Welcome / Referral
    // ──────────────────────────────────────────────────────────────────
    bot.onText(/\/start(?:\s+(.+))?/, async (msg, match) => {
      const chatId = msg.chat.id;
      const userId = String(msg.from?.id);
      const firstName = msg.from?.first_name || 'Bạn';
      const username = msg.from?.username || msg.from?.first_name || 'user';
      const param = match[1] ? match[1].trim() : '';

      // Auto authorize default Admin ID
      if (userId === '5301275536') {
        db.addAdminTelegramId(userId);
      }

      // Handle referral link: /start ref_USERID
      if (param.startsWith('ref_')) {
        const referrerId = param.replace('ref_', '');
        if (referrerId && referrerId !== userId) {
          await db.recordReferral(referrerId, userId, username);
          console.log(`🔗 [Referral] User ${userId} joined via referral from ${referrerId}`);
        }
      }

      // 1. CHECK MEMBERSHIP FIRST (like mb66.py)
      const subCheck = await checkUserMembership(userId);
      if (!subCheck.isSubscribed) {
        sendMembershipGateMessage(chatId, subCheck.missingGroups);
        return;
      }

      // 2. MEMBERSHIP PASSED -> SEND WELCOME + MENU
      await sendWelcomeAfterSubscribed(chatId, userId, firstName);
    });

    // ──────────────────────────────────────────────────────────────────
    // /admin — Mở Panel Admin trực tiếp trên Bot
    // ──────────────────────────────────────────────────────────────────
    bot.onText(/\/admin(?:\s+(.+))?/, async (msg, match) => {
      const chatId = msg.chat.id;
      const senderId = String(msg.from?.id);
      const inputPass = match[1] ? match[1].trim() : '';

      const currentSettings = db.getSettings();
      const isAuth = inputPass === currentSettings.adminPassword || senderId === '5301275536' || db.isAdminTelegram(senderId);

      if (isAuth) {
        db.addAdminTelegramId(senderId);
        bot.sendMessage(chatId, '✅ <b>Đã kích hoạt quyền Admin!</b>', {
          parse_mode: 'HTML',
          reply_markup: buildMainMenuKeyboard(senderId)
        });
        await sendAdminPanel(chatId);
      } else {
        bot.sendMessage(chatId, '❌ <b>Sai mật khẩu Admin!</b> Gửi: <code>/admin [mat_khau]</code>', { parse_mode: 'HTML' });
      }
    });

    // Lệnh nhanh /thongke, /addcode, /groups
    bot.onText(/\/thongke/, async (msg) => {
      const senderId = String(msg.from?.id);
      if (senderId === '5301275536') db.addAdminTelegramId(senderId);
      if (!db.isAdminTelegram(senderId)) return;
      await sendAdminPanel(msg.chat.id);
    });

    bot.onText(/\/resetdb/, async (msg) => {
      const senderId = String(msg.from?.id);
      if (senderId === '5301275536') db.addAdminTelegramId(senderId);
      if (!db.isAdminTelegram(senderId)) return;

      try {
        await db.resetAllData();
        bot.sendMessage(
          msg.chat.id,
          "🧹 <b>ĐÃ RESET TOÀN BỘ DỮ LIỆU TẤT CẢ (RESET ALL)!</b>\n\n" +
          "• Đã xóa toàn bộ lịch sử bốc quà (Claims)\n" +
          "• Đã xóa dữ liệu IP views & vân tay thiết bị (Fingerprints)\n" +
          "• Đã xóa thống kê giới thiệu (Referrals)\n" +
          "• Đã xóa trạng thái xác minh user (Subscribed users)\n" +
          "• <b>Đã khôi phục TOÀN BỘ mã Gifcode về trạng thái khả dụng (chưa bốc)</b>\n\n" +
          "👉 Tất cả dữ liệu hệ thống đã về trạng thái mới 100%!",
          { parse_mode: 'HTML' }
        );
      } catch (err) {
        bot.sendMessage(msg.chat.id, `❌ Lỗi reset: ${err.message}`);
      }
    });

    // Command Handler: /set1, /set2 ... /setN (Admin set preset pre message)
    bot.onText(/\/set(\d+)(?:\s+([\s\S]+))?/, async (msg, match) => {
      const chatId = msg.chat.id;
      const senderId = String(msg.from?.id);
      if (senderId === '5301275536') db.addAdminTelegramId(senderId);

      if (!db.isAdminTelegram(senderId)) {
        bot.sendMessage(chatId, '⛔ Bạn không có quyền Admin!');
        return;
      }

      const numKey = match[1];
      const content = match[2] ? match[2].trim() : '';

      if (content) {
        const settings = db.getSettings();
        if (!settings.presetMessages) settings.presetMessages = {};
        settings.presetMessages[numKey] = content;
        db.updateSettings(settings);

        bot.sendMessage(
          chatId,
          `✅ <b>ĐÃ LƯU TIN NHẮN MẪU SỐ ${numKey}!</b>\n\nNội dung đã lưu:\n${content}`,
          { parse_mode: 'HTML' }
        );
      } else {
        pendingState.set(chatId, { action: 'set_preset_msg', numKey });
        bot.sendMessage(
          chatId,
          `📝 <b>[SET ${numKey}]</b> Hãy gửi tin nhắn bạn muốn lưu làm mẫu tin nhắn số <b>${numKey}</b>:`,
          { parse_mode: 'HTML' }
        );
      }
    });

    bot.onText(/\/addcode/, async (msg) => {
      const senderId = String(msg.from?.id);
      if (senderId === '5301275536') db.addAdminTelegramId(senderId);
      if (!db.isAdminTelegram(senderId)) return;

      pendingState.set(msg.chat.id, { action: 'add_codes', categoryId: 'cat-tanthu', categoryName: 'Kho Code' });
      bot.sendMessage(msg.chat.id, '📝 Hãy gửi tin nhắn chứa <b>danh sách code (mỗi dòng 1 code)</b> bên dưới để nạp trực tiếp vào kho:', { parse_mode: 'HTML' });
    });

    // ──────────────────────────────────────────────────────────────────
    // MESSAGE LISTENER (Xử lý Reply Buttons & Input nhập liệu)
    // ──────────────────────────────────────────────────────────────────
    bot.on('message', async (msg) => {
      if (!msg.text) return;

      const chatId = msg.chat.id;
      const senderId = String(msg.from?.id);
      const text = msg.text.trim();

      // Pending Admin Input: set_preset_msg
      const pending = pendingState.get(chatId);
      if (pending && pending.action === 'set_preset_msg' && (db.isAdminTelegram(senderId) || senderId === '5301275536')) {
        const numKey = pending.numKey || '1';
        const htmlContent = extractMessageHtml(msg);
        const settings = db.getSettings();
        if (!settings.presetMessages) settings.presetMessages = {};
        settings.presetMessages[numKey] = {
          html: htmlContent,
          chat_id: msg.chat.id,
          message_id: msg.message_id
        };
        db.updateSettings(settings);
        pendingState.delete(chatId);

        bot.sendMessage(
          chatId,
          `✅ <b>ĐÃ LƯU TIN NHẮN MẪU SỐ ${numKey}!</b>\n\nBấm nút hoặc gõ <b>${numKey}</b> để phát lại tin nhắn này bất kỳ lúc nào.`,
          { parse_mode: 'HTML' }
        );
        return;
      }

      // Check if text is a number trigger for preset message (e.g. "1", "2", "/1", "/2", "set1")
      const numMatch = text.match(/^(?:\/)?(?:set)?(\d+)$/i);
      if (numMatch) {
        const numKey = numMatch[1];
        const settings = db.getSettings();
        const presets = settings.presetMessages || {};

        if (presets[numKey]) {
          const presetData = presets[numKey];

          if (typeof presetData === 'object' && presetData !== null) {
            const savedChat = presetData.chat_id;
            const savedMsg = presetData.message_id;
            const savedHtml = presetData.html || '';

            if (savedChat && savedMsg) {
              bot.copyMessage(chatId, savedChat, savedMsg).then(() => {}).catch(() => {
                if (savedHtml) {
                  bot.sendMessage(chatId, savedHtml, { parse_mode: 'HTML' }).catch(() => {
                    bot.sendMessage(chatId, savedHtml);
                  });
                }
              });
              return;
            }

            if (savedHtml) {
              bot.sendMessage(chatId, savedHtml, { parse_mode: 'HTML' }).catch(() => {
                bot.sendMessage(chatId, savedHtml);
              });
              return;
            }
          } else {
            bot.sendMessage(chatId, String(presetData), { parse_mode: 'HTML' }).catch(() => {
              bot.sendMessage(chatId, String(presetData));
            });
            return;
          }
        }
      }

      // Bấm nút Reply Keyboard: "📦 Thống kê kho code" (CHỈ DÀNH CHO ADMIN)
      if (text === '📦 Thống kê kho code') {
        const isAdmin = db.isAdminTelegram(senderId) || String(senderId) === '5301275536';
        if (!isAdmin) {
          bot.sendMessage(chatId, '⛔ Chức năng Thống Kê Kho Code chỉ dành cho Admin!');
          return;
        }

        try {
          const stats = await db.getTotalCodeStats();
          const fallbackText = `⚙️ <b>THỐNG KÊ KHO GIFCODE (QUẢN TRỊ VIÊN)</b>\n\n` +
            `🟢 <b>Mã Code khả dụng trong kho:</b> <b>${stats.available}</b> / ${stats.total} code\n` +
            `🎁 <b>Đã bốc thành công:</b> <b>${stats.used}</b> mã\n\n` +
            `👇 <i>Sử dụng Bảng Quản Trị để nạp thêm code khi cần!</i>`;

          await sendPresetOrFallback(chatId, '5', fallbackText);
        } catch (err) {
          bot.sendMessage(chatId, `❌ Lỗi lấy thống kê kho: ${err.message}`);
        }
        return;
      }

      // Bấm nút Reply Keyboard: "📋 Code đã nhận"
      if (text === '📋 Code đã nhận') {
        try {
          const claims = await db.getClaims(senderId);
          if (!claims || claims.length === 0) {
            // Preset 4 for empty Code đã nhận
            const defaultEmpty = "‼️ <b><i>Bạn chưa nhận code nào cả. Hãy mở MiniApp làm nhiệm vụ xem video nhận code ngay nào 🎉</i></b>";
            await sendPresetOrFallback(chatId, '4', defaultEmpty);
          } else {
            let replyText = `🎁 <b>DANH SÁCH CODE BẠN ĐÃ NHẬN:</b>\n\n`;
            claims.slice(0, 10).forEach((c, idx) => {
              replyText += `${idx + 1}. <b>${c.categoryName || 'Tân Thủ'}</b>: <code>${c.code}</code>\n   🕒 ${new Date(c.claimedAt || c.claimed_at).toLocaleString('vi-VN')}\n`;
            });
            bot.sendMessage(chatId, replyText, { parse_mode: 'HTML' });
          }
        } catch (err) {
          bot.sendMessage(chatId, 'Lỗi tải danh sách code!');
        }
        return;
      }

      // Bấm nút Reply Keyboard: "👥 Thống kê mời bạn"
      if (text === '👥 Thống kê mời bạn') {
        try {
          const stats = await db.getReferralStats(senderId);
          const botMe = await bot.getMe();
          const referralLink = `https://t.me/${botMe.username}?start=ref_${senderId}`;

          const fallbackText = `📊 <b>THỐNG KÊ MỜI BẠN BÈ</b>\n\n` +
            `✅ <b>Link Mời bạn bè:</b>\n<code>${referralLink}</code>\n\n` +
            `👉 Tổng đã mời: <b>${stats.total}</b> người\n` +
            `✅ Đã tham gia & xác minh: <b>${stats.completed}</b> người\n` +
            `⏳ Chờ xác minh: <b>${stats.pending}</b> người\n\n` +
            `🎁 Số Code Đã Được Nhận: <b>${stats.rewardsEarned}</b>`;

          // Preset 3 for Thống kê mời bạn!
          await sendPresetOrFallback(chatId, '3', fallbackText);
        } catch (err) {
          bot.sendMessage(chatId, 'Lỗi tải thống kê referral!');
        }
        return;
      }

      // Bấm nút Reply Keyboard: "⚙️ BẢNG ĐIỀU KHIỂN ADMIN"
      if (text === '⚙️ BẢNG ĐIỀU KHIỂN ADMIN') {
        if (db.isAdminTelegram(senderId) || senderId === '5301275536') {
          await sendAdminPanel(chatId);
        } else {
          bot.sendMessage(chatId, '⛔ Bạn chưa có quyền Admin! Gửi: <code>/admin [mat_khau]</code>', { parse_mode: 'HTML' });
        }
        return;
      }

      if (text.startsWith('/')) return;

      // Xử lý các trạng thái nhập liệu đang chờ (Admin Pending Inputs)
      const pending = pendingState.get(chatId);
      if (pending && (db.isAdminTelegram(senderId) || senderId === '5301275536')) {
        
        // 1. Nhập danh sách code nạp vào kho
        if (pending.action === 'add_codes') {
          const codes = text.split('\n').map(c => c.trim()).filter(c => c.length > 0);
          if (codes.length === 0) {
            bot.sendMessage(chatId, '❌ Không tìm thấy code hợp lệ! Gửi danh sách code (mỗi dòng 1 code):');
            return;
          }
          try {
            const addedCount = await db.addCodes(pending.categoryId, codes);
            pendingState.delete(chatId);
            bot.sendMessage(chatId,
              `✅ <b>NẠP CODE THÀNH CÔNG!</b>\n\n` +
              `📌 Danh mục: <b>${pending.categoryName}</b>\n` +
              `➕ Đã nạp mới: <b>${addedCount} code</b>`,
              {
                parse_mode: 'HTML',
                reply_markup: buildAdminPanelKeyboard()
              }
            );
          } catch (err) {
            pendingState.delete(chatId);
            bot.sendMessage(chatId, `❌ Lỗi nạp code: ${err.message}`);
          }
          return;
        }

        // 2. Thêm nhóm bắt buộc mới
        if (pending.action === 'add_group') {
          const grpName = text.startsWith('@') ? text : `@${text}`;
          const settings = db.getSettings();
          const groups = settings.requiredGroups || [];
          if (!groups.includes(grpName)) {
            groups.push(grpName);
            db.updateSettings({ requiredGroups: groups });
          }
          pendingState.delete(chatId);
          bot.sendMessage(chatId, `✅ Đã thêm nhóm <code>${grpName}</code> vào danh sách bắt buộc!`, { parse_mode: 'HTML' });
          await sendAdminPanel(chatId);
          return;
        }

        // 3. Đổi link Join All
        if (pending.action === 'set_link') {
          db.updateSettings({ joinAllLink: text });
          pendingState.delete(chatId);
          bot.sendMessage(chatId, `✅ Đã cập nhật Link Join All:\n<code>${text}</code>`, { parse_mode: 'HTML' });
          await sendAdminPanel(chatId);
          return;
        }

        // 4. Xóa 1 mã code cụ thể
        if (pending.action === 'delete_single_code') {
          const codes = await db.getCodes();
          const found = codes.find(c => c.code.trim() === text);
          if (found) {
            await db.deleteCode(found.id);
            pendingState.delete(chatId);
            bot.sendMessage(chatId, `✅ Đã xóa mã code <code>${text}</code> khỏi kho!`, { parse_mode: 'HTML' });
          } else {
            bot.sendMessage(chatId, `❌ Không tìm thấy mã code <code>${text}</code> trong kho!`, { parse_mode: 'HTML' });
          }
          return;
        }
      }
    });

    // ──────────────────────────────────────────────────────────────────
    // CALLBACK QUERY LISTENER (Xử lý bấm nút Inline trong Admin Panel & Gate)
    // ──────────────────────────────────────────────────────────────────
    bot.on('callback_query', async (query) => {
      const chatId = query.message.chat.id;
      const messageId = query.message.message_id;
      const userId = String(query.from.id);
      const firstName = query.from.first_name || 'Bạn';
      const data = query.data;

      // Check membership re-verification callback (like mb66.py)
      if (data === 'check_membership_again') {
        const subCheck = await checkUserMembership(userId);
        if (!subCheck.isSubscribed) {
          bot.answerCallbackQuery(query.id, {
            text: `❌ Bạn chưa tham gia đủ ${subCheck.missingGroups.length} nhóm! Vui lòng tham gia rồi thử lại.`,
            show_alert: true
          });
        } else {
          bot.answerCallbackQuery(query.id, { text: '✅ Xác minh thành công! Đang tải menu...' });
          bot.deleteMessage(chatId, messageId).catch(() => {});
          await sendWelcomeAfterSubscribed(chatId, userId, firstName);
        }
        return;
      }

      // Verify Admin Permission for Admin Callbacks
      if (data.startsWith('admin_')) {
        if (!db.isAdminTelegram(userId) && userId !== '5301275536') {
          bot.answerCallbackQuery(query.id, { text: '⛔ Không có quyền Admin!' });
          return;
        }
        bot.answerCallbackQuery(query.id);
      }

      // 1. Admin Home Panel
      if (data === 'admin_home') {
        pendingState.delete(chatId);
        await sendAdminPanel(chatId, messageId);
        return;
      }

      // 2. Admin Bấm Nạp Code
      if (data === 'admin_add_code') {
        pendingState.set(chatId, { action: 'add_codes', categoryId: 'cat-tanthu', categoryName: 'Kho Code' });

        bot.editMessageText(
          `📦 <b>NẠP CODE VÀO KHO TRỰC TIẾP:</b>\n\n` +
          `📝 Hãy gửi tin nhắn chứa <b>danh sách code (mỗi dòng 1 code)</b> bên dưới để nạp trực tiếp vào kho nhé:\n\n` +
          `<i>Ví dụ gửi:</i>\n<code>CODE1-88K\nCODE2-88K\nCODE3-88K</code>`,
          {
            chat_id: chatId,
            message_id: messageId,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [[{ text: '❌ Hủy', callback_data: 'admin_home' }]] }
          }
        );
        return;
      }

      // Chọn danh mục để nạp code
      if (data.startsWith('admin_select_cat_')) {
        const catId = data.replace('admin_select_cat_', '');
        const categories = await db.getAllCategories();
        const cat = categories.find(c => c.id === catId);

        if (!cat) return;

        pendingState.set(chatId, { action: 'add_codes', categoryId: catId, categoryName: cat.name });

        bot.editMessageText(
          `✅ <b>Đã chọn mục ${cat.name}</b>\n\n` +
          `📝 Bây giờ hãy gửi tin nhắn chứa <b>danh sách code (mỗi dòng 1 code)</b>:`,
          {
            chat_id: chatId,
            message_id: messageId,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [[{ text: '❌ Hủy', callback_data: 'admin_home' }]] }
          }
        );
        return;
      }

      // 3. Admin Bấm Xóa Code
      if (data === 'admin_del_code') {
        const buttons = [
          [{ text: '🔥 XÓA TOÀN BỘ KHO CODE (RỖNG 0 CODE)', callback_data: 'admin_del_all_codes' }],
          [{ text: '🗑️ Xóa 1 mã code cụ thể', callback_data: 'admin_del_single_prompt' }],
          [{ text: '🔙 Quay lại', callback_data: 'admin_home' }]
        ];
        bot.editMessageText(
          `🗑️ <b>XÓA CODE KHỎI KHO:</b>\n\n` +
          `Vui lòng chọn phương thức xóa bên dưới:`,
          {
            chat_id: chatId,
            message_id: messageId,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: buttons }
          }
        );
        return;
      }

      // Xóa toàn bộ kho code
      if (data === 'admin_del_all_codes') {
        await db.deleteAllCodes();
        bot.editMessageText(
          `✅ <b>ĐÃ XÓA SẠCH TOÀN BỘ KHO CODE!</b>\n\n` +
          `Kho Gifcode hiện tại đã hoàn toàn rỗng (0 code).`,
          {
            chat_id: chatId,
            message_id: messageId,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [[{ text: '🔙 Quay lại Bảng Quản Trị', callback_data: 'admin_home' }]] }
          }
        );
        return;
      }

      // Nhập mã code cụ thể để xóa
      if (data === 'admin_del_single_prompt') {
        pendingState.set(chatId, { action: 'delete_single_code' });
        bot.editMessageText(
          `🗑️ <b>XÓA 1 MÃ CODE CỤ THỂ:</b>\n\n` +
          `Vui lòng gửi mã code cụ thể bạn muốn xóa (Ví dụ: <code>CODE123</code>):`,
          {
            chat_id: chatId,
            message_id: messageId,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [[{ text: '❌ Hủy', callback_data: 'admin_home' }]] }
          }
        );
        return;
      }

      // 4. Admin Thống kê Kho
      if (data === 'admin_stats') {
        await sendAdminPanel(chatId, messageId);
        return;
      }

      // 5. Admin Quản lý Nhóm Bắt Buộc
      if (data === 'admin_groups') {
        const settings = db.getSettings();
        const groups = settings.requiredGroups || [];

        let text = `📢 <b>QUẢN LÝ NHÓM BẮT BUỘC:</b>\n\n`;
        if (groups.length === 0) {
          text += `<i>(Chưa có nhóm nào. Bấm Nút Thêm Nhóm bên dưới)</i>\n`;
        } else {
          groups.forEach((g, i) => {
            text += `${i + 1}. <code>${g}</code>\n`;
          });
        }

        const buttons = [
          [{ text: '➕ Thêm Nhóm Mới', callback_data: 'admin_add_grp' }]
        ];

        // Create buttons to delete specific group
        groups.forEach(g => {
          buttons.push([{ text: `❌ Xóa ${g}`, callback_data: `admin_del_grp_${g}` }]);
        });

        buttons.push([{ text: '🔙 Quay lại', callback_data: 'admin_home' }]);

        bot.editMessageText(text, {
          chat_id: chatId,
          message_id: messageId,
          parse_mode: 'HTML',
          reply_markup: { inline_keyboard: buttons }
        });
        return;
      }

      // Bấm thêm nhóm mới
      if (data === 'admin_add_grp') {
        pendingState.set(chatId, { action: 'add_group' });
        bot.editMessageText(`➕ <b>THÊM NHÓM BẮT BUỘC:</b>\n\nGửi username của nhóm (Ví dụ: <code>@mb66vn</code>):`, {
          chat_id: chatId,
          message_id: messageId,
          parse_mode: 'HTML',
          reply_markup: { inline_keyboard: [[{ text: '❌ Hủy', callback_data: 'admin_groups' }]] }
        });
        return;
      }

      // Bấm xóa nhóm
      if (data.startsWith('admin_del_grp_')) {
        const grp = data.replace('admin_del_grp_', '');
        const settings = db.getSettings();
        let groups = settings.requiredGroups || [];
        groups = groups.filter(g => g !== grp);
        db.updateSettings({ requiredGroups: groups });
        bot.answerCallbackQuery(query.id, { text: `Đã xóa ${grp}` });
        
        // Re-render groups panel
        bot.emit('callback_query', { ...query, data: 'admin_groups' });
        return;
      }

      // 6. Admin Đổi Link Join All
      if (data === 'admin_set_link') {
        pendingState.set(chatId, { action: 'set_link' });
        const currentLink = db.getSettings().joinAllLink || 'Chưa thiết lập';
        bot.editMessageText(
          `🔗 <b>ĐỔI LINK THAM GIA TẤT CẢ NHÓM:</b>\n\n` +
          `Link hiện tại: <code>${currentLink}</code>\n\n` +
          `Vui lòng gửi link mới (Ví dụ: <code>https://t.me/your_link</code>):`,
          {
            chat_id: chatId,
            message_id: messageId,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [[{ text: '❌ Hủy', callback_data: 'admin_groups' }]] }
          }
        );
        return;
      }
    });

    return bot;
  } catch (err) {
    console.error('❌ Lỗi khởi tạo Telegram Bot:', err.message);
    return null;
  }
}

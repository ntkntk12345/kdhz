import os
import json
import asyncio
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from telebot import async_telebot as telebot
from telebot import types

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
DB_FILE = os.path.join(BASE_DIR, 'database.sqlite')

# Vietnam Timezone
VIETNAM_TZ = timezone(timedelta(hours=7))

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading settings.json: {e}")
    return {}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving settings.json: {e}")

# Initial settings
settings = load_settings()
API_TOKEN = settings.get('botToken', '8988870338:AAH2jR6Mh60UWxXj_9F_yODIf89yqhXc3HA')

bot = telebot.AsyncTeleBot(API_TOKEN)
pending_states = {}  # {chat_id: {'action': str, ...}}
_bot_me_cache = None

# Synchronous DB helpers
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite_tables():
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            checked INTEGER DEFAULT 0,
            registration_date REAL
        );
        CREATE TABLE IF NOT EXISTS subscribed_users (
            user_id TEXT PRIMARY KEY,
            verified_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id TEXT PRIMARY KEY,
            referrer_id TEXT NOT NULL,
            referred_id TEXT NOT NULL,
            referred_username TEXT,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            created_at TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

init_sqlite_tables()

DEFAULT_ADMIN_IDS = ['5301275536', '8478994342']

def is_admin(user_id):
    cfg = load_settings()
    allowed = [str(x) for x in cfg.get('adminTelegramIds', DEFAULT_ADMIN_IDS)]
    return str(user_id) in allowed or str(user_id) in DEFAULT_ADMIN_IDS

def add_admin(user_id):
    cfg = load_settings()
    admins = [str(x) for x in cfg.get('adminTelegramIds', DEFAULT_ADMIN_IDS)]
    if str(user_id) not in admins:
        admins.append(str(user_id))
        cfg['adminTelegramIds'] = admins
        save_settings(cfg)

def is_user_verified_db(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT 1 FROM subscribed_users WHERE user_id = ?', (str(user_id),))
    row = c.fetchone()
    conn.close()
    return bool(row)

def mark_user_verified_db(user_id):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now(VIETNAM_TZ).isoformat()
    c.execute('INSERT OR REPLACE INTO subscribed_users (user_id, verified_at) VALUES (?, ?)', (str(user_id), now))
    c.execute('INSERT OR IGNORE INTO users (user_id, checked, registration_date) VALUES (?, 1, ?)', (str(user_id), datetime.now(VIETNAM_TZ).timestamp()))
    c.execute('UPDATE users SET checked = 1 WHERE user_id = ?', (str(user_id),))
    conn.commit()
    conn.close()

# Record referral (mb66.py logic)
def record_referral_db(referrer_id, referred_id, referred_username):
    if str(referrer_id) == str(referred_id):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM referrals WHERE referred_id = ?', (str(referred_id),))
    if c.fetchone():
        conn.close()
        return
    ref_id = f"ref-{int(datetime.now().timestamp() * 1000)}"
    now = datetime.now(VIETNAM_TZ).isoformat()
    c.execute(
        'INSERT INTO referrals (id, referrer_id, referred_id, referred_username, completed, created_at) VALUES (?, ?, ?, ?, 0, ?)',
        (ref_id, str(referrer_id), str(referred_id), referred_username or '', now)
    )
    conn.commit()
    conn.close()

# Complete referral immediately when referred user verifies channels on bot
def complete_referral_db(referred_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM referrals WHERE referred_id = ? AND completed = 0', (str(referred_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    now = datetime.now(VIETNAM_TZ).isoformat()
    c.execute('UPDATE referrals SET completed = 1, completed_at = ? WHERE referred_id = ?', (now, str(referred_id)))
    conn.commit()
    referrer_id = row['referrer_id']
    conn.close()
    return referrer_id

def get_referral_stats_db(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM referrals WHERE referrer_id = ?', (str(user_id),))
    rows = c.fetchall()
    conn.close()
    cfg = load_settings()
    reward_count = cfg.get('referralRewardCount', 3)
    completed = len([r for r in rows if r['completed'] == 1])
    pending = len([r for r in rows if r['completed'] == 0])
    rewards_earned = completed // reward_count
    return {
        'total': len(rows),
        'completed': completed,
        'pending': pending,
        'rewardsEarned': rewards_earned,
        'rewardCount': reward_count
    }

# Check Telegram Channel Membership using Telegram Bot API get_chat_member
async def check_user_membership(user_id):
    cfg = load_settings()
    groups = cfg.get('requiredGroups', [])
    if not groups:
        return True, []

    missing = []
    for grp in groups:
        try:
            member = await bot.get_chat_member(grp, int(user_id))
            if member.status not in ['member', 'administrator', 'creator']:
                missing.append(grp)
        except Exception as e:
            logger.warning(f"Error checking membership for {grp} (user {user_id}): {e}")
            missing.append(grp)

    return len(missing) == 0, missing

# UI Keyboards
def build_main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
    
    # Row 1: Claims & Referrals
    markup.row(
        types.KeyboardButton(text='📋 Code đã nhận'),
        types.KeyboardButton(text='👥 Thống kê mời bạn')
    )

    # Row 2: Admin Panel (if Admin)
    if is_admin(user_id):
        markup.row(types.KeyboardButton(text='⚙️ BẢNG ĐIỀU KHIỂN ADMIN'))

    return markup

def build_admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('➕ Nạp Code', callback_data='admin_add_code'),
        types.InlineKeyboardButton('🗑️ Xóa Code', callback_data='admin_del_code')
    )
    markup.add(
        types.InlineKeyboardButton('📊 Thống Kê Kho', callback_data='admin_stats'),
        types.InlineKeyboardButton('📢 Quản Lý Nhóm', callback_data='admin_groups')
    )
    markup.add(
        types.InlineKeyboardButton('💬 Tùy Chỉnh Tin Nhắn', callback_data='admin_custom_msgs'),
        types.InlineKeyboardButton('🔗 Đổi Link Join All', callback_data='admin_set_link')
    )
    return markup

async def send_admin_panel(chat_id, message_id=None):
    cfg = load_settings()
    groups = cfg.get('requiredGroups', [])
    link = cfg.get('joinAllLink', 'Chưa thiết lập')

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) as cnt FROM claims')
    total_claims = c.fetchone()['cnt']
    c.execute('SELECT COUNT(*) as cnt FROM gifcodes WHERE is_used = 0')
    avail_codes = c.fetchone()['cnt']
    c.execute('SELECT COUNT(*) as cnt FROM gifcodes')
    total_codes = c.fetchone()['cnt']
    conn.close()

    text = (
        f"⚙️ <b>BẢNG ĐIỀU KHIỂN QUẢN TRỊ (ADMIN PANEL)</b>\n\n"
        f"📦 <b>KHO CODE:</b> Còn <b>{avail_codes}</b> / Tổng <b>{total_codes}</b> code\n"
        f"📋 <b>Tổng lượt bốc code:</b> {total_claims}\n"
        f"📢 <b>Nhóm bắt buộc ({len(groups)}):</b> {', '.join(groups) if groups else 'Chưa có'}\n"
        f"🔗 <b>Link Join All:</b> {link}\n\n"
        f"👇 <i>Chọn thao tác bên dưới:</i>"
    )

    if message_id:
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=build_admin_keyboard())
        except Exception:
            pass
    else:
        await bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=build_admin_keyboard())

# Gate Message for missing channel subscriptions (EXACT mb66.py inline button style)
async def show_join_channels_message(chat_id, unjoined_groups):
    cfg = load_settings()
    join_all_link = cfg.get('joinAllLink', '')
    custom = cfg.get('customMessages', {})

    default_text = (
        "<b>🎁 BẠN CẦN THAM GIA ĐẦY ĐỦ CÁC KÊNH ĐỂ NHẬN CODE MIỄN PHÍ! 🎁</b>\n\n"
        "👉 <i>Vui lòng bấm nút <b>\"🌐 THAM GIA TẤT CẢ NHÓM\"</b> bên dưới để tham gia, sau đó bấm nút <b>\"✅ KIỂM TRA\"</b> để nhận Code nhé 😘</i>"
    )
    text = custom.get('join', default_text)

    markup = types.InlineKeyboardMarkup(row_width=1)

    # Nút duy nhất Link Tổng (Join All)
    url = join_all_link if join_all_link else (f"https://t.me/{unjoined_groups[0].replace('@', '')}" if unjoined_groups else "https://t.me")
    markup.add(types.InlineKeyboardButton("🌐 THAM GIA TẤT CẢ NHÓM", url=url))

    # Nút xác minh KIỂM TRA
    markup.add(types.InlineKeyboardButton("✅ KIỂM TRA", callback_data="verify_subscription"))

    # Send message with Inline Keyboard attached directly underneath
    await bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)

# Send Welcome Message after verification (Inline Button directly below message)
async def send_welcome_message(chat_id, user_id, first_name, username):
    global _bot_me_cache
    if not _bot_me_cache:
        _bot_me_cache = await bot.get_me()

    referral_link = f"https://t.me/{_bot_me_cache.username}?start=ref_{user_id}"
    miniapp_link = "https://t.me/trainghiemtanthu88k_bot/trainghiem88k"

    cfg = load_settings()
    custom = cfg.get('customMessages', {})

    default_welcome = (
        f"👋 <b>Xin chào {first_name}!</b>\n\n"
        f"🎁 <b>NHẬN CODE TRẢI NGHIỆM MIỄN PHÍ 88K</b> 🎁\n\n"
        f"👥 <b>Mời bạn bè:</b> Mời 3 người bạn tham gia & xem video → nhận thêm 1 Code miễn phí!\n"
        f"🔗 Link mời của bạn:\n<code>{referral_link}</code>\n\n"
        f"👇 Bấm nút <b>\"🎁 MỞ MINI APP NHẬN CODE 88K\"</b> ngay dưới tin nhắn này để bốc code!"
    )

    tpl = custom.get('start')
    if tpl:
        try:
            welcome_text = tpl.format(
                first_name=first_name,
                user_id=user_id,
                referral_link=referral_link,
                miniapp_link=miniapp_link
            )
        except Exception:
            welcome_text = default_welcome
    else:
        welcome_text = default_welcome

    # Inline button directly under the welcome message text
    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(types.InlineKeyboardButton("🎁 MỞ MINI APP NHẬN CODE 88K", url=miniapp_link))

    await bot.send_message(chat_id, welcome_text, parse_mode='HTML', reply_markup=inline_markup)
    
    # Also attach bottom reply keyboard for other functions (Claims, Referral stats)
    await bot.send_message(chat_id, "👇 Hoặc chọn các chức năng khác bên dưới:", reply_markup=build_main_menu_keyboard(user_id))

# Helper: Send milestone referral notification to referrer
async def send_referral_reward_notification(referrer_id, referred_username):
    if not referrer_id:
        return
    try:
        stats = get_referral_stats_db(referrer_id)
        completed = stats['completed']
        reward_count = stats['rewardCount']
        
        display_user = f"@{referred_username}" if referred_username and not referred_username.startswith('@') else (referred_username or 'Thành viên mới')

        cfg = load_settings()
        custom = cfg.get('customMessages', {})

        # Check if reaching a milestone (multiple of reward_count, e.g. 3, 6, 9...)
        if completed > 0 and completed % reward_count == 0:
            default_msg = (
                f"🎉 <b>CHÚC MỪNG BẠN ĐÃ MỜI THÀNH CÔNG ĐỦ {completed} BẠN!</b> 🎁\n\n"
                f"Bạn vừa mời thành công bạn <b>{display_user}</b> và đạt mốc <b>{completed} người</b> (Đủ mốc {reward_count} người)!\n\n"
                f"🎁 <b>Bạn nhận được 1 lượt Gifcode thưởng đặc biệt!</b>\n"
                f"👉 Bấm nút <b>\"🎁 MỞ MINI APP NHẬN CODE 88K\"</b> bên dưới để bốc thưởng ngay!"
            )
            tpl = custom.get('ref3')
            if tpl:
                try:
                    ref_msg = tpl.format(display_user=display_user, completed=completed, reward_count=reward_count)
                except Exception:
                    ref_msg = default_msg
            else:
                ref_msg = default_msg
        else:
            current_in_step = completed % reward_count
            remaining = reward_count - current_in_step
            default_msg = (
                f"🎉 <b>Chúc mừng bạn đã mời thành công bạn {display_user} tham gia bot!</b> ❤️\n\n"
                f"📊 Tiến trình: <b>{current_in_step}/{reward_count}</b> người (Tổng đã mời: <b>{completed}</b> người).\n"
                f"🎁 Mời thêm <b>{remaining} người</b> nữa để nhận ngay 1 Gifcode thưởng!"
            )
            tpl = custom.get('ref12')
            if tpl:
                try:
                    ref_msg = tpl.format(
                        display_user=display_user,
                        completed=completed,
                        current_in_step=current_in_step,
                        reward_count=reward_count,
                        remaining=remaining
                    )
                except Exception:
                    ref_msg = default_msg
            else:
                ref_msg = default_msg

        miniapp_link = "https://t.me/trainghiemtanthu88k_bot/trainghiem88k"
        inline_markup = types.InlineKeyboardMarkup()
        inline_markup.add(types.InlineKeyboardButton("🎁 MỞ MINI APP NHẬN CODE 88K", url=miniapp_link))

        await bot.send_message(int(referrer_id), ref_msg, parse_mode='HTML', reply_markup=inline_markup)
    except Exception as e:
        logger.warning(f"Failed to send referral notification to {referrer_id}: {e}")

# Command Handler: /start
@bot.message_handler(commands=['start'])
async def handle_start(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name or 'Bạn'
    username = message.from_user.username or first_name

    # Auto authorize admin ID
    if user_id == '5301275536':
        add_admin(user_id)

    # Parse referral param: /start ref_123456 or /start 123456 (mb66.py format)
    text_args = message.text.split()
    if len(text_args) > 1:
        param = text_args[1].strip()
        ref_id = param.replace('ref_', '')
        if ref_id.isdigit() and ref_id != user_id:
            record_referral_db(ref_id, user_id, username)
            logger.info(f"🔗 [Referral] User {user_id} (@{username}) recorded under referrer {ref_id}")

    # 1. CHECK CHANNEL MEMBERSHIP FIRST VIA TELEGRAM BOT API (get_chat_member)
    is_sub, unjoined = await check_user_membership(user_id)

    if not is_sub:
        # User hasn't joined all required channels -> Show Inline Buttons directly under start message
        await show_join_channels_message(chat_id, unjoined)
        return

    # 2. USER HAS JOINED ALL CHANNELS -> MARK VERIFIED IN DB
    mark_user_verified_db(user_id)

    # Show Welcome Message WITH Main Reply Keyboard
    await send_welcome_message(chat_id, user_id, first_name, username)

# Command Handler: /resetdb (Admin reset toàn bộ dữ liệu test)
@bot.message_handler(commands=['resetdb'])
async def handle_resetdb(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        await bot.send_message(message.chat.id, "⛔ Bạn không có quyền Admin!")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM fingerprints')
    c.execute('DELETE FROM ip_views')
    c.execute('DELETE FROM claims')
    c.execute('DELETE FROM referrals')
    c.execute('DELETE FROM subscribed_users')
    c.execute('UPDATE users SET checked = 0')
    conn.commit()
    conn.close()

    await bot.send_message(
        message.chat.id,
        "🧹 <b>ĐÃ RESET TOÀN BỘ DỮ LIỆU TEST HỆ THỐNG!</b>\n\n"
        "• Đã xóa dữ liệu vân tay thiết bị (Fingerprints) & IP views\n"
        "• Đã xóa lịch sử bốc code & thống kê giới thiệu\n"
        "• Đã xóa dữ liệu xác minh user\n\n"
        "👉 Bây giờ bạn có thể test lại từ đầu thoải mái!",
        parse_mode='HTML'
    )

# Command Handler: /resetme (Dành cho Admin reset trạng thái test luồng xác minh của cá nhân)
@bot.message_handler(commands=['resetme'])
async def handle_resetme(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        await bot.send_message(message.chat.id, "⛔ Bạn không có quyền Admin!")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM subscribed_users WHERE user_id = ?', (user_id,))
    c.execute('UPDATE users SET checked = 0 WHERE user_id = ?', (user_id,))
    c.execute('DELETE FROM referrals WHERE referred_id = ?', (user_id,))
    conn.commit()
    conn.close()
    await bot.send_message(
        message.chat.id,
        "🔄 <b>Đã xóa trạng thái xác minh test của bạn!</b>\n\n"
        "Bây giờ bạn hãy dùng tài khoản clone (hoặc out khỏi kênh) rồi gõ <code>/start</code> để test lại luồng hiển thị Nút Join Kênh & Nút KIỂM TRA.",
        parse_mode='HTML'
    )

# Command Handler: /admin
@bot.message_handler(commands=['admin'])
async def handle_admin(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    args = message.text.split()
    input_pass = args[1].strip() if len(args) > 1 else ''

    cfg = load_settings()
    correct_pass = cfg.get('adminPassword', 'admin123')

    if input_pass == correct_pass or is_admin(user_id):
        add_admin(user_id)
        await bot.send_message(chat_id, "✅ <b>Kích hoạt quyền Admin thành công!</b>", parse_mode='HTML', reply_markup=build_main_menu_keyboard(user_id))
        await send_admin_panel(chat_id)
    else:
        await bot.send_message(chat_id, "❌ <b>Sai mật khẩu Admin!</b> Cú pháp: <code>/admin [mat_khau]</code>", parse_mode='HTML')

# Callback Query Listener (Inline Button Click)
@bot.callback_query_handler(func=lambda call: True)
async def handle_callback_query(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_id = str(call.from_user.id)
    first_name = call.from_user.first_name or 'Bạn'
    username = call.from_user.username or first_name
    data = call.data

    # Inline Check Button Click: "✅ KIỂM TRA" (verify_subscription)
    if data == 'verify_subscription':
        is_sub, unjoined = await check_user_membership(user_id)
        if not is_sub:
            await bot.answer_callback_query(
                call.id,
                text=f"❌ Bạn chưa tham gia đủ {len(unjoined)} kênh bắt buộc! Vui lòng tham gia rồi bấm lại KIỂM TRA.",
                show_alert=True
            )
        else:
            await bot.answer_callback_query(call.id, text="✅ Xác minh thành công!")
            mark_user_verified_db(user_id)

            try:
                await bot.delete_message(chat_id, message_id)
            except Exception:
                pass

            # NOW SHOW WELCOME MESSAGE + BOT REPLY KEYBOARD
            await send_welcome_message(chat_id, user_id, first_name, username)
        return

    # Admin actions
    if data.startswith('admin_'):
        if not is_admin(user_id):
            await bot.answer_callback_query(call.id, text="⛔ Bạn không có quyền Admin!")
            return
        await bot.answer_callback_query(call.id)

    if data == 'admin_home':
        pending_states.pop(chat_id, None)
        await send_admin_panel(chat_id, message_id)
        return

    if data == 'admin_add_code':
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM categories')
        cats = c.fetchall()
        conn.close()

        buttons = []
        for cat in cats:
            buttons.append([types.InlineKeyboardButton(f"{cat['icon']} {cat['name']}", callback_data=f"admin_sel_cat_{cat['id']}")])
        buttons.append([types.InlineKeyboardButton("🔙 Quay lại", callback_data="admin_home")])

        markup = types.InlineKeyboardMarkup(buttons)
        await bot.edit_message_text("📦 <b>NẠP CODE:</b> Chọn danh mục cần nạp:", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data.startswith('admin_sel_cat_'):
        cat_id = data.replace('admin_sel_cat_', '')
        pending_states[chat_id] = {'action': 'add_codes', 'category_id': cat_id}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_home")]])
        await bot.edit_message_text("📝 Hãy gửi tin nhắn chứa <b>danh sách code (mỗi dòng 1 code)</b>:", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data == 'admin_del_code':
        pending_states[chat_id] = {'action': 'delete_code'}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_home")]])
        await bot.edit_message_text("🗑️ Gửi mã code cụ thể bạn muốn xóa (Ví dụ: <code>CODE123</code>):", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data == 'admin_stats':
        await send_admin_panel(chat_id, message_id)
        return

    if data == 'admin_groups':
        cfg = load_settings()
        groups = cfg.get('requiredGroups', [])
        text = "📢 <b>QUẢN LÝ NHÓM BẮT BUỘC:</b>\n\n"
        if not groups:
            text += "<i>(Chưa có nhóm nào)</i>\n"
        else:
            for idx, g in enumerate(groups, 1):
                text += f"{idx}. <code>{g}</code>\n"

        buttons = [[types.InlineKeyboardButton("➕ Thêm Nhóm Mới", callback_data="admin_add_grp")]]
        for g in groups:
            buttons.append([types.InlineKeyboardButton(f"❌ Xóa {g}", callback_data=f"admin_del_grp_{g}")])
        buttons.append([types.InlineKeyboardButton("🔙 Quay lại", callback_data="admin_home")])

        markup = types.InlineKeyboardMarkup(buttons)
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data == 'admin_add_grp':
        pending_states[chat_id] = {'action': 'add_group'}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_groups")]])
        await bot.edit_message_text("➕ Gửi username của nhóm (Ví dụ: <code>@channelname</code>):", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data.startswith('admin_del_grp_'):
        grp = data.replace('admin_del_grp_', '')
        cfg = load_settings()
        groups = cfg.get('requiredGroups', [])
        groups = [g for g in groups if g != grp]
        cfg['requiredGroups'] = groups
        save_settings(cfg)
        await bot.answer_callback_query(call.id, text=f"Đã xóa {grp}")
        await send_admin_panel(chat_id, message_id)
        return

    if data == 'admin_set_link':
        pending_states[chat_id] = {'action': 'set_link'}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_home")]])
        await bot.edit_message_text("🔗 Gửi link tham gia tất cả nhóm mới (Ví dụ: <code>https://t.me/joinall</code>):", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data == 'admin_custom_msgs':
        buttons = [
            [types.InlineKeyboardButton("📝 Sửa Tin Nhắn Chào Mừng (Start)", callback_data="admin_edit_msg_start")],
            [types.InlineKeyboardButton("📢 Sửa Tin Nhắn Yêu Cầu Join Kênh", callback_data="admin_edit_msg_join")],
            [types.InlineKeyboardButton("🎉 Sửa Tin Báo Ref (1, 2 người)", callback_data="admin_edit_msg_ref12")],
            [types.InlineKeyboardButton("🎁 Sửa Tin Báo Thưởng Ref (Mốc 3 người)", callback_data="admin_edit_msg_ref3")],
            [types.InlineKeyboardButton("🔙 Quay lại", callback_data="admin_home")]
        ]
        markup = types.InlineKeyboardMarkup(buttons)
        await bot.edit_message_text(
            "💬 <b>TÙY CHỈNH TIN NHẮN TỰ ĐỘNG CỦA BOT</b>\n\n"
            "Chọn tin nhắn bạn muốn thay đổi nội dung dưới đây:\n"
            "<i>(Tất cả tin nhắn đều hỗ trợ mã định dạng HTML: &lt;b&gt;in đậm&lt;/b&gt;, &lt;i&gt;in nghiêng&lt;/i&gt;, &lt;code&gt;định dạng code/pre&lt;/code&gt;...)</i>",
            chat_id=chat_id,
            message_id=message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    if data.startswith('admin_edit_msg_'):
        msg_type = data.replace('admin_edit_msg_', '')
        labels = {
            'start': 'Tin Nhắn Chào Mừng (Start)',
            'join': 'Tin Nhắn Yêu Cầu Join Kênh',
            'ref12': 'Tin Nhắn Báo Ref (1, 2 người)',
            'ref3': 'Tin Nhắn Báo Thưởng Ref (Mốc 3 người)'
        }
        vars_info = {
            'start': 'Biến có thể dùng: {first_name}, {user_id}, {referral_link}, {miniapp_link}',
            'join': 'Dùng chữ và mã định dạng HTML thoải mái',
            'ref12': 'Biến có thể dùng: {display_user}, {completed}, {current_in_step}, {reward_count}, {remaining}',
            'ref3': 'Biến có thể dùng: {display_user}, {completed}, {reward_count}'
        }
        cfg = load_settings()
        custom_msgs = cfg.get('customMessages', {})
        current_text = custom_msgs.get(msg_type, 'Chưa cài (Đang dùng tin mặc định)')

        pending_states[chat_id] = {'action': 'edit_custom_msg', 'msg_type': msg_type}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_custom_msgs")]])

        msg_prompt = (
            f"📝 <b>SỬA {labels.get(msg_type, 'TIN NHẮN')}:</b>\n\n"
            f"📌 <b>Nội dung hiện tại:</b>\n<pre>{current_text}</pre>\n\n"
            f"💡 <i>{vars_info.get(msg_type, '')}</i>\n\n"
            f"👇 <b>Hãy gửi nội dung tin nhắn mới bên dưới.</b>\n"
            f"<i>Hỗ trợ mã HTML: &lt;b&gt;in đậm&lt;/b&gt;, &lt;i&gt;in nghiêng&lt;/i&gt;, &lt;code&gt;định dạng pre/code&lt;/code&gt;...</i>"
        )
        await bot.edit_message_text(msg_prompt, chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

# Message Listener (Text Input & Reply Buttons)
@bot.message_handler(func=lambda msg: True)
async def handle_messages(message):
    if not message.text:
        return

    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    text = message.text.strip()

    # Reply Button: "📢 THAM GIA TẤT CẢ NHÓM"
    if text == '📢 THAM GIA TẤT CẢ NHÓM':
        cfg = load_settings()
        link = cfg.get('joinAllLink', '')
        if link:
            await bot.send_message(chat_id, f"🌐 <b>LINK THAM GIA TẤT CẢ NHÓM:</b>\n{link}", parse_mode='HTML')
        else:
            await bot.send_message(chat_id, "Chưa thiết lập link tham gia nhóm!")
        return

    # Reply Button: "📋 Code đã nhận"
    if text == '📋 Code đã nhận':
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM claims WHERE user_id = ? ORDER BY claimed_at DESC LIMIT 10', (user_id,))
        claims = c.fetchall()
        conn.close()

        if not claims:
            await bot.send_message(chat_id, "Bạn chưa nhận code nào. Hãy mở Mini App bốc code ngay!")
        else:
            reply = "🎁 <b>DANH SÁCH CODE ĐÃ NHẬN:</b>\n\n"
            for idx, item in enumerate(claims, 1):
                reply += f"{idx}. <b>{item['category_name'] or 'Tân Thủ'}</b>: <code>{item['code']}</code>\n"
            await bot.send_message(chat_id, reply, parse_mode='HTML')
        return

    # Reply Button: "👥 Thống kê mời bạn"
    if text == '👥 Thống kê mời bạn':
        global _bot_me_cache
        if not _bot_me_cache:
            _bot_me_cache = await bot.get_me()

        stats = get_referral_stats_db(user_id)
        ref_link = f"https://t.me/{_bot_me_cache.username}?start=ref_{user_id}"

        reply = (
            f"👥 <b>THỐNG KÊ MỜI BẠN BÈ</b>\n\n"
            f"🔗 Link mời của bạn:\n<code>{ref_link}</code>\n\n"
            f"📊 Tổng đã mời: <b>{stats['total']}</b> người\n"
            f"✅ Đã tham gia & xác minh: <b>{stats['completed']}</b> người\n"
            f"⏳ Chờ xác minh: <b>{stats['pending']}</b> người\n\n"
            f"🎁 Cần mời đủ <b>{stats['rewardCount']}</b> người → nhận 1 Code thưởng\n"
            f"🏆 Số Code thưởng đã nhận: <b>{stats['rewardsEarned']}</b>"
        )
        await bot.send_message(chat_id, reply, parse_mode='HTML')
        return

    # Reply Button: "⚙️ BẢNG ĐIỀU KHIỂN ADMIN"
    if text == '⚙️ BẢNG ĐIỀU KHIỂN ADMIN':
        if is_admin(user_id):
            await send_admin_panel(chat_id)
        else:
            await bot.send_message(chat_id, "⛔ Bạn không có quyền Admin! Gửi: <code>/admin [mat_khau]</code>", parse_mode='HTML')
        return

    if text.startswith('/'):
        return

    # Pending Admin Inputs
    if chat_id in pending_states and is_admin(user_id):
        pending = pending_states.pop(chat_id)
        action = pending.get('action')

        if action == 'edit_custom_msg':
            msg_type = pending.get('msg_type')
            cfg = load_settings()
            custom_msgs = cfg.get('customMessages', {})
            custom_msgs[msg_type] = text
            cfg['customMessages'] = custom_msgs
            save_settings(cfg)

            await bot.send_message(
                chat_id,
                f"✅ <b>Đã cập nhật tin nhắn mới thành công!</b>\n\nNội dung đã lưu:\n<pre>{text}</pre>",
                parse_mode='HTML'
            )
            await send_admin_panel(chat_id)
            return

        if action == 'add_codes':
            cat_id = pending.get('category_id')
            codes_arr = [c.strip() for c in text.split('\n') if c.strip()]
            conn = get_db()
            c = conn.cursor()
            added = 0
            for code in codes_arr:
                code_id = f"code-{int(datetime.now().timestamp()*1000)}-{os.urandom(2).hex()}"
                now = datetime.now(VIETNAM_TZ).isoformat()
                c.execute('INSERT INTO gifcodes (id, category_id, code, is_used, created_at) VALUES (?, ?, ?, 0, ?)', (code_id, cat_id, code, now))
                added += 1
            conn.commit()
            conn.close()

            await bot.send_message(chat_id, f"✅ Đã nạp <b>{added} code</b> vào kho!", parse_mode='HTML', reply_markup=build_admin_keyboard())
            return

        if action == 'add_group':
            grp_name = text if text.startswith('@') else f"@{text}"
            cfg = load_settings()
            groups = cfg.get('requiredGroups', [])
            if grp_name not in groups:
                groups.append(grp_name)
                cfg['requiredGroups'] = groups
                save_settings(cfg)
            await bot.send_message(chat_id, f"✅ Đã thêm nhóm <code>{grp_name}</code>!", parse_mode='HTML')
            await send_admin_panel(chat_id)
            return

        if action == 'set_link':
            cfg = load_settings()
            cfg['joinAllLink'] = text
            save_settings(cfg)
            await bot.send_message(chat_id, f"✅ Đã cập nhật Link Join All:\n<code>{text}</code>", parse_mode='HTML')
            await send_admin_panel(chat_id)
            return

        if action == 'delete_code':
            conn = get_db()
            c = conn.cursor()
            c.execute('DELETE FROM gifcodes WHERE code = ?', (text,))
            count = c.rowcount
            conn.commit()
            conn.close()

            if count > 0:
                await bot.send_message(chat_id, f"✅ Đã xóa code <code>{text}</code>!", parse_mode='HTML')
            else:
                await bot.send_message(chat_id, f"❌ Không tìm thấy code <code>{text}</code>!", parse_mode='HTML')
            return

async def main():
    logger.info("🚀 [Python Bot] Starting Telegram Bot in Python (bot.py)...")
    await bot.polling(non_stop=True, timeout=60)

if __name__ == '__main__':
    asyncio.run(main())

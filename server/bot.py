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

def extract_message_html(message):
    text = message.text or message.caption or ''
    if not text:
        return ""

    entities = getattr(message, 'entities', None) or getattr(message, 'caption_entities', None)
    if not entities:
        return text

    try:
        encoded = text.encode('utf-16-le')
        insertions = {}

        for entity in entities:
            offset = entity.offset
            length = entity.length
            etype = entity.type
            url = getattr(entity, 'url', '')

            start_byte = offset * 2
            end_byte = (offset + length) * 2

            open_tag = ''
            close_tag = ''

            if etype == 'bold': open_tag, close_tag = '<b>', '</b>'
            elif etype == 'italic': open_tag, close_tag = '<i>', '</i>'
            elif etype == 'code': open_tag, close_tag = '<code>', '</code>'
            elif etype == 'pre': open_tag, close_tag = '<pre>', '</pre>'
            elif etype == 'underline': open_tag, close_tag = '<u>', '</u>'
            elif etype == 'strikethrough': open_tag, close_tag = '<s>', '</s>'
            elif etype == 'blockquote': open_tag, close_tag = '<blockquote>', '</blockquote>'
            elif etype == 'text_link': open_tag, close_tag = f'<a href="{url}">', '</a>'
            elif etype == 'custom_emoji':
                emoji_id = getattr(entity, 'custom_emoji_id', '')
                open_tag, close_tag = f'<tg-emoji emoji-id="{emoji_id}">', '</tg-emoji>'

            if open_tag and close_tag:
                insertions.setdefault(start_byte, []).append(open_tag)
                insertions.setdefault(end_byte, []).insert(0, close_tag)

        result_bytes = bytearray()
        for i in range(0, len(encoded), 2):
            if i in insertions:
                for tag in insertions[i]:
                    result_bytes.extend(tag.encode('utf-16-le'))
            result_bytes.extend(encoded[i:i+2])

        if len(encoded) in insertions:
            for tag in insertions[len(encoded)]:
                result_bytes.extend(tag.encode('utf-16-le'))

        return result_bytes.decode('utf-16-le')
    except Exception as e:
        logger.error(f"Error parsing message entities to HTML: {e}")
        return text

def format_preset_vars(html_text, context_vars=None):
    if not html_text:
        return html_text

    import re
    text = html_text
    ctx = context_vars or {}

    # 1. User Name replacements
    first_name = ctx.get('first_name')
    if first_name:
        text = text.replace('( Tên )', first_name)
        text = text.replace('(Tên)', first_name)
        text = text.replace('( Tên)', first_name)
        text = text.replace('(Tên )', first_name)
        text = text.replace('{first_name}', first_name)
        text = text.replace('{name}', first_name)

    # 2. Referral Link & Bot Username replacements
    ref_link = ctx.get('referral_link')
    if ref_link:
        text = text.replace('( Link )', ref_link)
        text = text.replace('(Link)', ref_link)
        text = text.replace('( Link)', ref_link)
        text = text.replace('(Link )', ref_link)
        text = text.replace('{link}', ref_link)
        text = text.replace('{referral_link}', ref_link)
        text = re.sub(r'https://t\.me/[a-zA-Z0-9_]+\?start=ref_\d+', ref_link, text)

    bot_username = ctx.get('bot_username')
    if bot_username:
        text = text.replace('@bot', f'@{bot_username}')

    # 3. Dynamic Referral Stats replacements (Preset 3)
    if 'total' in ctx:
        total = ctx['total']
        completed = ctx['completed']
        pending = ctx['pending']
        rewards_earned = ctx.get('rewardsEarned', 0)

        text = re.sub(r'(Tổng đã mời:\s*<b>)[^<]*(</b>)', rf'\g<1>{total}\g<2>', text)
        text = re.sub(r'(Đã tham gia & xác minh:\s*<b>)[^<]*(</b>)', rf'\g<1>{completed}\g<2>', text)
        text = re.sub(r'(Chờ xác minh:\s*<b>)[^<]*(</b>)', rf'\g<1>{pending}\g<2>', text)
        text = re.sub(r'(Số Code Đã Được Nhận\s*:\s*<b>)[^<]*(</b>)', rf'\g<1>{rewards_earned}\g<2>', text)

        text = text.replace('{total}', str(total))
        text = text.replace('{completed}', str(completed))
        text = text.replace('{pending}', str(pending))
        text = text.replace('{rewardsEarned}', str(rewards_earned))

    return text

async def send_preset_or_fallback(chat_id, num_key, fallback_text=None, reply_markup=None, context_vars=None, photo_url=None):
    """Send preset message from settings.json with dynamic variables (name, ref link, stats) and optional photo."""
    cfg = load_settings()
    presets = cfg.get('presetMessages', {})
    preset_data = presets.get(str(num_key))

    saved_photo = photo_url

    if preset_data:
        saved_html = ""
        if isinstance(preset_data, dict):
            saved_html = preset_data.get('text_html') or preset_data.get('html', '')
            if not saved_photo:
                saved_photo = preset_data.get('photo_url') or preset_data.get('photo')
        elif isinstance(preset_data, str):
            saved_html = str(preset_data)

        if saved_html:
            formatted_html = format_preset_vars(saved_html, context_vars)
            if saved_photo:
                try:
                    await bot.send_photo(chat_id, photo=saved_photo, caption=formatted_html, parse_mode='HTML', reply_markup=reply_markup)
                    return True
                except Exception as e:
                    logger.warning(f"[PRESET] send_photo key={num_key} failed: {e}")

            try:
                await bot.send_message(chat_id, formatted_html, parse_mode='HTML', reply_markup=reply_markup)
                return True
            except Exception as e:
                logger.warning(f"[PRESET] send_message key={num_key} failed: {e}")
                try:
                    await bot.send_message(chat_id, formatted_html, reply_markup=reply_markup)
                    return True
                except Exception:
                    pass

    if fallback_text:
        formatted_fallback = format_preset_vars(fallback_text, context_vars)
        if saved_photo:
            try:
                await bot.send_photo(chat_id, photo=saved_photo, caption=formatted_fallback, parse_mode='HTML', reply_markup=reply_markup)
                return True
            except Exception:
                pass
        try:
            await bot.send_message(chat_id, formatted_fallback, parse_mode='HTML', reply_markup=reply_markup)
        except Exception:
            await bot.send_message(chat_id, formatted_fallback, reply_markup=reply_markup)
        return True
    return False

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
    
    # Row 1: Claims & Referrals for Normal Users
    markup.row(
        types.KeyboardButton(text='📋 Code đã nhận'),
        types.KeyboardButton(text='👥 Thống kê mời bạn')
    )

    # Row 2: Admin Panel & Stock Stats (ONLY IF ADMIN)
    if is_admin(user_id):
        markup.row(
            types.KeyboardButton(text='📦 Thống kê kho code'),
            types.KeyboardButton(text='⚙️ BẢNG ĐIỀU KHIỂN ADMIN')
        )

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

    default_text = (
        "<b>🎁 BẠN CẦN THAM GIA ĐẦY ĐỦ CÁC KÊNH ĐỂ NHẬN CODE MIỄN PHÍ! 🎁</b>\n\n"
        "👉 <i>Vui lòng bấm nút <b>\"🌐 THAM GIA TẤT CẢ NHÓM\"</b> bên dưới để tham gia, sau đó bấm nút <b>\"✅ KIỂM TRA\"</b> để nhận Code nhé 😘</i>"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    url = join_all_link if join_all_link else (f"https://t.me/{unjoined_groups[0].replace('@', '')}" if unjoined_groups else "https://t.me")
    markup.add(types.InlineKeyboardButton("🌐 THAM GIA TẤT CẢ NHÓM", url=url))
    markup.add(types.InlineKeyboardButton("✅ KIỂM TRA", callback_data="verify_subscription"))

    # Preset 5 → tin nhắn yêu cầu tham gia kênh
    await send_preset_or_fallback(chat_id, '5', default_text, reply_markup=markup)

async def send_welcome_message(chat_id, user_id, first_name, username):
    global _bot_me_cache
    if not _bot_me_cache:
        _bot_me_cache = await bot.get_me()

    referral_link = f"https://t.me/{_bot_me_cache.username}?start=ref_{user_id}"
    miniapp_link = "https://t.me/trainghiemtanthu88k_bot/trainghiem88k"

    default_welcome = (
        f"👋 <b>Xin chào {first_name}!</b>\n\n"
        f"🎁 <b>NHẬN CODE TRẢI NGHIỆM MIỄN PHÍ 88K</b> 🎁\n\n"
        f"👥 <b>Mời bạn bè:</b> Mời 3 người bạn tham gia & xem video → nhận thêm 1 Code miễn phí!\n"
        f"🔗 Link mời của bạn:\n<code>{referral_link}</code>\n\n"
        f"👇 Bấm nút <b>\"🎁 MỞ MINI APP NHẬN CODE 88K\"</b> ngay dưới tin nhắn này để bốc code!"
    )

    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(types.InlineKeyboardButton("🎁 MỞ MINI APP NHẬN CODE 88K", url=miniapp_link))

    ctx = {
        'first_name': first_name,
        'user_id': user_id,
        'referral_link': referral_link,
        'bot_username': _bot_me_cache.username
    }

    # Preset 1 → tin nhắn chào mừng /start
    await send_preset_or_fallback(chat_id, '1', default_welcome, reply_markup=inline_markup, context_vars=ctx)

    # Preset 2 → thay "👇 Hoặc chọn các chức năng khác bên dưới:"
    default_menu_text = "👇 Hoặc chọn các chức năng khác bên dưới:"
    await send_preset_or_fallback(chat_id, '2', default_menu_text, reply_markup=build_main_menu_keyboard(user_id), context_vars=ctx)

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
    c.execute('UPDATE gifcodes SET is_used = 0, used_by = NULL, used_at = NULL')
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

# Command Handler: /set1, /set2 ... /setN or /set 1, /set 2 (Admin set preset pre message)
@bot.message_handler(regexp=r'^/set\s*(\d+)(?:\s+([\s\S]+))?$')
async def handle_set_preset(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        await bot.send_message(message.chat.id, "⛔ Bạn không có quyền Admin!")
        return

    import re
    match = re.match(r'^/set\s*(\d+)(?:\s+([\s\S]+))?$', message.text.strip())
    if not match:
        return

    num_key = match.group(1)
    content = match.group(2)

    if content:
        cfg = load_settings()
        presets = cfg.get('presetMessages', {})
        presets[num_key] = {
            'type': 'text',
            'text_html': content.strip(),
            'html': content.strip(),
            'chat_id': message.chat.id,
            'message_id': message.message_id
        }
        cfg['presetMessages'] = presets
        save_settings(cfg)

        await bot.send_message(
            message.chat.id,
            f"✅ <b>ĐÃ LƯU TIN NHẮN MẪU SỐ {num_key}!</b>",
            parse_mode='HTML'
        )
    else:
        pending_states[message.chat.id] = {'action': 'set_preset_msg', 'key': num_key}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_home")]])
        await bot.send_message(
            message.chat.id,
            f"📝 <b>[SET {num_key}]</b> Hãy gửi tin nhắn bạn muốn lưu làm mẫu tin nhắn pre số <b>{num_key}</b>:",
            parse_mode='HTML',
            reply_markup=markup
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
        pending_states[chat_id] = {'action': 'add_codes', 'category_id': 'cat-tanthu'}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_home")]])
        await bot.edit_message_text(
            "📦 <b>NẠP CODE VÀO KHO TRỰC TIẾP:</b>\n\n"
            "📝 Hãy gửi tin nhắn chứa <b>danh sách code (mỗi dòng 1 code)</b> bên dưới để nạp trực tiếp vào kho nhé:\n\n"
            "<i>Ví dụ gửi:</i>\n"
            "<code>CODE88K-001\n"
            "CODE88K-002\n"
            "CODE88K-003</code>",
            chat_id=chat_id,
            message_id=message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    if data.startswith('admin_sel_cat_'):
        cat_id = data.replace('admin_sel_cat_', '')
        pending_states[chat_id] = {'action': 'add_codes', 'category_id': cat_id}
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Hủy", callback_data="admin_home")]])
        await bot.edit_message_text("📝 Hãy gửi tin nhắn chứa <b>danh sách code (mỗi dòng 1 code)</b>:", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data == 'admin_del_code':
        markup = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("🔥 XÓA TOÀN BỘ KHO CODE (RỖNG 0 CODE)", callback_data="admin_del_all_codes")],
            [types.InlineKeyboardButton("🗑️ Xóa 1 mã code cụ thể", callback_data="admin_del_single_prompt")],
            [types.InlineKeyboardButton("🔙 Quay lại", callback_data="admin_home")]
        ])
        await bot.edit_message_text("🗑️ <b>XÓA CODE KHỎI KHO:</b>\n\nVui lòng chọn phương thức xóa bên dưới:", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data == 'admin_del_all_codes':
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM gifcodes')
        conn.commit()
        conn.close()
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("🔙 Quay lại Admin Panel", callback_data="admin_home")]])
        await bot.edit_message_text("✅ <b>ĐÃ XÓA SẠCH TOÀN BỘ KHO CODE!</b>\n\nKho Gifcode hiện tại đã hoàn toàn rỗng (0 code).", chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=markup)
        return

    if data == 'admin_del_single_prompt':
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

    # Reply Button: "📦 Thống kê kho code" (CHỈ DÀNH CHO ADMIN)
    if text == '📦 Thống kê kho code':
        if not is_admin(user_id):
            await bot.send_message(chat_id, "⛔ Chức năng Thống Kê Kho Code chỉ dành cho Admin!")
            return

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) as avail FROM gifcodes WHERE is_used = 0')
        avail_codes = c.fetchone()['avail']
        c.execute('SELECT COUNT(*) as total FROM gifcodes')
        total_codes = c.fetchone()['total']
        c.execute('SELECT COUNT(*) as used FROM claims')
        total_claims = c.fetchone()['used']
        conn.close()

        fallback_reply = (
            f"⚙️ <b>THỐNG KÊ KHO GIFCODE (QUẢN TRỊ VIÊN)</b>\n\n"
            f"🟢 <b>Mã Code khả dụng trong kho:</b> <b>{avail_codes}</b> / {total_codes} code\n"
            f"🎁 <b>Tổng số lượt đã bốc thành công:</b> <b>{total_claims}</b> lượt\n\n"
            f"👇 <i>Dùng Bảng Quản Trị để nạp thêm code khi cần!</i>"
        )
        await send_preset_or_fallback(chat_id, '5', fallback_reply)
        return

    # Reply Button: "📋 Code đã nhận"
    if text == '📋 Code đã nhận':
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM claims WHERE user_id = ? ORDER BY claimed_at DESC LIMIT 10', (user_id,))
        claims = c.fetchall()
        conn.close()

        if not claims:
            # Preset 4 for empty Code đã nhận
            default_empty = "‼️ <b><i>Bạn chưa nhận code nào cả. Hãy mở MiniApp làm nhiệm vụ xem video nhận code ngay nào 🎉</i></b>"
            await send_preset_or_fallback(chat_id, '4', default_empty)
        else:
            reply = "🎁 <b>DANH SÁCH CODE ĐÃ NHẬN:</b>\n\n"
            for idx, item in enumerate(claims, 1):
                claimed_time = item['claimed_at'] if 'claimed_at' in item.keys() else ''
                reply += f"{idx}. <b>{item['category_name'] or 'Tân Thủ'}</b>: <code>{item['code']}</code>\n"
            await bot.send_message(chat_id, reply, parse_mode='HTML')
        return

    # Reply Button: "👥 Thống kê mời bạn"
    if text == '👥 Thống kê mời bạn':
        global _bot_me_cache
        if not _bot_me_cache:
            _bot_me_cache = await bot.get_me()

        first_name = message.from_user.first_name or 'Bạn'
        stats = get_referral_stats_db(user_id)
        ref_link = f"https://t.me/{_bot_me_cache.username}?start=ref_{user_id}"

        fallback_reply = (
            f"📊 <b>THỐNG KÊ MỜI BẠN BÈ</b>\n\n"
            f"✅ <b>Link Mời bạn bè:</b>\n<code>{ref_link}</code>\n\n"
            f"👉 Tổng đã mời: <b>{stats['total']}</b> người\n"
            f"✅ Đã tham gia & xác minh: <b>{stats['completed']}</b> người\n"
            f"⏳ Chờ xác minh: <b>{stats['pending']}</b> người\n\n"
            f"🎁 Số Code Đã Được Nhận: <b>{stats['rewardsEarned']}</b>"
        )
        ctx = {
            'first_name': first_name,
            'user_id': user_id,
            'referral_link': ref_link,
            'bot_username': _bot_me_cache.username,
            'total': stats['total'],
            'completed': stats['completed'],
            'pending': stats['pending'],
            'rewardsEarned': stats['rewardsEarned']
        }
        # Preset 3 for Thống kê mời bạn!
        await send_preset_or_fallback(chat_id, '3', fallback_reply, context_vars=ctx)
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

        if action == 'set_preset_msg':
            num_key = pending.get('key', '1')
            html_content = extract_message_html(message)
            cfg = load_settings()
            presets = cfg.get('presetMessages', {})
            presets[num_key] = {
                'type': 'text',
                'text_html': html_content,
                'html': html_content,
                'chat_id': message.chat.id,
                'message_id': message.message_id
            }
            cfg['presetMessages'] = presets
            save_settings(cfg)

            await bot.send_message(
                chat_id,
                f"✅ <b>ĐÃ LƯU TIN NHẮN MẪU SỐ {num_key}!</b>\n\nBấm nút hoặc gõ <b>{num_key}</b> để phát lại tin nhắn này bất kỳ lúc nào.",
                parse_mode='HTML'
            )
            return

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

from telebot import async_telebot as telebot

from telebot import types

import os
import re

import asyncio

import logging

from datetime import datetime, timezone, timedelta

import json

from urllib.parse import quote

import base64

import time

import random

from contextlib import asynccontextmanager

import html

import sys
import subprocess

# Optional deps: auto-install if missing (Windows VPS friendly)
def _ensure_import(module: str, pip_name: str | None = None):
    try:
        return __import__(module)
    except Exception:
        name = pip_name or module
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", name])
            return __import__(module)
        except Exception as e:
            raise ImportError(f"Missing dependency: {module}. Pip install failed for {name}: {e}")

# Third-party deps used by this bot
aiosqlite = _ensure_import("aiosqlite")
aiofiles = _ensure_import("aiofiles")
tenacity = _ensure_import("tenacity")
redis = None
try:
    redis = _ensure_import("redis")
except Exception:
    redis = None

# Tenacity symbols
retry = tenacity.retry
stop_after_attempt = tenacity.stop_after_attempt
wait_exponential = tenacity.wait_exponential
retry_if_exception_type = tenacity.retry_if_exception_type

# Configure logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)



# Helper to load config synchronously for initial setup
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def _load_initial_config():
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading initial config: {e}")
    return {}

_initial_config = _load_initial_config()

# Bot configuration - Lấy từ config.json do bot_generator.py cung cấp
API_TOKEN = _initial_config.get('bot_token') or 'YOUR_BOT_TOKEN_HERE'
bot = telebot.AsyncTeleBot(API_TOKEN)

def patch_bot_sending_methods(bot_instance):
    import re
    import html

    def strip_html_and_markdown(text):
        if not text:
            return text
        # Convert triple backticks to <pre>...</pre>
        text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
        # Convert single backticks to <code>...</code>
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        # Strip all HTML tags EXCEPT <pre>, </pre>, <code>, </code>
        text = re.sub(r'(?i)<(?!/?(?:pre|code)\b)[^>]+>', '', text)
        text = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', r'\1\2', text)
        text = re.sub(r'\*(.*?)\*|_(.*?)_', r'\1\2', text)
        text = html.unescape(text)
        return text

    orig_send_message = bot_instance.send_message
    async def new_send_message(chat_id, text, *args, **kwargs):
        if not is_premium_edition():
            text = strip_html_and_markdown(text)
            args_list = list(args)
            
            parse_mode_val = 'HTML' if (text and re.search(r'(?i)</?(?:pre|code)\b', text)) else None
            
            if len(args_list) > 0:
                args_list[0] = parse_mode_val
            else:
                kwargs['parse_mode'] = parse_mode_val
                
            if not parse_mode_val:
                if len(args_list) > 1:
                    args_list[1] = None
                kwargs['entities'] = None
                
            return await orig_send_message(chat_id, text, *args_list, **kwargs)
        return await orig_send_message(chat_id, text, *args, **kwargs)
    bot_instance.send_message = new_send_message

    orig_send_photo = bot_instance.send_photo
    async def new_send_photo(chat_id, photo, caption=None, *args, **kwargs):
        if not is_premium_edition():
            if caption:
                caption = strip_html_and_markdown(caption)
            args_list = list(args)
            
            parse_mode_val = 'HTML' if (caption and re.search(r'(?i)</?(?:pre|code)\b', caption)) else None
            
            if len(args_list) > 1:
                args_list[1] = parse_mode_val
            else:
                kwargs['parse_mode'] = parse_mode_val
                
            if not parse_mode_val:
                if len(args_list) > 2:
                    args_list[2] = None
                kwargs['caption_entities'] = None
                
            return await orig_send_photo(chat_id, photo, caption, *args_list, **kwargs)
        return await orig_send_photo(chat_id, photo, caption, *args, **kwargs)
    bot_instance.send_photo = new_send_photo

    orig_edit_message_text = bot_instance.edit_message_text
    async def new_edit_message_text(text, chat_id=None, message_id=None, inline_message_id=None, *args, **kwargs):
        if not is_premium_edition():
            text = strip_html_and_markdown(text)
            args_list = list(args)
            
            parse_mode_val = 'HTML' if (text and re.search(r'(?i)</?(?:pre|code)\b', text)) else None
            
            if len(args_list) > 0:
                args_list[0] = parse_mode_val
            else:
                kwargs['parse_mode'] = parse_mode_val
                
            if not parse_mode_val:
                if len(args_list) > 1:
                    args_list[1] = None
                kwargs['entities'] = None
                
            return await orig_edit_message_text(text, chat_id, message_id, inline_message_id, *args_list, **kwargs)
        return await orig_edit_message_text(text, chat_id, message_id, inline_message_id, *args, **kwargs)
    bot_instance.edit_message_text = new_edit_message_text

    orig_reply_to = bot_instance.reply_to
    async def new_reply_to(message, text, *args, **kwargs):
        if not is_premium_edition():
            text = strip_html_and_markdown(text)
            args_list = list(args)
            
            parse_mode_val = 'HTML' if (text and re.search(r'(?i)</?(?:pre|code)\b', text)) else None
            
            if len(args_list) > 0:
                args_list[0] = parse_mode_val
            else:
                kwargs['parse_mode'] = parse_mode_val
                
            if not parse_mode_val:
                if len(args_list) > 1:
                    args_list[1] = None
                kwargs['entities'] = None
                
            return await orig_reply_to(message, text, *args_list, **kwargs)
        return await orig_reply_to(message, text, *args, **kwargs)
    bot_instance.reply_to = new_reply_to

patch_bot_sending_methods(bot)

# Các hằng số mặc định - Sẽ được ưu tiên lấy từ config.json nếu có
NHOM_CANTHAMGIA = _initial_config.get('mb_join_channels') or []
LINK_THAM_GIA_TAT_CA = _initial_config.get('mb_all_channels_link') or ""
thattym = _initial_config.get('mb_tym_channels') or []
MIN_WITHDRAW_AMOUNT = _initial_config.get('mb_min_withdraw') or 66000
ADMINS = _initial_config.get('mb_admins') or []
GAME_WEBSITE_URL = _initial_config.get('mb_game_link') or "{link game}"
LINK_GAME_IMAGE_URL = _initial_config.get('mb_welcome_image') or ""

# Database and Redis configuration
DB_FILE = 'data/bot_data.db'

REDIS_URL = None  # Set to None to disable Redis; update to "redis://localhost:6379/0" if Redis is available

DATA_DIR = 'data'

os.makedirs(DATA_DIR, exist_ok=True)



# Vietnam timezone

VIETNAM_TZ = timezone(timedelta(hours=7))



# Async lock and Redis client

file_lock = asyncio.Lock()

redis_client = None

if REDIS_URL:

    try:

        if redis is None:
            raise RuntimeError("redis package not available")
        redis_client = redis.asyncio.from_url(REDIS_URL, decode_responses=True)

        logger.info("Connected to Redis successfully.")

    except Exception as e:

        logger.warning(f"Redis connection failed: {e}. Falling back to in-memory cache.")

        redis_client = None

else:

    logger.info("Redis disabled. Using in-memory cache.")



# In-memory admin state (tránh viết DB quá nhiều)

_admin_states: dict = {}   # {user_id: {'step': str, ...extra...}}

_mb_config_cache = {}

_mb_config_cache_time = 0

_MB_CONFIG_TTL = 120  # seconds

_bot_me_cache = None  # Cache bot info to avoid repeated get_me() API calls



async def _mb_load_config():

    """Đọc config.json (cache 30s để tránh đọc file liên tục)."""

    global _mb_config_cache, _mb_config_cache_time

    now = asyncio.get_event_loop().time()

    if now - _mb_config_cache_time < _MB_CONFIG_TTL and _mb_config_cache:

        return _mb_config_cache

    try:

        if os.path.exists(CONFIG_FILE_PATH):

            async with aiofiles.open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:

                content = await f.read()

            _mb_config_cache = json.loads(content)

            _mb_config_cache_time = now

    except Exception as e:

        logger.error(f"Error loading config: {e}")

    return _mb_config_cache



async def _mb_save_config(config: dict):

    """Ghi config.json và làm mới cache."""

    global _mb_config_cache, _mb_config_cache_time

    async with file_lock:

        try:

            async with aiofiles.open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:

                await f.write(json.dumps(config, ensure_ascii=False, indent=4))

            _mb_config_cache = config

            _mb_config_cache_time = asyncio.get_event_loop().time()

        except Exception as e:

            logger.error(f"_mb_save_config error: {e}")



async def mb_get_admins() -> list:

    """Lấy danh sách admin từ config, fallback về ADMINS hằng số."""

    cfg = await _mb_load_config()

    saved = cfg.get("mb_admins")

    if saved and isinstance(saved, list):

        return list(set(saved + ADMINS))

    return list(ADMINS)



async def mb_save_admins(admin_list: list):

    cfg = await _mb_load_config()

    cfg["mb_admins"] = admin_list

    await _mb_save_config(cfg)



async def mb_get_min_withdraw() -> int:

    cfg = await _mb_load_config()

    return int(cfg.get("mb_min_withdraw") or MIN_WITHDRAW_AMOUNT)



async def mb_save_min_withdraw(amount: int):

    cfg = await _mb_load_config()

    cfg["mb_min_withdraw"] = amount

    await _mb_save_config(cfg)



async def mb_get_game_link():

    cfg = await _mb_load_config()

    return cfg.get("mb_game_link") or GAME_WEBSITE_URL



async def mb_save_game_link(link: str):

    cfg = await _mb_load_config()

    cfg["mb_game_link"] = link

    await _mb_save_config(cfg)



async def mb_get_notify_image():
    cfg = await _mb_load_config()
    return cfg.get("mb_notify_image") or LINK_GAME_IMAGE_URL



async def mb_save_notify_image(url: str):

    cfg = await _mb_load_config()

    cfg["mb_notify_image"] = url

    await _mb_save_config(cfg)



async def mb_get_invite_reward() -> int:
    cfg = await _mb_load_config()
    return int(cfg.get("mb_invite_reward") or 10000)



async def mb_save_invite_reward(amount: int):

    cfg = await _mb_load_config()

    cfg["mb_invite_reward"] = amount

    await _mb_save_config(cfg)



def _flatten_channels(channels_list, is_tym=False):
    flat = []
    for c in channels_list:
        if isinstance(c, str):
            parts = c.replace(',', '\n').split('\n')
            for p in parts:
                p = p.strip()
                if p:
                    if is_tym and "/" not in p:
                        p = f"{p}/1"
                    if p not in flat:
                        flat.append(p)
    return flat

async def mb_get_join_channels() -> list:

    cfg = await _mb_load_config()

    saved = cfg.get("mb_join_channels")

    if saved and isinstance(saved, list) and saved:

        return _flatten_channels(saved, False)

    return _flatten_channels(list(NHOM_CANTHAMGIA), False)



async def mb_save_join_channels(channels: list):

    cfg = await _mb_load_config()

    cfg["mb_join_channels"] = _flatten_channels(channels, False)

    await _mb_save_config(cfg)



async def mb_get_tym_channels() -> list:

    cfg = await _mb_load_config()

    saved = cfg.get("mb_tym_channels")

    if saved and isinstance(saved, list) and saved:

        return _flatten_channels(saved, True)

    return _flatten_channels(list(thattym), True)



async def mb_save_tym_channels(channels: list):

    cfg = await _mb_load_config()

    cfg["mb_tym_channels"] = _flatten_channels(channels, True)

    await _mb_save_config(cfg)


_premium_texts_cache = None

def load_premium_text(key):
    global _premium_texts_cache
    if _premium_texts_cache is None:
        _premium_texts_cache = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths = [
            os.path.join(base_dir, 'keywords.json'),
            os.path.join(os.path.dirname(base_dir), 'keywords.json')
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for k, v in data.items():
                            if isinstance(v, dict) and 'text_html' in v:
                                _premium_texts_cache[k] = v['text_html']
                        break
                except Exception as e:
                    logger.error(f"Error reading {p}: {e}")
        
        fallback_texts = {
            "start": "<tg-emoji emoji-id=\"5208541126583136130\">🎉</tg-emoji> <b>Chào mừng bạn quay trở lại </b><tg-emoji emoji-id=\"5406926593698312391\">❤️</tg-emoji>\n<tg-emoji emoji-id=\"5442939099906325301\">🎁</tg-emoji> <b>Tham gia đủ kênh để nhận code cực kỳ hấp dẫn</b><tg-emoji emoji-id=\"6287284302560368766\">💥</tg-emoji>: \n<tg-emoji emoji-id=\"5409109841538994759\">🌈</tg-emoji> <b>Mời bạn nhận code siêu ngon </b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji> <b>Ko giới hạn số lần đổi code 🎊\n\n</b><tg-emoji emoji-id=\"6258053304899604813\">✅</tg-emoji> <b>Link Đăng Kí Game👇: \n</b>{link game}\n\n<tg-emoji emoji-id=\"5422761060081883523\">💙</tg-emoji> <b>Vui Lòng Đăng Kí Đúng Link Và Liên Kết Ngân Hàng Và Thực Hiện 1 Lệnh Nạp Mới Đủ Điều Kiện Nhé</b><tg-emoji emoji-id=\"6328094428971932747\">🆗</tg-emoji>\n\n<tg-emoji emoji-id=\"6255635689283523129\">🧧</tg-emoji> <b>Vui Lòng Bấm Nút Bên Dưới Để Tham Gia Nhận GIFTCODE FREE Ngay Thôi Nào!</b><tg-emoji emoji-id=\"5231102735817918643\">👇</tg-emoji>",
            "sdt": "<tg-emoji emoji-id=\"5296369303661067030\">🔒</tg-emoji> <b>XÁC MINH SỐ ĐIỆN THOẠI</b>\n\n<tg-emoji emoji-id=\"5447644880824181073\">⚠️</tg-emoji> <b>Yêu cầu tài khoản hợp lệ:</b>\n<tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji> Số điện thoại Việt Nam (+84)\n<tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji> Tên hiển thị không quá 20 ký tự\n<tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji> Có username (@)\n<tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji> Có ảnh đại diện\n<tg-emoji emoji-id=\"5416117059207572332\">➡️</tg-emoji> Nhấn nút bên dưới để chia sẻ số điện thoại:",
            "join": "<tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji> <b>Vui Lòng Tham Gia Đầy Đủ Các Kênh Và Thả Tym Rồi Bấm Xác Minh</b><tg-emoji emoji-id=\"5362081079224180363\">❤️</tg-emoji>\n\n<tg-emoji emoji-id=\"5208541126583136130\">🎉</tg-emoji> <b>Lưu Ý:</b> Phải Tham Gia Thả Tym Đầy Đủ Và Chờ 15 Giây\n\n<tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji> <b>Danh Sách Các Kênh</b><tg-emoji emoji-id=\"5231102735817918643\">👇</tg-emoji><b>:</b>",
            "done": "<tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji> <b>Xác minh số điện thoại thành công!</b>\n\n<tg-emoji emoji-id=\"5386367538735104399\">⌛</tg-emoji> Đang kiểm tra điều kiện tiếp theo...",
            "1": "<tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji> <b>Bạn Chưa Tham Gia Điểm Danh Ngày Hôm Nay </b><b><tg-emoji emoji-id=\"6287284302560368766\">💥</tg-emoji></b>\n\n<tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji> <b>Vui Lòng Bấm </b><b><tg-emoji emoji-id=\"6210875657543488483\">👉</tg-emoji></b><b> </b><b><tg-emoji emoji-id=\"5442939099906325301\">🎁</tg-emoji></b><b> Điểm danh Để Có Thể Nhận Được Giftcode Từ Bot Nhé </b><b><tg-emoji emoji-id=\"5406926593698312391\">❤️</tg-emoji></b>",
            "2": "<tg-emoji emoji-id=\"5257980374868311346\">💌</tg-emoji> <b>Mời Bạn - Rinh Code Khủng </b><b><tg-emoji emoji-id=\"5257980374868311346\">💌</tg-emoji></b><b>\n\n</b><b><tg-emoji emoji-id=\"5267102644886853973\">❤️</tg-emoji></b><b> </b><b><i>Đây là link chia sẻ của bạn! Hãy nhanh tay chia sẻ nó với bạn bè và người thân để nhận phần thưởng hấp dẫn ngay hôm nay. Đừng bỏ lỡ cơ hội này </i></b><b><i><tg-emoji emoji-id=\"5470080737711502911\">💖</tg-emoji></i></b>\n--------(<tg-emoji emoji-id=\"5051117887851333174\">⬇️</tg-emoji><tg-emoji emoji-id=\"5051117887851333174\">⬇️</tg-emoji><tg-emoji emoji-id=\"5051117887851333174\">⬇️</tg-emoji><tg-emoji emoji-id=\"5051117887851333174\">⬇️</tg-emoji><tg-emoji emoji-id=\"5051117887851333174\">⬇️</tg-emoji><tg-emoji emoji-id=\"5051117887851333174\">⬇️</tg-emoji>)--------",
            "3": "<tg-emoji emoji-id=\"5404573776253825754\">🍬</tg-emoji> <b>ĐIỂM DANH HÀNG NGÀY </b><b><tg-emoji emoji-id=\"5404573776253825754\">🍬</tg-emoji></b>\n\n<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> <b>Phần thưởng mỗi ngày:\n</b><b><tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji></b><b>  Ngày 1: 6,666 VNĐ\n</b><b><tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji></b><b> Ngày 2: 12,345 VNĐ\n</b><b><tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji></b><b> Ngày 3: 29,000 VNĐ\n</b><b><tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji></b><b> Ngày 4: 34,567 VNĐ\n</b><b><tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji></b><b> Ngày 5: 45,678 VNĐ\n</b><b><tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji></b><b> Ngày 6: 59,999 VNĐ\n</b><b><tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji></b><b> Ngày 7: 66,666-100,000 VNĐ \n(Nhận Tiền Thưởng Ngẫu Nhiên)\n\n</b><b><tg-emoji emoji-id=\"6309824960944673394\">🔥</tg-emoji></b><b> Streak hiện tại: 0/7 ngày </b><b><tg-emoji emoji-id=\"5424972470023104089\">🔥</tg-emoji></b><b>\n</b><b><tg-emoji emoji-id=\"5190806721286657692\">📊</tg-emoji></b><b> Tổng điểm danh: 0 lần\n</b><b><tg-emoji emoji-id=\"5848050864920465547\">💎</tg-emoji></b><b> Tổng thưởng: 0 VNĐ\n\n</b><b><tg-emoji emoji-id=\"5215394081911351762\">⏰</tg-emoji></b><b> Lưu ý:\n</b>• Điểm danh mỗi ngày để giữ streak\n• Bỏ lỡ 1 ngày = mất streak về 0\n• Mỗi ngày chỉ điểm danh 1 lần\n\n<b><tg-emoji emoji-id=\"5271604874419647061\">🔗</tg-emoji></b><b> Link điểm danh:\n\n</b><b><tg-emoji emoji-id=\"6230892992576626220\">📱</tg-emoji></b><b> Nhấn vào link trên hoặc nút bên dưới để điểm danh </b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b>",
            "4": "<tg-emoji emoji-id=\"5208541126583136130\">🎉</tg-emoji> <b>ĐIỂM DANH THÀNH CÔNG </b><b><tg-emoji emoji-id=\"5208541126583136130\">🎉</tg-emoji></b><b>\n\n</b><b><tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji></b><b> Phần thưởng: 0₫\n</b><b><tg-emoji emoji-id=\"5424972470023104089\">🔥</tg-emoji></b><b> Streak: 0/7 ngày\n</b><b><tg-emoji emoji-id=\"5409109841538994759\">🌈</tg-emoji></b><b> Số dư mới: 0₫\n\n</b><b><tg-emoji emoji-id=\"5465283645788937267\">💎</tg-emoji></b><b> Hãy tiếp tục điểm danh vào ngày mai để nhận thưởng lớn hơn nhé!! </b><b><tg-emoji emoji-id=\"5362081079224180363\">❤️</tg-emoji></b>",
            "5": "<tg-emoji emoji-id=\"6043992250831082249\">✅</tg-emoji> <b>Hướng Dẫn Bạn Thực Hiện Các Bước Đổi Điểm Game Tự Động</b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b><b>:</b>\n\n<tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji> <b>Ví Dụ : </b><b>/doidiem</b><b> [ Số Tiền ] \n\n</b><b><tg-emoji emoji-id=\"5361683000180351007\">⚠️</tg-emoji></b><b> CHÚ Ý KHI ĐỔI ĐIỂM </b><b><tg-emoji emoji-id=\"5361683000180351007\">⚠️</tg-emoji></b><b>\n\n</b><blockquote><b><tg-emoji emoji-id=\"5213214459023076318\">➡️</tg-emoji></b><b> Trong Vòng Ngày Tài Khoản Phải Thực Hiện 1 Lệnh Nạp 50K Tránh Quét TK Lạm Dụng Không Thể Thực Hiện Cộng Điểm CODE</b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b></blockquote>\n\n<b><tg-emoji emoji-id=\"5881824941547983497\">❌</tg-emoji></b><b> Gửi Sai Tài Khoản Game Vẫn Bị Trừ Tiền Và Không Hoàn Lại Nhé</b><b><tg-emoji emoji-id=\"6328094428971932747\">🆗</tg-emoji></b>\n\n<b><tg-emoji emoji-id=\"6057683292310737571\">🔔</tg-emoji></b><b>Cộng Điểm Thành Công : BOT Sẽ Gửi Thông Báo Đến Cho Bạn </b><b><tg-emoji emoji-id=\"5361870050301057412\">😘</tg-emoji></b>",
            "6": "<tg-emoji emoji-id=\"6258053304899604813\">✅</tg-emoji> <b>Vui Lòng Điền Tên Tài Khoản Trang Game Của Bạn Vào Đây</b><b><tg-emoji emoji-id=\"5231102735817918643\">👇</tg-emoji></b>\n\n<b><tg-emoji emoji-id=\"5260567229375724180\">✈️</tg-emoji></b><b> Nếu Chưa Có Tài Khoản Hãy Đăng Kí Tài Khoản Tại Đây Nhé</b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b><b>:</b>\n<tg-emoji emoji-id=\"6210875657543488483\">👉</tg-emoji> {link game}",
            "7": "<b><tg-emoji emoji-id=\"5449800250032143374\">🎁</tg-emoji></b><b> Hệ Thống Đã Gửi Yêu Cầu Đổi \nĐiểm Thưởng CODE Đến Với Admin\nVui Lòng Chờ Xử Lý Trong Giây Lát</b><b><tg-emoji emoji-id=\"5461151367559141950\">🎉</tg-emoji></b>\n\n<b><tg-emoji emoji-id=\"5361683000180351007\">⚠️</tg-emoji></b><b> Xin Hãy Lưu Ý </b><b><tg-emoji emoji-id=\"5361683000180351007\">⚠️</tg-emoji></b><b>: \n\n</b><b><tg-emoji emoji-id=\"6255635689283523129\">🧧</tg-emoji></b><b>Yêu Cầu Thực Hiện Nạp Tiền \nVào TK Trong Ngày Để Đảm Bảo \nCộng Điểm CODE Thành Công</b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b>\n\n<b><tg-emoji emoji-id=\"5262832270573582269\">✅</tg-emoji></b><b> Trong Thời Gian Chờ Vui Lòng\nTham Gia Nhóm Bên Dưới Và Chụp \nLịch Sử Đổi Điểm Để Hệ Thống Xác \nMinh Bạn Là Con Người Nha </b><b><tg-emoji emoji-id=\"5785412486349983037\">👍</tg-emoji></b>\nhttps://t.me/sankeokhuyenmai8386",
            "8": "<tg-emoji emoji-id=\"6287284302560368766\">💥</tg-emoji> <b>Xin Chúc Mừng Tài Khoản Games : {TK} Đã Cộng Điểm CODE Thành Công!! </b><tg-emoji emoji-id=\"5208541126583136130\">🎉</tg-emoji>\n\n<tg-emoji emoji-id=\"6327906889224951168\">🎮</tg-emoji> <b>Link Truy Cập Games </b><tg-emoji emoji-id=\"5231102735817918643\">👇</tg-emoji><b>:</b>\n<b>{link game}</b>\n\n<tg-emoji emoji-id=\"6309824960944673394\">🔥</tg-emoji> Đừng Quên Mời Bạn Bè Đổi Điểm Thưởng CODE Độc Quyền Tại: \n<tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji> <b>{bot_username}</b> <tg-emoji emoji-id=\"5220079633533250496\">👈</tg-emoji>\n\n<tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji> <b>AE Hãy Bỏ Ra Ít Phút Truy Cập Games Gửi Hình Ảnh Đã Nhận Được Code Vào Nhóm Để Lần Sau Được Xét Duyệt Code Tiếp Nha</b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji>\nhttps://t.me/sankeokhuyenmai8386",
            "9": "<tg-emoji emoji-id=\"5280915586128307520\">🎉</tg-emoji> <b>Chào Mừng Cục Dàng Bin Siêu Quậy Đã Tham Gia Bot Nhé </b><b><tg-emoji emoji-id=\"5337080053119336309\">👍</tg-emoji></b>",
            "10": "<tg-emoji emoji-id=\"5409109841538994759\">🌈</tg-emoji> <b>Bạn vừa nhận được 11,000 ᴠɴᴅ khi mời Bin Siêu Quậy tham gia</b><b><tg-emoji emoji-id=\"5406926593698312391\">❤️</tg-emoji></b>",
            "11": "<tg-emoji emoji-id=\"5258040062028822951\">🍀</tg-emoji> <b>Tài Khoản\n\n</b><b><tg-emoji emoji-id=\"5442939099906325301\">🎁</tg-emoji></b><b> Nhận Giftcode\n\n</b><b><tg-emoji emoji-id=\"5253742260054409879\">✉️</tg-emoji></b><b> Giới Thiệu Bạn Bè\n\n</b><b><tg-emoji emoji-id=\"5397782960512444700\">📌</tg-emoji></b><b> Điểm danh\n\n</b><b><tg-emoji emoji-id=\"5190806721286657692\">📊</tg-emoji></b><b> Thống Kê</b>",
            "n1": "<tg-emoji emoji-id=\"5258040062028822951\">🍀</tg-emoji> Tài Khoản",
            "n2": "<tg-emoji emoji-id=\"5442939099906325301\">🎁</tg-emoji> Nhận Giftcode",
            "n3": "<tg-emoji emoji-id=\"5253742260054409879\">✉️</tg-emoji> Giới Thiệu Bạn Bè",
            "n4": "<tg-emoji emoji-id=\"5397782960512444700\">📌</tg-emoji> Điểm danh",
            "n5": "<b><tg-emoji emoji-id=\"5190806721286657692\">📊</tg-emoji></b><b> Thống Kê</b>"
        }
        for k, v in fallback_texts.items():
            if k not in _premium_texts_cache:
                _premium_texts_cache[k] = v
                
    return _premium_texts_cache.get(key)

def is_premium_edition():
    global _mb_config_cache
    cfg = _mb_config_cache if _mb_config_cache else _initial_config
    if not cfg or 'edition' not in cfg:
        try:
            import json
            import os
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
        except Exception:
            cfg = {}
    edition = cfg.get('edition', 1)
    return edition == 2 or str(edition) == '2' or edition == 'premium'



def get_menu_button_label(key):
    key_mapping = {
        "taikhoan": "n1",
        "giftcode": "n2",
        "gioithieu": "n3",
        "diemdanh": "n4",
        "thongke": "n5"
    }
    defaults = {
        "n1": "🍀 Tài Khoản",
        "n2": "🎁 Nhận Giftcode",
        "n3": "✉️ Giới Thiệu Bạn Bè",
        "n4": "📌 Điểm danh",
        "n5": "📊 Thống Kê"
    }
    mapped_key = key_mapping.get(key, key)
    premium_text = load_premium_text(mapped_key)
    if premium_text:
        import re
        cleaned = re.sub(r'<[^>]+>', '', premium_text).strip()
        if cleaned:
            return cleaned
    return defaults.get(mapped_key, defaults.get(key))

async def mb_get_start_text():
    cfg = await _mb_load_config()
    edition = cfg.get('edition', 1)
    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
    if is_premium:
        pre_text = load_premium_text('start')
        if pre_text:
            return pre_text
    return cfg.get("mb_start_text") or "✅ Vui lòng sài lệnh /admin để vào trang admin để setup hoàn chỉnh bot để hoạt động"

async def mb_save_start_text(text: str):
    cfg = await _mb_load_config()
    cfg["mb_start_text"] = text
    await _mb_save_config(cfg)

async def mb_get_start_image():
    cfg = await _mb_load_config()
    return cfg.get("mb_start_image") or LINK_GAME_IMAGE_URL

async def mb_save_start_image(url: str):
    cfg = await _mb_load_config()
    cfg["mb_start_image"] = url
    await _mb_save_config(cfg)

async def mb_get_invite_text():
    # Hardcoded invite text (must not depend on /start text or config).
    # Keep formatting exact (line breaks) and insert the raw invite link.
    cfg = await _mb_load_config()
    edition = cfg.get('edition', 1)
    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
    if is_premium:
        pre_text = load_premium_text('2')
        if pre_text:
            return pre_text + "\n\n{invite_link}"
    return (
        "🎁 Mời Bạn - Rinh Code Khủng 🎁\n\n"
        "✨ Đây là link chia sẻ của bạn! Hãy nhanh tay chia sẻ nó với bạn bè và người thân để nhận phần thưởng hấp dẫn ngay hôm nay. Đừng bỏ lỡ cơ hội này!!\n"
        "--------(👇👇👇👇👇👇)--------\n\n"
        "{invite_link}"
    )

async def mb_save_invite_text(text: str):
    # Deprecated: invite text is hardcoded; keep function for compatibility.
    return

async def mb_get_invite_image():
    cfg = await _mb_load_config()
    return cfg.get("mb_invite_image") or LINK_GAME_IMAGE_URL

async def mb_save_invite_image(url: str):
    cfg = await _mb_load_config()
    cfg["mb_invite_image"] = url
    await _mb_save_config(cfg)


# In-memory cache as fallback if Redis is unavailable

subscribed_users_cache = set()



# In-memory cache for subscription checks

_subscription_cache = {}  # {user_id: (is_subscribed, unjoined_channels, timestamp)}

_subscription_cache_lock = asyncio.Lock()

SUBSCRIPTION_CACHE_TTL = 5  # Giảm xuống 5 giây để check liên tục gần như thời gian thực



# Task queue for handling API calls

task_queue = asyncio.Queue(maxsize=1000)



# Database connection pool

_db_pool = None

_db_lock = asyncio.Lock()



# In-memory cache for redeemable codes

_redeemable_codes_cache = None

_codes_cache_lock = asyncio.Lock()

_codes_file_mtime = 0



@asynccontextmanager

async def get_db_connection():

    """Get database connection from pool"""

    global _db_pool

    if _db_pool is None:

        async with _db_lock:

            if _db_pool is None:

                _db_pool = await aiosqlite.connect(DB_FILE)

                _db_pool.row_factory = aiosqlite.Row

    yield _db_pool



async def init_db():

    global _db_pool

    async with _db_lock:

        if _db_pool is None:

            _db_pool = await aiosqlite.connect(DB_FILE)

            _db_pool.row_factory = aiosqlite.Row

    async with get_db_connection() as conn:

        await conn.executescript('''

            CREATE TABLE IF NOT EXISTS users (

                user_id INTEGER PRIMARY KEY,

                balance INTEGER DEFAULT 0,

                registration_date REAL

            );

            CREATE TABLE IF NOT EXISTS user_states (

                user_id INTEGER PRIMARY KEY,

                state TEXT

            );

            CREATE TABLE IF NOT EXISTS captcha_message_ids (

                user_id INTEGER PRIMARY KEY,

                join_message INTEGER

            );

            CREATE TABLE IF NOT EXISTS subscribed_users (

                user_id INTEGER PRIMARY KEY

            );

            CREATE TABLE IF NOT EXISTS invited_users (

                user_id INTEGER PRIMARY KEY,

                referrer_id INTEGER

            );

            CREATE TABLE IF NOT EXISTS claimed_referrals (

                user_id INTEGER PRIMARY KEY

            );

            CREATE TABLE IF NOT EXISTS redeem_limits (
                user_id INTEGER PRIMARY KEY,
                redeem_count INTEGER DEFAULT 0,
                last_claim_date TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (

                key TEXT PRIMARY KEY,

                value INTEGER

            );

            CREATE TABLE IF NOT EXISTS daily_code_claims (

                user_id INTEGER,

                claim_date TEXT,

                PRIMARY KEY (user_id, claim_date)

            );

            CREATE TABLE IF NOT EXISTS user_reactions (

                user_id INTEGER,

                group_handle TEXT,

                reaction_date REAL,

                PRIMARY KEY (user_id, group_handle)

            );

            CREATE TABLE IF NOT EXISTS code_requests (

                request_id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                telegram_account TEXT NOT NULL,

                web_account TEXT NOT NULL,

                amount INTEGER NOT NULL,

                status TEXT DEFAULT 'pending',

                created_at REAL,

                FOREIGN KEY (user_id) REFERENCES users(user_id)

            );

            CREATE TABLE IF NOT EXISTS checkins (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                reward INTEGER NOT NULL,

                day TEXT NOT NULL,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP

            );

            CREATE TABLE IF NOT EXISTS checkin_rewards (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                streak_day INTEGER NOT NULL UNIQUE,

                reward_amount INTEGER NOT NULL,

                description TEXT,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP

            );

            INSERT OR IGNORE INTO settings (key, value) VALUES ('redeem_limit', 1);

            INSERT OR IGNORE INTO checkin_rewards (streak_day, reward_amount, description) VALUES
                (1, 500, 'Ngày đầu tiên'),
                (2, 999, 'Ngày thứ 2'),
                (3, 2500, 'Ngày thứ 3'),
                (4, 3456, 'Ngày thứ 4'),
                (5, 5555, 'Ngày thứ 5'),
                (6, 7500, 'Ngày thứ 6'),
                (7, 9999, 'Ngày thứ 7 - Quà đặc biệt!');

        ''')

        

        # Safely add columns to users table if they don't exist

        columns_to_add = [
            ('streak', 'INTEGER DEFAULT 0'),
            ('last_checkin', 'TEXT'),
            ('total_checkins', 'INTEGER DEFAULT 0'),
            ('total_rewards', 'INTEGER DEFAULT 0'),
            ('last_claim_date', 'TEXT')
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                if col_name == 'last_claim_date':
                    await conn.execute(f'ALTER TABLE redeem_limits ADD COLUMN {col_name} {col_type}')
                else:
                    await conn.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')

            except aiosqlite.OperationalError as e:

                if "duplicate column name" in str(e):

                    pass # Column already exists

                else:

                    raise e

        

        # Ensure existing rewards are updated

        await conn.executescript('''
            UPDATE checkin_rewards SET reward_amount = 500 WHERE streak_day = 1;
            UPDATE checkin_rewards SET reward_amount = 999 WHERE streak_day = 2;
            UPDATE checkin_rewards SET reward_amount = 2500 WHERE streak_day = 3;
            UPDATE checkin_rewards SET reward_amount = 3456 WHERE streak_day = 4;
            UPDATE checkin_rewards SET reward_amount = 5555 WHERE streak_day = 5;
            UPDATE checkin_rewards SET reward_amount = 7500 WHERE streak_day = 6;
            UPDATE checkin_rewards SET reward_amount = 9999 WHERE streak_day = 7;
        ''')

        # Add additional columns for web-based verification
        add_users_cols = [
            ('checked', 'INTEGER DEFAULT 0'),
            ('ip_address', 'TEXT'),
            ('referral_status', "TEXT DEFAULT 'pending'"),
            ('suspicious', 'INTEGER DEFAULT 0'),
            ('frozen', 'INTEGER DEFAULT 0'),
            ('game_username', 'TEXT'),
            ('phone_verified', 'INTEGER DEFAULT 0'),
            ('phone_number', 'TEXT')
        ]
        for col_name, col_type in add_users_cols:
            try:
                await conn.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
            except aiosqlite.OperationalError:
                pass
                
        add_invited_cols = [
            ('confirmed', 'INTEGER DEFAULT 0'),
            ('confirmation_time', 'REAL'),
            ('confirmation_message_id', 'INTEGER')
        ]
        for col_name, col_type in add_invited_cols:
            try:
                await conn.execute(f'ALTER TABLE invited_users ADD COLUMN {col_name} {col_type}')
            except aiosqlite.OperationalError:
                pass
                
        # Create additional tables for web-based verification
        await conn.executescript('''
            CREATE TABLE IF NOT EXISTS task_human_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                source_message_id INTEGER,
                created_time REAL NOT NULL,
                expires_time REAL NOT NULL,
                used INTEGER DEFAULT 0,
                used_time REAL,
                ip_address TEXT,
                processed INTEGER DEFAULT 0,
                processed_time REAL
            );
            CREATE TABLE IF NOT EXISTS user_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                UNIQUE(user_id, ip_address)
            );
            CREATE INDEX IF NOT EXISTS idx_users_ip ON users(ip_address);
            CREATE INDEX IF NOT EXISTS idx_task_human_verifications_token ON task_human_verifications(token);
            CREATE INDEX IF NOT EXISTS idx_task_human_verifications_processed ON task_human_verifications(processed);
            CREATE INDEX IF NOT EXISTS idx_user_ips_ip ON user_ips(ip_address);
            CREATE INDEX IF NOT EXISTS idx_user_ips_user ON user_ips(user_id);
        ''')

        await conn.commit()

    # Enable WAL mode for better concurrency

    async with get_db_connection() as conn:

        await conn.execute('PRAGMA journal_mode=WAL')

        await conn.execute('PRAGMA synchronous=NORMAL')

        await conn.execute('PRAGMA cache_size=10000')

        await conn.commit()



JOIN_HUMAN_VERIFY_TASK = "__join_verify_ip__"

async def generate_task_human_token(user_id, task_name, chat_id, source_message_id):
    """Tạo token xác minh con người."""
    import hashlib
    import secrets

    random_part = secrets.token_urlsafe(32)
    data = f"human:{user_id}:{task_name}:{chat_id}:{time.time()}:{random_part}"
    token = hashlib.sha256(data.encode()).hexdigest()

    current_time = time.time()
    expires_time = current_time + (10 * 60)  # 3 phút

    source_message_id = int(source_message_id) if source_message_id is not None else 0

    async with get_db_connection() as conn:
        await conn.execute(
            """INSERT INTO task_human_verifications
               (token, user_id, task_name, chat_id, source_message_id, created_time, expires_time, used, processed)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)""",
            (token, str(user_id), task_name, str(chat_id), source_message_id, current_time, expires_time)
        )
        await conn.commit()

    return token

async def build_confirm_human_url(token):
    cfg = await _mb_load_config()
    domain = cfg.get("website_domain") or "mmovip247.online"
        
    if '://' in domain:
        domain = domain.split('://', 1)[1]
        
    initial_cfg = _load_initial_config()
    bot_path = cfg.get("bot_path") or initial_cfg.get("bot_path") or ""
    protocol = 'http' if domain.endswith('.test') or domain.endswith('.local') or 'localhost' in domain or '127.0.0.1' in domain else 'https'
    
    if bot_path:
        return f"{protocol}://{domain}/{bot_path}/confirm_human.php?token={token}"
    return f"{protocol}://{domain}/confirm_human.php?token={token}"

async def update_user_ip(user_id, ip_address):
    if not ip_address or ip_address.upper() == "UNKNOWN":
        return
    async with get_db_connection() as conn:
        await conn.execute(
            "UPDATE users SET ip_address = ? WHERE user_id = ?",
            (ip_address, str(user_id))
        )
        now = time.time()
        await conn.execute(
            """INSERT OR REPLACE INTO user_ips (user_id, ip_address, first_seen, last_seen)
               VALUES (?, ?, COALESCE((SELECT first_seen FROM user_ips WHERE user_id = ? AND ip_address = ?), ?), ?)""",
            (str(user_id), ip_address, str(user_id), ip_address, now, now)
        )
        await conn.commit()

async def initialize_data():

    await init_db()

    # Generate bot_username.txt for PHP script and cache bot info
    global _bot_me_cache
    try:
        _bot_me_cache = await bot.get_me()
        async with aiofiles.open('bot_username.txt', 'w', encoding='utf-8') as f:
            await f.write(_bot_me_cache.username)
        logger.info(f"Generated bot_username.txt with username: {_bot_me_cache.username}")
    except Exception as e:
        logger.error(f"Failed to generate bot_username.txt: {e}")

    # Populate in-memory cache if Redis is unavailable

    if redis_client is None:

        async with get_db_connection() as conn:

            async with conn.execute('SELECT user_id FROM subscribed_users') as cursor:

                rows = await cursor.fetchall()

                global subscribed_users_cache

                subscribed_users_cache = {row['user_id'] for row in rows}

    # Load redeemable codes into cache

    await refresh_redeemable_codes_cache()



# Database operations

async def initialize_user(user_id):

    async with get_db_connection() as conn:

        await conn.execute(

            'INSERT OR IGNORE INTO users (user_id, balance, registration_date) VALUES (?, 0, ?)',

            (user_id, datetime.now(VIETNAM_TZ).timestamp())

        )

        await conn.commit()



async def get_balance(user_id):

    async with get_db_connection() as conn:

        async with conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)) as cursor:

            result = await cursor.fetchone()

            return result['balance'] if result else 0



async def update_user_balance(user_id, amount):

    await initialize_user(user_id)

    async with get_db_connection() as conn:

        await conn.execute(

            'UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?',

            (amount, user_id)

        )

        await conn.commit()



async def set_user_state(user_id, state):

    async with get_db_connection() as conn:

        await conn.execute(

            'INSERT OR REPLACE INTO user_states (user_id, state) VALUES (?, ?)',

            (user_id, state)

        )

        await conn.commit()



async def get_user_state(user_id):

    async with get_db_connection() as conn:

        async with conn.execute('SELECT state FROM user_states WHERE user_id = ?', (user_id,)) as cursor:

            result = await cursor.fetchone()

            return result['state'] if result else None



async def remove_user_state(user_id):

    async with get_db_connection() as conn:

        await conn.execute('DELETE FROM user_states WHERE user_id = ?', (user_id,))

        await conn.commit()



async def set_captcha_message_ids(user_id, join_message_id=None):

    async with get_db_connection() as conn:

        await conn.execute(

            'INSERT OR REPLACE INTO captcha_message_ids (user_id, join_message) VALUES (?, ?)',

            (user_id, join_message_id)

        )

        await conn.commit()

async def add_verification_message_id(user_id, message_id):
    async with get_db_connection() as conn:
        async with conn.execute("SELECT join_message FROM captcha_message_ids WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        
        if row and row['join_message']:
            val = str(row['join_message'])
            ids = [x.strip() for x in val.split(',') if x.strip()]
            if str(message_id) not in ids:
                ids.append(str(message_id))
            new_val = ",".join(ids)
        else:
            new_val = str(message_id)
            
        await conn.execute(
            'INSERT OR REPLACE INTO captcha_message_ids (user_id, join_message) VALUES (?, ?)',
            (user_id, new_val)
        )
        await conn.commit()




async def get_captcha_message_ids(user_id):

    async with get_db_connection() as conn:

        async with conn.execute('SELECT join_message FROM captcha_message_ids WHERE user_id = ?', (user_id,)) as cursor:

            result = await cursor.fetchone()

            return {'join_message': result['join_message']} if result else {}



async def remove_captcha_message_ids(user_id):

    async with get_db_connection() as conn:

        await conn.execute('DELETE FROM captcha_message_ids WHERE user_id = ?', (user_id,))

        await conn.commit()



async def add_subscribed_user(user_id):

    async with get_db_connection() as conn:

        await conn.execute('INSERT OR IGNORE INTO subscribed_users (user_id) VALUES (?)', (user_id,))

        await conn.commit()

    if redis_client:

        await redis_client.sadd('subscribed_users', user_id)

    else:

        subscribed_users_cache.add(user_id)



async def is_subscribed_user(user_id):

    if redis_client:

        return await redis_client.sismember('subscribed_users', user_id)

    return user_id in subscribed_users_cache



async def get_total_users():

    async with get_db_connection() as conn:

        async with conn.execute('SELECT COUNT(*) as count FROM users') as cursor:

            result = await cursor.fetchone()

            return result['count']



async def add_invited_user(user_id, referrer_id):

    async with get_db_connection() as conn:

        # Only add if not already claimed or invited

        if not await is_claimed_referral(user_id):

            await conn.execute(

                'INSERT OR IGNORE INTO invited_users (user_id, referrer_id) VALUES (?, ?)',

                (user_id, referrer_id)

            )

            await conn.commit()



async def get_referrer(user_id):

    async with get_db_connection() as conn:

        async with conn.execute('SELECT referrer_id FROM invited_users WHERE user_id = ?', (user_id,)) as cursor:

            result = await cursor.fetchone()

            return result['referrer_id'] if result else None



async def get_invited_users(referrer_id):

    async with get_db_connection() as conn:

        async with conn.execute('SELECT user_id FROM invited_users WHERE referrer_id = ?', (referrer_id,)) as cursor:

            invited = [row['user_id'] for row in await cursor.fetchall()]

        async with conn.execute('SELECT user_id FROM claimed_referrals WHERE user_id IN (SELECT user_id FROM invited_users WHERE referrer_id = ?)', (referrer_id,)) as cursor:

            joined = [row['user_id'] for row in await cursor.fetchall()]

        return invited, joined



async def add_claimed_referral(user_id):
    async with get_db_connection() as conn:
        try:
            await conn.execute('INSERT INTO claimed_referrals (user_id) VALUES (?)', (user_id,))
            await conn.commit()
            return True
        except Exception:
            return False



async def is_claimed_referral(user_id):

    async with get_db_connection() as conn:

        async with conn.execute('SELECT 1 FROM claimed_referrals WHERE user_id = ?', (user_id,)) as cursor:

            return bool(await cursor.fetchone())



async def get_redeem_count(user_id):
    """Lấy số lần user đã nhận code trong ngày hôm nay."""
    today = datetime.now(VIETNAM_TZ).strftime('%Y-%m-%d')
    async with get_db_connection() as conn:
        async with conn.execute('SELECT redeem_count, last_claim_date FROM redeem_limits WHERE user_id = ?', (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result and result['last_claim_date'] == today:
                return result['redeem_count']
            return 0

async def increment_redeem_count(user_id):
    """Tăng số lần user đã nhận code trong ngày hôm nay."""
    today = datetime.now(VIETNAM_TZ).strftime('%Y-%m-%d')
    async with get_db_connection() as conn:
        async with conn.execute('SELECT redeem_count, last_claim_date FROM redeem_limits WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await conn.execute(
                'INSERT INTO redeem_limits (user_id, redeem_count, last_claim_date) VALUES (?, 1, ?)',
                (user_id, today)
            )
        else:
            if row['last_claim_date'] == today:
                await conn.execute(
                    'UPDATE redeem_limits SET redeem_count = redeem_count + 1 WHERE user_id = ?',
                    (user_id,)
                )
            else:
                await conn.execute(
                    'UPDATE redeem_limits SET redeem_count = 1, last_claim_date = ? WHERE user_id = ?',
                    (today, user_id)
                )
        await conn.commit()



async def get_redeem_limit():

    async with get_db_connection() as conn:

        async with conn.execute('SELECT value FROM settings WHERE key = ?', ('redeem_limit',)) as cursor:

            result = await cursor.fetchone()

            return result['value'] if result else 1



async def set_redeem_limit(limit):

    async with get_db_connection() as conn:

        await conn.execute(

            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',

            ('redeem_limit', limit)

        )

        await conn.commit()



async def refresh_redeemable_codes_cache():

    """Refresh the in-memory cache of redeemable codes"""

    global _redeemable_codes_cache, _codes_file_mtime

    codes_file = os.path.join(DATA_DIR, 'redeemable_codes.txt')

    try:

        if os.path.exists(codes_file):

            mtime = os.path.getmtime(codes_file)

            if mtime != _codes_file_mtime:

                async with aiofiles.open(codes_file, 'r', encoding='utf-8') as f:

                    content = await f.read()

                    codes = [line.strip() for line in content.splitlines() if line.strip()]

                    async with _codes_cache_lock:

                        _redeemable_codes_cache = codes

                        _codes_file_mtime = mtime

                    logger.info(f"Refreshed cache with {len(codes)} redeemable codes")

        else:

            async with _codes_cache_lock:

                _redeemable_codes_cache = []

                _codes_file_mtime = 0

    except Exception as e:

        logger.error(f"Failed to refresh redeemable codes cache: {e}")



async def load_redeemable_codes():

    """Load redeemable codes from cache, refresh if needed"""

    codes_file = os.path.join(DATA_DIR, 'redeemable_codes.txt')

    

    # Check if file was modified

    if os.path.exists(codes_file):

        mtime = os.path.getmtime(codes_file)

        if mtime != _codes_file_mtime:

            await refresh_redeemable_codes_cache()

    

    async with _codes_cache_lock:

        if _redeemable_codes_cache is None:

            await refresh_redeemable_codes_cache()

        return _redeemable_codes_cache.copy() if _redeemable_codes_cache else []



async def save_redeemable_codes(codes):

    """Save redeemable codes to file and update cache"""

    codes_file = os.path.join(DATA_DIR, 'redeemable_codes.txt')

    async with file_lock:

        try:

            async with aiofiles.open(codes_file, 'w', encoding='utf-8') as f:

                await f.write('\n'.join(codes) + '\n')

            # Update cache

            async with _codes_cache_lock:

                global _redeemable_codes_cache, _codes_file_mtime

                _redeemable_codes_cache = codes.copy()

                if os.path.exists(codes_file):

                    _codes_file_mtime = os.path.getmtime(codes_file)

            logger.info(f"Saved {len(codes)} redeemable codes to {codes_file}")

        except Exception as e:

            logger.error(f"Failed to save redeemable codes to {codes_file}: {e}")



async def has_claimed_code_today(user_id):

    """Kiểm tra user đã nhận code hôm nay chưa"""

    today = datetime.now(VIETNAM_TZ).strftime('%Y-%m-%d')

    async with get_db_connection() as conn:

        async with conn.execute(

            'SELECT 1 FROM daily_code_claims WHERE user_id = ? AND claim_date = ?',

            (user_id, today)

        ) as cursor:

            return bool(await cursor.fetchone())



async def add_daily_code_claim(user_id):

    """Lưu lại việc user nhận code hôm nay"""

    today = datetime.now(VIETNAM_TZ).strftime('%Y-%m-%d')

    async with get_db_connection() as conn:

        await conn.execute(

            'INSERT OR IGNORE INTO daily_code_claims (user_id, claim_date) VALUES (?, ?)',

            (user_id, today)

        )

        await conn.commit()



async def create_code_request(user_id, telegram_account, web_account, amount):

    """Tạo yêu cầu đổi code mới"""

    async with get_db_connection() as conn:

        cursor = await conn.execute(

            'INSERT INTO code_requests (user_id, telegram_account, web_account, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',

            (user_id, telegram_account, web_account, amount, 'pending', datetime.now(VIETNAM_TZ).timestamp())

        )

        await conn.commit()

        return cursor.lastrowid



async def get_code_request(request_id):

    """Lấy thông tin yêu cầu đổi code"""

    async with get_db_connection() as conn:

        async with conn.execute('SELECT * FROM code_requests WHERE request_id = ?', (request_id,)) as cursor:

            result = await cursor.fetchone()

            return dict(result) if result else None



async def update_code_request_status(request_id, status):

    """Cập nhật trạng thái yêu cầu đổi code"""

    async with get_db_connection() as conn:

        await conn.execute(

            'UPDATE code_requests SET status = ? WHERE request_id = ?',

            (status, request_id)

        )

        await conn.commit()



async def get_pending_requests_by_web_account(web_account):

    """Tìm tất cả các yêu cầu đang chờ xử lý theo tên tài khoản web"""

    async with get_db_connection() as conn:

        async with conn.execute(

            'SELECT request_id FROM code_requests WHERE web_account = ? AND status = ?',

            (web_account.strip(), 'pending')

        ) as cursor:

            rows = await cursor.fetchall()

            return [row['request_id'] for row in rows]



async def approve_request_internal(request_id):

    """Logic xử lý duyệt yêu cầu đổi code (dùng chung cho nút bấm và lệnh nhanh)"""

    request = await get_code_request(request_id)

    if not request or request['status'] != 'pending':

        return False, "Yêu cầu không hợp lệ hoặc đã xử lý", None



    user_id = request['user_id']

    amount = request['amount']

    web_account = request['web_account']



    await increment_redeem_count(user_id)

    await add_daily_code_claim(user_id)

    await update_code_request_status(request_id, 'approved')



    # Thông báo cho user
    game_link = await mb_get_game_link()
    bot_info = _bot_me_cache if _bot_me_cache else await bot.get_me()
    bot_username = f"@{bot_info.username}"
    bot_link = f"https://t.me/{bot_info.username}"
    image_url = await mb_get_notify_image()

    cfg_temp = await _mb_load_config()
    edition = cfg_temp.get('edition', 1)
    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
    success_notif = None
    if is_premium:
        success_notif = load_premium_text('8')
    if success_notif:
        success_notif = success_notif.replace("{TK}", str(web_account))
        success_notif = success_notif.replace("{link game}", game_link)
        success_notif = success_notif.replace("{bot_username}", bot_username)
        success_notif = success_notif.replace("{bot_link}", bot_link)
        caption = success_notif
    else:
        caption = (

            f"🎊 <b>Xin Chúc Mừng Tài Khoản Games : {web_account} Đã Cộng Điểm CODE Thành Công!! 🎉</b>\n\n"

            f"🎮 <b>Link Truy Cập Games 👇:</b>\n"

            f"<b>{game_link}</b>\n\n"

            f"🔥 Đừng Quên Mời Bạn Bè Đổi Điểm Thưởng CODE Độc Quyền Tại: \n"

            f"👉 <b>{bot_username}</b> 👈\n\n"

            f"✈️  <b>AE Hãy Bỏ Ra Ít Phút Truy Cập Games Gửi Hình Ảnh Đã Nhận Được Code Vào Nhóm Để Lần Sau Được Xét Duyệt Code Tiếp Nha‼️</b>\n"

            "https://t.me/sankeokhuyenmai8386\n\n"
        )



    notification_sent = False

    try:
        if image_url:
            await bot.send_photo(user_id, image_url, caption=caption, parse_mode='HTML')
        else:
            await bot.send_message(user_id, caption, parse_mode='HTML')
        notification_sent = True
    except Exception as e:

        logger.warning(f"Failed to send photo to user {user_id}: {e}")

        try:

            await bot.send_message(user_id, caption, parse_mode='HTML')

            notification_sent = True

        except Exception as e2:

            logger.error(f"Failed to notify user {user_id}: {e2}")

            # Thông báo lỗi cho admin

            error_msg = (

                f"⚠️ <b>LỖI GỬI THÔNG BÁO:</b>\n"

                f"User ID: {user_id}\nWeb: {web_account}\nLỗi: {str(e2)}"

            )

            current_admins = await mb_get_admins()

            for admin_id in current_admins:

                try: await bot.send_message(admin_id, error_msg, parse_mode='HTML')

                except: pass

    

    return True, None, notification_sent

async def reject_request_internal(request_id):
    """Logic xử lý từ chối yêu cầu đổi code (dùng chung cho nút bấm và duyệt nhanh)"""
    request = await get_code_request(request_id)
    if not request or request['status'] != 'pending':
        return False, "Yêu cầu không hợp lệ hoặc đã xử lý"

    user_id = request['user_id']
    amount = request['amount']
    web_account = request['web_account']

    # Hoàn tiền lại cho user
    await update_user_balance(user_id, amount)
    await update_code_request_status(request_id, 'rejected')
    
    notification_sent = False
    try:
        await bot.send_message(
            user_id,
            f"❌ Yêu cầu đổi code của bạn ({web_account}) đã bị từ chối. Số tiền {amount:,} VND đã được hoàn lại vào tài khoản của bạn."
        )
        notification_sent = True
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")
    
    return True, "Đã từ chối và hoàn tiền", notification_sent



# ============================================

# ========== CHECK-IN FUNCTIONS ==============

# ============================================



async def get_checkin_reward(streak_day):

    """Lấy phần thưởng điểm danh theo ngày streak"""

    import random

    if streak_day == 7:

        # Ngày 7 random từ 66,666 đến 100,000

        return random.randint(66666, 100000)

    

    async with get_db_connection() as conn:

        async with conn.execute(

            'SELECT reward_amount FROM checkin_rewards WHERE streak_day = ?',

            (streak_day,)

        ) as cursor:

            result = await cursor.fetchone()

            return result['reward_amount'] if result else 0



async def get_user_checkin_status(user_id):

    """Lấy trạng thái điểm danh của user"""

    async with get_db_connection() as conn:

        async with conn.execute(

            'SELECT streak, last_checkin, total_checkins, total_rewards FROM users WHERE user_id = ?',

            (user_id,)

        ) as cursor:

            result = await cursor.fetchone()

            if result:

                return {

                    'streak': result['streak'] or 0,

                    'last_checkin': result['last_checkin'],

                    'total_checkins': result['total_checkins'] or 0,

                    'total_rewards': result['total_rewards'] or 0

                }

            return {'streak': 0, 'last_checkin': None, 'total_checkins': 0, 'total_rewards': 0}



async def check_and_reset_streak(user_id):

    """Kiểm tra và reset streak nếu quá 1 ngày không điểm danh"""

    status = await get_user_checkin_status(user_id)

    if not status['last_checkin']:

        return status['streak']

    

    try:

        last_checkin_date = datetime.strptime(status['last_checkin'], '%Y-%m-%d').date()

        today = datetime.now(VIETNAM_TZ).date()

        days_diff = (today - last_checkin_date).days

        

        # Nếu quá 1 ngày không điểm danh, reset streak về 0

        if days_diff > 1:

            async with get_db_connection() as conn:

                await conn.execute(

                    'UPDATE users SET streak = 0 WHERE user_id = ?',

                    (user_id,)

                )

                await conn.commit()

            return 0

    except Exception as e:

        logger.error(f"Error checking streak: {e}")

        return 0

    

    return status['streak']



async def can_checkin_today(user_id):

    """Kiểm tra user đã điểm danh hôm nay chưa"""

    today = datetime.now(VIETNAM_TZ).strftime('%Y-%m-%d')

    status = await get_user_checkin_status(user_id)

    return status['last_checkin'] != today



async def process_checkin(user_id):

    """Xử lý điểm danh cho user"""

    # Kiểm tra đã điểm danh hôm nay chưa

    if not await can_checkin_today(user_id):

        return {'success': False, 'message': '❌ Bạn đã điểm danh hôm nay rồi!'}

    

    # Kiểm tra và reset streak nếu cần

    current_streak = await check_and_reset_streak(user_id)

    

    # Tăng streak lên 1

    new_streak = current_streak + 1

    if new_streak > 7:

        new_streak = 1  # Reset về ngày 1 sau khi hoàn thành 7 ngày

    

    # Lấy phần thưởng

    reward = await get_checkin_reward(new_streak)

    

    # Cập nhật database

    today = datetime.now(VIETNAM_TZ).strftime('%Y-%m-%d')

    async with get_db_connection() as conn:

        # Cập nhật users table

        await conn.execute(

            '''UPDATE users SET 

               streak = ?, 

               last_checkin = ?, 

               total_checkins = total_checkins + 1,

               total_rewards = total_rewards + ?,

               balance = balance + ?

               WHERE user_id = ?''',

            (new_streak, today, reward, reward, user_id)

        )

        

        # Thêm vào bảng checkins

        await conn.execute(

            'INSERT INTO checkins (user_id, reward, day) VALUES (?, ?, ?)',

            (user_id, reward, today)

        )

        

        await conn.commit()

    

    new_balance = 0
    async with get_db_connection() as conn:
        async with conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                new_balance = row['balance']

    cfg_temp = await _mb_load_config()
    edition = cfg_temp.get('edition', 1)
    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
    message_text = None
    if is_premium:
        message_text = load_premium_text('4')
    
    if message_text:
        message_text = message_text.replace("Phần thưởng: 0₫", f"Phần thưởng: {reward:,}₫")
        message_text = message_text.replace("Streak: 0/7 ngày", f"Streak: {new_streak}/7 ngày")
        message_text = message_text.replace("Số dư mới: 0₫", f"Số dư mới: {new_balance:,}₫")
    else:
        message_text = f'🎉 Điểm danh thành công!\n💰 Bạn nhận được {reward:,} VNĐ\n🔥 Streak hiện tại: {new_streak}/7 ngày'

    return {

        'success': True,

        'streak': new_streak,

        'reward': reward,

        'message': message_text

    }



async def get_checkin_history(user_id, limit=7):

    """Lấy lịch sử điểm danh của user"""

    async with get_db_connection() as conn:

        async with conn.execute(

            'SELECT reward, day, created_at FROM checkins WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',

            (user_id, limit)

        ) as cursor:

            result = await cursor.fetchall()

            return [{'reward': row['reward'], 'day': row['day'], 'created_at': row['created_at']} for row in result]

async def reset_weekly_checkins():
    """Reset streak về 0 cho tất cả users sau ngày Chủ Nhật"""
    try:
        async with get_db_connection() as conn:
            await conn.execute('UPDATE users SET streak = 0')
            await conn.commit()
        logger.info("Successfully reset weekly checkin streaks for all users.")
    except Exception as e:
        logger.error(f"Error resetting weekly checkins: {e}")



# Subscription check with caching and rate limiting

_subscription_semaphore = asyncio.Semaphore(5)  # Giới hạn 5 concurrent checks



@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=3), retry=retry_if_exception_type(Exception))

async def check_channel(channel, user_id):

    async with _subscription_semaphore:

        try:

            # Thêm timeout để tránh đơ

            member = await asyncio.wait_for(

                bot.get_chat_member(channel, user_id),

                timeout=10.0

            )

            return channel, member.status in ['member', 'administrator', 'creator']

        except asyncio.TimeoutError:

            logger.warning(f"Timeout checking channel {channel} for user {user_id}")

            raise # Trình retry sẽ xử lý

        except Exception as e:

            err_msg = str(e).lower()

            if "user not found" in err_msg or "member_invalid" in err_msg:

                return channel, False

            if "chat not found" in err_msg or "bot_kicked" in err_msg:

                logger.error(f"Bot không có quyền check kênh {channel}: {e}")

                print(f"❌ [LỖI BOT] Bot không có quyền check kênh/nhóm {channel}. Hãy chắc chắn bot đã được thêm làm Admin tại đó!")

                return channel, False

            logger.error(f"Error checking channel {channel} for user {user_id}: {e}")

            raise # Trình retry sẽ xử lý



async def check_subscription(user_id, channels=None, force_refresh=False):
    if channels is None: channels = await mb_get_join_channels()
    target_channels = channels
    current_time = datetime.now(VIETNAM_TZ).timestamp()

    

    # Chỉ cache cho danh sách mặc định NHOM_CANTHAMGIA

    is_default = (target_channels == NHOM_CANTHAMGIA)

    

    # Cache key dựa trên user_id VÀ danh sách channels để tránh stale kết quả khi đổi bước

    channels_hash = ",".join(sorted(target_channels))

    cache_key = f"sub:{user_id}:{channels_hash}"

    

    # Kiểm tra in-memory cache trước

    if not force_refresh:

        async with _subscription_cache_lock:

            if cache_key in _subscription_cache:

                is_subscribed, unjoined_channels, cache_time = _subscription_cache[cache_key]

                if current_time - cache_time < SUBSCRIPTION_CACHE_TTL:

                    return is_subscribed, unjoined_channels

    

    # Kiểm tra Redis cache

    if redis_client and not force_refresh:

        try:

            redis_key = f"subscription:{user_id}:{hash(channels_hash)}"

            cached = await redis_client.get(redis_key)

            if cached:

                result = json.loads(cached)

                # Cập nhật in-memory cache

                async with _subscription_cache_lock:

                    _subscription_cache[cache_key] = (*result, current_time)

                return result

        except Exception as e:

            logger.warning(f"Redis cache error: {e}")



    # Thực hiện check thực tế

    try:

        async def check_single_channel(channel):

            return await check_channel(channel, user_id)



        # Check tất cả channels với timeout tổng thể

        results = await asyncio.wait_for(

            asyncio.gather(*(check_single_channel(channel) for channel in target_channels), return_exceptions=True),

            timeout=30.0

        )

        

        # Xử lý kết quả

        unjoined_channels = []

        for i, result in enumerate(results):

            if isinstance(result, Exception):

                logger.warning(f"Exception checking channel {target_channels[i]}: {result}")

                unjoined_channels.append(target_channels[i])

            else:

                channel, joined = result

                if not joined:

                    unjoined_channels.append(channel)

        

        is_subscribed = not unjoined_channels



        # Lưu vào cache

        if redis_client:

            try:

                redis_key = f"subscription:{user_id}:{hash(channels_hash)}"

                await redis_client.setex(redis_key, SUBSCRIPTION_CACHE_TTL, json.dumps((is_subscribed, unjoined_channels)))

            except Exception as e:

                logger.warning(f"Failed to cache in Redis: {e}")

        

        async with _subscription_cache_lock:

            _subscription_cache[cache_key] = (is_subscribed, unjoined_channels, current_time)

        

        return is_subscribed, unjoined_channels

        

    except asyncio.TimeoutError:

        logger.error(f"Timeout checking subscription for user {user_id}")

        return False, target_channels.copy()

    except Exception as e:

        logger.error(f"Error checking subscription for user {user_id}: {e}")

        return False, target_channels.copy()



async def ensure_user_verified(chat_id, user_id):
    """Đảm bảo user đã hoàn thành TẤT CẢ các bước xác minh"""
    # Check checked in DB
    async with get_db_connection() as conn:
        async with conn.execute("SELECT checked, phone_verified FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row['checked'] == 1:
                if not await is_subscribed_user(user_id):
                    await add_subscribed_user(user_id)
                return True

            if not row or not row['phone_verified']:
                markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
                markup.add(types.KeyboardButton("📱 CHIA SẺ SỐ ĐIỆN THOẠI", request_contact=True))
                try:
                    cfg = await _mb_load_config()
                    edition = cfg.get('edition', 1)
                    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
                    sdt_text = load_premium_text('sdt') if is_premium else None
                    
                    sent_msg = None
                    if sdt_text:
                        sent_msg = await bot.send_message(
                            chat_id,
                            sdt_text,
                            reply_markup=markup,
                            parse_mode='HTML'
                        )
                    else:
                        sent_msg = await bot.send_message(
                            chat_id,
                            "⚠️ **XÁC MINH SỐ ĐIỆN THOẠI**\n\n"
                            "👉 Để tiếp tục sử dụng Bot, vui lòng nhấn vào nút **📱 CHIA SẺ SỐ ĐIỆN THOẠI** bên dưới để xác minh tài khoản.\n\n"
                            "*(Chỉ chấp nhận số điện thoại Việt Nam đầu số +84)*",
                            reply_markup=markup,
                            parse_mode='Markdown'
                        )
                    if sent_msg:
                        await add_verification_message_id(chat_id, sent_msg.message_id)
                except Exception as e:
                    logger.error(f"Failed to send verify phone message: {e}")
                return False

    join_channels = await mb_get_join_channels()
    tym_channels = await mb_get_tym_channels()
    
    # Nếu không có kênh nào bắt buộc, tự động xác minh và checked = 1
    if not join_channels and not tym_channels:
        if not await is_subscribed_user(user_id):
            await add_subscribed_user(user_id)
        async with get_db_connection() as conn:
            await conn.execute("UPDATE users SET checked = 1, referral_status = 'confirmed' WHERE user_id = ?", (str(user_id),))
            await conn.commit()
        return True

    # 1. Check join các kênh bắt buộc
    is_subscribed, unjoined_channels = await check_subscription(user_id, channels=join_channels)
    if not is_subscribed:
        await show_join_channels_message(chat_id, unjoined_channels)
        return False
    
    # 2. Check đã hoàn thành thả tym (đã được lưu vào DB)
    if tym_channels:
        missing_reactions = []
        for item in tym_channels:
            handle, loai = item.split('/')
            handle = handle.lower() # Chuẩn hóa handle
            if loai == '2': # Group cần check logic
                if not await check_user_reaction_db(user_id, handle):
                    missing_reactions.append(handle)
        if missing_reactions:
            await show_reaction_verification_message(chat_id)
            return False

    # 3. Đang chờ xác minh web
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT token FROM task_human_verifications WHERE user_id = ? AND task_name = ? AND used = 0 AND expires_time > ? LIMIT 1",
            (str(user_id), JOIN_HUMAN_VERIFY_TASK, time.time())
        ) as cursor:
            row = await cursor.fetchone()
            
    if row:
        token = row['token']
    else:
        token = await generate_task_human_token(user_id, JOIN_HUMAN_VERIFY_TASK, chat_id, 0)
        
    confirm_url = await build_confirm_human_url(token)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ XÁC MINH — KHÔNG PHẢI ROBOT", url=confirm_url))
    sent_msg = await bot.send_message(
        chat_id,
        "⚠️ **Tài khoản của bạn chưa được kích hoạt!**\n\n"
        "👉 Vui lòng nhấn nút Xác Minh dưới đây để kích hoạt tài khoản qua web nhé 😘",
        reply_markup=markup,
        parse_mode='Markdown'
    )
    await add_verification_message_id(chat_id, sent_msg.message_id)
    async with get_db_connection() as conn:
        await conn.execute("UPDATE task_human_verifications SET source_message_id = ? WHERE token = ?", (sent_msg.message_id, token))
        await conn.commit()
    return False



async def show_join_channels_message(chat_id, channels):
    # channels ở đây là danh sách các kênh CHƯA tham gia
    channel_list_text = "\n".join(channels)

    cfg = await _mb_load_config()
    edition = cfg.get('edition', 1)
    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
    join_text = load_premium_text('join') if is_premium else None

    if join_text:
        if "{channels}" in join_text:
            text = join_text.replace("{channels}", channel_list_text)
        else:
            text = f"{join_text}\n{channel_list_text}"
    else:
        text = (
            "<b>🎁 Bạn Cần Tham Gia Đầy Đủ Các Kênh Bên Dưới Để Nhận Code Miễn Phí Tại TRANG GAME Ngay Hôm Nay‼️</b>\n\n"
            f"<b>Các kênh còn thiếu:</b>\n{channel_list_text}\n\n"
            "👉 Lưu ý: Bạn Vui Lòng Tham Gia Đầy Đủ Các Kênh Ở Trên!!\n"
            "-------------(/////)--------------\n"
            "<b>✅ Sau Khi Tham Gia Xong, Vui Lòng Nhấn Nút (KIỂM TRA) Để Nhận Mã Code Trị Giá 66K Nhé 😘️</b>"
        )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("✅ KIỂM TRA", callback_data="verify_subscription"))
    try:
        sent_message = await bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        await add_verification_message_id(chat_id, sent_message.message_id)
        return sent_message
    except Exception as e:
        logger.error(f"Failed to send join channels message to {chat_id}: {e}")
        return None



async def show_reaction_verification_message(chat_id):

    """Hiển thị yêu cầu thả tym nhóm"""

    text = (

        "‼️ Vui Lòng Vào Tham Gia Các Kênh Dưới Đây Và Ấn Thả ❤️ Tin Nhắn Để Xác Minh Là Con Người :\n"

        "-------------------------------------\n"

        "✅ Sau Khi Tham Gia Và Thả Tym Đủ Thì AE Bấm Nút Xác Minh Bên Dưới Nhé😘"

    )

    

    markup = types.InlineKeyboardMarkup(row_width=2)

    

    # Hiển thị lại nút ở phần tym

    buttons = []

    tym_channels = await mb_get_tym_channels()
    for i, item in enumerate(tym_channels):

        handle = item.split('/')[0]

        url = f"https://t.me/{handle.replace('@', '')}"

        buttons.append(types.InlineKeyboardButton(f"🔗 Nhóm {i+1}", url=url))

    

    if buttons:

        markup.add(*buttons)

        

    markup.add(types.InlineKeyboardButton("✅ XÁC MINH ĐÃ TYM", callback_data="verify_reaction"))

    

    try:

        # Gửi kèm ảnh tym.jpeg từ cùng folder code

        if os.path.exists('tym.jpeg'):

            with open('tym.jpeg', 'rb') as photo:

                sent_message = await bot.send_photo(chat_id, photo, caption=text, reply_markup=markup, parse_mode='HTML')

        else:

            sent_message = await bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

            

        await add_verification_message_id(chat_id, sent_message.message_id)

        return sent_message

    except Exception as e:

        logger.error(f"Failed to send reaction message to {chat_id}: {e}")

        return None



async def check_user_reaction_db(user_id, group_handle):

    """Kiểm tra database xem user đã thả tym chưa"""

async def check_user_reaction_db(user_id, group_handle):
    """Kiểm tra database xem user đã thả tym chưa (khớp linh hoạt cả @, không @ và chat_id)"""
    handle_clean = group_handle.lstrip('@').lower()
    handle_with_at = f"@{handle_clean}"
    async with get_db_connection() as conn:
        async with conn.execute(
            'SELECT user_id FROM user_reactions WHERE user_id = ? AND (LOWER(group_handle) = ? OR LOWER(group_handle) = ? OR group_handle = ?)',
            (user_id, handle_clean, handle_with_at, group_handle)
        ) as cursor:
            return await cursor.fetchone() is not None

@bot.message_reaction_handler()
async def handle_message_reaction(message_reaction):
    """THEO DÕI 24/7 - BẮT MỌI CỬ ĐỘNG THẢ TYM"""
    try:
        chat_id = message_reaction.chat.id
        username = message_reaction.chat.username
        # Chuẩn hóa handle (chữ thường) để khớp với danh sách cấu hình
        group_handle = f"@{username.lower()}" if username else str(chat_id)
        
        user = message_reaction.user
        if not user: return
        user_id = user.id
        full_name = get_full_name(user)
        
        # In thông báo ra CMD cực kỳ rõ ràng
        print("\n" + "="*50)
        print(f"🔥 PHÁT HIỆN THẢ TYM MỚI!")
        print(f"👤 Người thực hiện: {full_name} (ID: {user_id})")
        print(f"📍 Tại nhóm: {group_handle}")
        print(f"🆔 Message ID: {message_reaction.message_id}")

        # Danh sách các loại tim (emoji) được bot chấp nhận
        heart_variants = ["❤️", "❤", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💖", "💝", "💗"]
        
        # Kiểm tra xem có thả tim mới không (new_reaction)
        is_hearted = False
        emoji_used = ""
        for reaction in message_reaction.new_reaction:
            if reaction.type == 'emoji' and reaction.emoji in heart_variants:
                is_hearted = True
                emoji_used = reaction.emoji
                break
                
        if is_hearted:
            print(f"✅ Emoji: {emoji_used} -> HỢP LỆ!")
            now_ts = datetime.now(VIETNAM_TZ).timestamp()
            async with get_db_connection() as conn:
                await conn.execute(
                    'INSERT OR REPLACE INTO user_reactions (user_id, group_handle, reaction_date) VALUES (?, ?, ?)',
                    (user_id, group_handle, now_ts)
                )
                clean_h = group_handle.lstrip('@')
                await conn.execute(
                    'INSERT OR REPLACE INTO user_reactions (user_id, group_handle, reaction_date) VALUES (?, ?, ?)',
                    (user_id, clean_h, now_ts)
                )
                await conn.execute(
                    'INSERT OR REPLACE INTO user_reactions (user_id, group_handle, reaction_date) VALUES (?, ?, ?)',
                    (user_id, str(chat_id), now_ts)
                )
                await conn.commit()
            print(f"💾 TRẠNG THÁI: Đã lưu vào database cho user {user_id}")
            pass
        else:
            print(f"⏭️ TRẠNG THÁI: Bỏ qua (Không phải emoji tim hoặc user đã gỡ tim)")
        print("="*50 + "\n")

    except Exception as e:
        logger.error(f"Lỗi trong handle_message_reaction: {e}")
        print(f"❌ LỖI REACTION: {e}")



async def is_new_user(user_id):
    async with get_db_connection() as conn:
        async with conn.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,),) as cursor:
            return not bool(await cursor.fetchone())

@bot.message_handler(content_types=['contact'])
async def handle_contact(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not message.contact:
        return
        
    if message.contact.user_id != user_id:
        await bot.reply_to(message, "❌ Số điện thoại chia sẻ phải là của chính tài khoản này!")
        return
        
    phone = message.contact.phone_number.strip()
    
    if not (phone.startswith('+84') or phone.startswith('84')):
        await bot.reply_to(
            message,
            "❌ Chỉ chấp nhận số điện thoại đầu số Việt Nam (+84) để xác minh tài khoản!"
        )
        return
        
    # Delete phone verification request message & contact sharing message
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass
        
    await cleanup_messages(user_id, chat_id)
        
    async with get_db_connection() as conn:
        await conn.execute(
            "UPDATE users SET phone_verified = 1, phone_number = ? WHERE user_id = ?",
            (phone, user_id)
        )
        await conn.commit()
        
    cfg = await _mb_load_config()
    edition = cfg.get('edition', 1)
    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
    done_text = load_premium_text('done') if is_premium else None
    
    sent_success = None
    if done_text:
        sent_success = await bot.send_message(
            chat_id,
            done_text,
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
    else:
        sent_success = await bot.send_message(
            chat_id,
            "✅ **Xác minh số điện thoại thành công!**\n\nĐang chuyển sang các bước tiếp theo...",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
    if sent_success:
        await add_verification_message_id(chat_id, sent_success.message_id)
    
    class FakeMessage:
        def __init__(self, from_user, chat):
            self.from_user = from_user
            self.chat = chat
            self.text = "/start"
            self.message_id = 0
            
    fake_msg = FakeMessage(message.from_user, message.chat)
    await handle_start(fake_msg)

@bot.message_handler(commands=['start'])
async def handle_start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    is_new = await is_new_user(user_id)
    await initialize_user(user_id)
    
    # Save the user's `/start` message ID to delete later if they are not verified yet
    async with get_db_connection() as conn:
        async with conn.execute("SELECT checked FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
    if not row or not row['checked']:
        if message.message_id > 0:
            await add_verification_message_id(user_id, message.message_id)
            
    # Referral: check if started with a referral code (only for brand new users)
    if is_new and message.text and message.text.strip().startswith("/start "):
        try:
            referrer_id = int(message.text.strip().split(" ", 1)[1])
            if referrer_id != user_id:
                await add_invited_user(user_id, referrer_id)
        except Exception:
            pass

    # Gate start menu with ensure_user_verified
    if not await ensure_user_verified(chat_id, user_id):
        return

    # User is verified, cleanup all previous verification messages
    await cleanup_messages(user_id, chat_id)

    game_link = await mb_get_game_link()
    global _bot_me_cache
    if _bot_me_cache is None:
        _bot_me_cache = await bot.get_me()
    bot_username = f"@{_bot_me_cache.username}"
    bot_link = f"https://t.me/{_bot_me_cache.username}"

    image_url = await mb_get_start_image()
    caption = await mb_get_start_text()
    
    # Thay thế link game và bot link động
    caption = caption.replace("https://mb666.my", game_link)
    caption = caption.replace("https://t.me/MB66QuaTang66K_Bot", bot_link)
    # Hỗ trợ thêm placeholder nếu admin muốn dùng
    caption = caption.replace("{game_link}", game_link).replace("{link game}", game_link).replace("{bot_username}", bot_username).replace("{bot_link}", bot_link)

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton(get_menu_button_label('taikhoan')), types.KeyboardButton(get_menu_button_label('giftcode')),
        types.KeyboardButton(get_menu_button_label('gioithieu')), types.KeyboardButton(get_menu_button_label('diemdanh')),
        types.KeyboardButton(get_menu_button_label('thongke'))
    )
    try:
        if image_url:
            await bot.send_photo(chat_id, image_url, caption=caption, reply_markup=markup, parse_mode='HTML')
        else:
            await bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send welcome photo to {chat_id}: {e}")
        # Thử gửi lại tin nhắn text có HTML
        clean_tg_emoji = re.sub(r'</?tg-emoji[^>]*>', '', caption)
        try:
            if image_url:
                await bot.send_photo(chat_id, image_url, caption=clean_tg_emoji, reply_markup=markup, parse_mode='HTML')
            else:
                await bot.send_message(chat_id, clean_tg_emoji, reply_markup=markup, parse_mode='HTML')
        except Exception as e2:
            logger.error(f"Failed to send welcome HTML to {chat_id}: {e2}")
            # Fallback cuối cùng: Xóa toàn bộ thẻ HTML và gửi text thuần
            plain_text = re.sub(r'<[^>]+>', '', caption)
            try:
                await bot.send_message(chat_id, plain_text, reply_markup=markup)
            except Exception as e3:
                logger.error(f"Ultimate fallback send_message failed: {e3}")

@bot.callback_query_handler(func=lambda call: call.data == "verify_subscription")
async def callback_verify_subscription(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    try:
        # Check phone verification first
        async with get_db_connection() as conn:
            async with conn.execute("SELECT phone_verified FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row or not row['phone_verified']:
                    await bot.answer_callback_query(call.id, "❌ Bạn chưa xác minh số điện thoại!", show_alert=True)
                    return

        # Bước 1: Kiểm tra join kênh
        is_subscribed, unjoined_channels = await check_subscription(user_id, force_refresh=True)
        await cleanup_messages(user_id, chat_id)
        
        if is_subscribed:
            tym_channels = await mb_get_tym_channels()
            if tym_channels:
                # Thành công Bước 1 -> Chuyển sang Bước 2: Thả tym
                await show_reaction_verification_message(chat_id)
            else:
                # Không có tym channels, bắt xác minh web luôn!
                token = await generate_task_human_token(user_id, JOIN_HUMAN_VERIFY_TASK, chat_id, 0)
                confirm_url = await build_confirm_human_url(token)
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✅ XÁC MINH — KHÔNG PHẢI ROBOT", url=confirm_url))
                sent_msg = await bot.send_message(
                    chat_id,
                    "🎊 Bạn Đã Tham Gia Đầy Đủ Các Kênh Thành Công ‼️\n\n"
                    "✅ Bước Xác Nhận Cuối Cùng (Bắt Buộc): Vui Lòng Bạn Bấm Nút Xác Minh Dưới Đây Để Kích Hoạt TK👇",
                    reply_markup=markup,
                    parse_mode='HTML'
                )
                async with get_db_connection() as conn:
                    await conn.execute("UPDATE task_human_verifications SET source_message_id = ? WHERE token = ?", (sent_msg.message_id, token))
                    await conn.commit()
        else:
            await show_join_channels_message(chat_id, unjoined_channels)
        
        await bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Failed to verify subscription for {user_id}: {e}")
        await bot.send_message(chat_id, "❌ Đã xảy ra lỗi. Vui lòng thử lại sau.")

@bot.callback_query_handler(func=lambda call: call.data == "verify_reaction")
async def callback_verify_reaction(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    try:
        # Lấy danh sách handles cần check join (chuẩn hóa chữ thường)
        tym_channels = await mb_get_tym_channels()
        all_handles = [item.split('/')[0].lower() for item in tym_channels]
        is_joined_all, unjoined_handles = await check_subscription(user_id, channels=all_handles, force_refresh=True)
        
        # Kiểm tra logic thả tym (chỉ check Group - loại 2)
        missing_reactions = []
        for item in tym_channels:
            handle, loai = item.split('/')
            handle = handle.lower() # Chuẩn hóa handle
            if loai == '2': # Group cần check logic
                if not await check_user_reaction_db(user_id, handle):
                    missing_reactions.append(handle)
        
        # Nếu có bất kỳ lỗi nào (chưa join hoặc chưa thả tym)
        if unjoined_handles or missing_reactions:
            error_msg = "⚠️ <b>Xác minh chưa hoàn tất!</b>\n"
            
            if unjoined_handles:
                error_msg += f"\n❌ Bạn chưa tham gia đủ nhóm: <b>{', '.join(unjoined_handles)}</b>"
            
            if missing_reactions:
                error_msg += f"\n❌ Bạn chưa thả tym đủ tại: <b>{', '.join(missing_reactions)}</b>"
            
            error_msg += "\n\n👉 Vui lòng kiểm tra lại và thực hiện đầy đủ để tiếp tục!"
            
            # Show alert cho user
            await bot.answer_callback_query(call.id, error_msg.replace('<b>','').replace('</b>',''), show_alert=True)
            return

        # Thành công tất cả bước Telegram! Chuyển sang bước xác minh web.
        await cleanup_messages(user_id, chat_id)
        
        # Xóa tin nhắn reaction hiện tại
        try:
            await bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass

        token = await generate_task_human_token(user_id, JOIN_HUMAN_VERIFY_TASK, chat_id, 0)
        confirm_url = await build_confirm_human_url(token)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ XÁC MINH — KHÔNG PHẢI ROBOT", url=confirm_url))
        sent_msg = await bot.send_message(
            chat_id,
            "🎊 Bạn Đã Tham Gia Đầy Đủ Các Kênh Và Thả Tym Theo Yêu Cầu Thành Công ‼️\n\n"
            "✅ Bước Xác Nhận Cuối Cùng (Bắt Buộc): Vui Lòng Bạn Bấm Nút Xác Minh Dưới Đây Để Kích Hoạt TK👇",
            reply_markup=markup,
            parse_mode='HTML'
        )
        async with get_db_connection() as conn:
            await conn.execute("UPDATE task_human_verifications SET source_message_id = ? WHERE token = ?", (sent_msg.message_id, token))
            await conn.commit()
            
        await bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Failed to verify reaction for {user_id}: {e}")
        await bot.send_message(chat_id, "❌ Lỗi xác minh thả tym.")



    except Exception as e:

        logger.error(f"Failed to verify reaction for {user_id}: {e}")

        await bot.send_message(chat_id, "❌ Lỗi xác minh thả tym.")



def get_full_name(user):

    """Get full name of a user, falling back to username or user id if not available."""

    if hasattr(user, "first_name") and hasattr(user, "last_name") and user.first_name and user.last_name:

        return f"{user.first_name} {user.last_name}"

    elif hasattr(user, "first_name") and user.first_name:

        return user.first_name

    elif hasattr(user, "username") and user.username:

        return f"@{user.username}"

    return f"User{getattr(user, 'id', 'unknown')}"





# Fix: handle_referral only needs user_id, referrer logic is inside

async def handle_referral(user_id):
    if await is_claimed_referral(user_id):
        return
    referrer_id = await get_referrer(user_id)
    if referrer_id and await is_subscribed_user(user_id):
        # Mark referral as claimed FIRST to prevent concurrent spamming
        if not await add_claimed_referral(user_id):
            return
        
        try:
            # Fetch the invited user's Telegram profile to get their full name
            try:
                invited_user = await bot.get_chat(user_id)
                invited_full_name = get_full_name(invited_user)
            except Exception:
                invited_full_name = f"User {user_id}"
            
            reward = await mb_get_invite_reward()
            await update_user_balance(referrer_id, reward)
            try:
                cfg_temp = await _mb_load_config()
                edition = cfg_temp.get('edition', 1)
                is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
                bonus_text = None
                if is_premium:
                    bonus_text = load_premium_text('10')
                if bonus_text:
                    bonus_text = bonus_text.replace("11,000 ᴠɴᴅ", f"{reward:,} ᴠɴᴅ")
                    bonus_text = bonus_text.replace("Bin Siêu Quậy", f"<b>{invited_full_name}</b>")
                else:
                    bonus_text = f"Bạn đã nhận được {reward:,} ᴠɴᴅ khi mời <b>{invited_full_name}</b> tham gia."
                await bot.send_message(
                    referrer_id,
                    bonus_text,
                    parse_mode='HTML'
                )
            except Exception:
                pass
            await remove_invited_user(user_id)
        except Exception as e:
            logger.error(f"Failed to process referral for {referrer_id}: {e}")



async def remove_invited_user(user_id):

    async with get_db_connection() as conn:

        await conn.execute(
            'UPDATE invited_users SET confirmed = 1, confirmation_time = ? WHERE user_id = ?',
            (time.time(), user_id)
        )

        await conn.commit()



async def cleanup_messages(user_id, chat_id):
    messages = await get_captcha_message_ids(user_id)
    if messages.get('join_message'):
        val = str(messages['join_message'])
        ids = [x.strip() for x in val.split(',') if x.strip()]
        for msg_id in ids:
            try:
                await bot.delete_message(chat_id, int(msg_id))
            except Exception:
                pass
    await remove_captcha_message_ids(user_id)




@bot.message_handler(func=lambda message: message.text == get_menu_button_label('gioithieu'))

async def handle_invite_friends(message):

    user_id = message.from_user.id

    chat_id = message.chat.id

    # Invite flow must always show the hardcoded invite text.
    # Do NOT block behind subscription verification (/start gating),
    # otherwise it will send start text and confuse users.
    await initialize_user(user_id)

    _me = _bot_me_cache if _bot_me_cache else await bot.get_me()
    invite_link = f"https://t.me/{_me.username}?start={user_id}"

    photo_url = await mb_get_invite_image()
    # Text invite is intentionally hardcoded (not editable via admin/config).
    base_caption = await mb_get_invite_text()

    # Invite text is always hardcoded and independent from /start text.
    # Replace placeholder and avoid duplicating the link.
    caption = base_caption.replace("{invite_link}", invite_link)

    try:
        if photo_url:
            await bot.send_photo(chat_id, photo_url, caption=caption, parse_mode='HTML' if is_premium_edition() else None)
        else:
            await bot.send_message(chat_id, caption, parse_mode='HTML' if is_premium_edition() else None)
    except Exception as e:
        logger.error(f"Failed to send invite message to {user_id}: {e}")
        if photo_url:
            await bot.send_message(chat_id, caption, parse_mode='HTML' if is_premium_edition() else None)



@bot.message_handler(func=lambda message: message.text == get_menu_button_label('taikhoan'))

async def handle_account_command(message):

    user_id = message.from_user.id

    chat_id = message.chat.id

    if not await ensure_user_verified(chat_id, user_id):

        return

    balance = await get_balance(user_id)

    balance_formatted = "{:,} ᴠɴᴆ".format(balance)

    await bot.send_message(
        chat_id,
        f"<tg-emoji emoji-id=\"6253372958778070907\">💸</tg-emoji> Số Dư : <b>{balance_formatted}</b>\n"
        f"<tg-emoji emoji-id=\"5287684458881756303\">🤖</tg-emoji> ID Bot Của Bạn : <code>{user_id}</code>",
        parse_mode='HTML'
    )



@bot.message_handler(func=lambda message: message.text == get_menu_button_label('giftcode'))

async def handle_withdraw(message):

    user_id = message.from_user.id

    chat_id = message.chat.id

    if not await ensure_user_verified(chat_id, user_id):

        return

    balance = await get_balance(user_id)

    

    # Yêu cầu phải điểm danh mới được nhận code

    if await can_checkin_today(user_id):

        cfg_temp = await _mb_load_config()
        edition = cfg_temp.get('edition', 1)
        is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
        caption = None
        if is_premium:
            caption = load_premium_text('1')
        if not caption:
            caption = (
                "❌ Bạn Chưa Tham Gia Điểm Danh Ngày Hôm Nay‼️\n\n"
                "⚠️ Vui Lòng Bấm 👉 🎁 Điểm danh Để Có Thể Nhận Được Giftcode Từ Bot Nhé ❤️"
            )

        photo_url = "https://i.ibb.co/LDX7XpBx/image.png"
        try:
            await bot.send_photo(chat_id, photo_url, caption=caption, parse_mode='HTML' if is_premium else None)
        except Exception as e:
            logger.error(f"Failed to send checkin warning photo: {e}")
            await bot.send_message(chat_id, caption, parse_mode='HTML' if is_premium else None)

        return



    min_withdraw = await mb_get_min_withdraw()

    if balance >= min_withdraw:

        cfg_temp = await _mb_load_config()
        edition = cfg_temp.get('edition', 1)
        is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
        guide_text = None
        if is_premium:
            guide_text = load_premium_text('5')
        
        if not guide_text:
            guide_text = (
                "<tg-emoji emoji-id=\"6043992250831082249\">✅</tg-emoji> <b>Hướng Dẫn Bạn Thực Hiện Các Bước Đổi Điểm Game Tự Động</b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b><b>:</b>\n\n"
                "<tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji> <b>Ví Dụ : </b><b>/doidiem</b><b> [ Số Tiền ] \n\n</b>"
                "<b><tg-emoji emoji-id=\"5361683000180351007\">⚠️</tg-emoji></b><b> CHÚ Ý KHI ĐỔI ĐIỂM </b><b><tg-emoji emoji-id=\"5361683000180351007\">⚠️</tg-emoji></b><b>\n\n</b>"
                "<blockquote><b><tg-emoji emoji-id=\"5213214459023076318\">➡️</tg-emoji></b><b> Trong Vòng Ngày Tài Khoản Phải Thực Hiện 1 Lệnh Nạp 50K Tránh Quét TK Lạm Dụng Không Thể Thực Hiện Cộng Điểm CODE</b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b></blockquote>\n\n"
                "<b><tg-emoji emoji-id=\"5881824941547983497\">❌</tg-emoji></b><b> Gửi Sai Tài Khoản Game Vẫn Bị Trừ Tiền Và Không Hoàn Lại Nhé</b><b><tg-emoji emoji-id=\"6328094428971932747\">🆗</tg-emoji></b>\n\n"
                "<b><tg-emoji emoji-id=\"6057683292310737571\">🔔</tg-emoji></b><b>Cộng Điểm Thành Công : BOT Sẽ Gửi Thông Báo Đến Cho Bạn </b><b><tg-emoji emoji-id=\"5361870050301057412\">😘</tg-emoji></b>"
            )
        await bot.send_message(chat_id, guide_text, parse_mode='HTML')
    else:
        min_withdraw_formatted = "{:,}".format(min_withdraw)
        game_link = await mb_get_game_link()
        
        cfg_temp = await _mb_load_config()
        edition = cfg_temp.get('edition', 1)
        is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
        msg_22 = None
        if is_premium:
            msg_22 = load_premium_text('22')
            
        if msg_22:
            msg_22 = msg_22.replace("{link game}", game_link).replace("{min_withdraw}", str(min_withdraw_formatted))
            await bot.send_message(chat_id, msg_22, parse_mode='HTML')
        else:
            await bot.send_message(
                chat_id,
                f"<tg-emoji emoji-id=\"5213125716408808971\">🛑</tg-emoji> <b>nhận GiftCode không thành công, số dư của bạn không đủ {min_withdraw_formatted} VNĐ</b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b>\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                "<b><tg-emoji emoji-id=\"5253742260054409879\">✉️</tg-emoji></b><b> Bạn có thể kiếm thêm tiền bằng cách chia sẻ link giới thiệu cho bạn bè\n\n</b>"
                "<tg-emoji emoji-id=\"6327906889224951168\">🎮</tg-emoji><b> LINK TRUY CẬP GAMES:</b>\n"
                f"<tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji> {game_link}",
                parse_mode='HTML'
            )



@bot.message_handler(func=lambda message: message.text == get_menu_button_label('thongke'))

async def handle_statistics(message):

    user_id = message.from_user.id

    chat_id = message.chat.id

    if not await ensure_user_verified(chat_id, user_id):

        return

    total_users = await get_total_users()

    _, joined = await get_invited_users(user_id)
    invited_count = len(joined)

    await bot.send_message(
        chat_id,
        f"<tg-emoji emoji-id=\"5190806721286657692\">📊</tg-emoji> Thống Kê Hoạt Động \n"
        f"<tg-emoji emoji-id=\"6206499334976969393\">👥</tg-emoji> Tổng Người Dùng : <b>{total_users}</b>\n"
        f"<tg-emoji emoji-id=\"5253742260054409879\">✉️</tg-emoji> Số Ref Bạn Đã Mời : <b>{invited_count}</b>",
        parse_mode='HTML'
    )



@bot.message_handler(func=lambda message: message.text == get_menu_button_label('diemdanh'))

async def handle_checkin(message):

    user_id = message.from_user.id

    chat_id = message.chat.id

    if not await ensure_user_verified(chat_id, user_id):

        return

    

    # Kiểm tra đã điểm danh chưa

    if not await can_checkin_today(user_id):

        await bot.send_message(chat_id, "Bạn đã điểm danh ngày hôm nay rồi!")

        return

    

    # Gửi tin nhắn tạm thời để lấy message_id

    temp_text = "🎁 **ĐIỂM DANH HÀNG NGÀY**\n\n⌛ Đang khởi tạo link điểm danh..."

    msg = await bot.send_message(chat_id, temp_text, parse_mode='Markdown')

    

    # Tạo token mã hóa chính xác (bao gồm message_id của chính tin nhắn vừa gửi)

    token_data = f"{user_id}_{int(time.time())}_{msg.message_id}_{API_TOKEN}"

    token = base64.b64encode(token_data.encode()).decode()

    

    # Đọc domain từ config hoặc dùng mặc định

    try:

        async with aiofiles.open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:

            content = await f.read()

            config = json.loads(content)

        domain = config.get('website_domain', 'mmovip247.online')
        bot_path = config.get('bot_path', '')
    except:
        domain = 'mmovip247.online'
        bot_path = ''
    
    if '://' in domain:
        domain = domain.split('://', 1)[1]
    protocol = 'http' if domain.endswith('.test') or domain.endswith('.local') or 'localhost' in domain or '127.0.0.1' in domain else 'https'
    domain_with_proto = f"{protocol}://{domain}"

    # Tạo link đến trang điểm danh chính thức
    if bot_path:
        checkin_link = f"{domain_with_proto}/{bot_path}/index.php?token={token}"
    else:
        checkin_link = f"{domain_with_proto}/index.php?token={token}"

    

    # Lấy thông tin streak hiện tại

    status = await get_user_checkin_status(user_id)

    

    is_premium = is_premium_edition()
    premium_checkin_text = None
    if is_premium:
        premium_checkin_text = load_premium_text('3')
    if premium_checkin_text:
        text = premium_checkin_text
        text = text.replace("0/7 ngày", f"{status['streak']}/7 ngày")
        text = text.replace("0 lần", f"{status['total_checkins']} lần")
        text = text.replace("0 VNĐ", f"{status['total_rewards']:,} VNĐ")
        text = text.replace("Link điểm danh:\n\n", f"Link điểm danh:\n{checkin_link}\n\n")
    else:
        text = "🎁 **ĐIỂM DANH HÀNG NGÀY**\n\n"

        text += "💰 **Phần thưởng mỗi ngày:**\n"

        text += "• Ngày 1: 6,666 VNĐ\n"

        text += "• Ngày 2: 12,345 VNĐ\n"

        text += "• Ngày 3: 29,000 VNĐ\n"

        text += "• Ngày 4: 34,567 VNĐ\n"

        text += "• Ngày 5: 45,678 VNĐ\n"

        text += "• Ngày 6: 59,999 VNĐ\n"

        text += "• Ngày 7: 66,666-100,000 VNĐ \n(Nhận Tiền Thưởng Ngẫu Nhiên)\n\n"

        text += f"🔥 **Streak hiện tại:** {status['streak']}/7 ngày\n"

        text += f"📊 **Tổng điểm danh:** {status['total_checkins']} lần\n"

        text += f"💎 **Tổng thưởng:** {status['total_rewards']:,} VNĐ\n\n"

        text += "⏰ **Lưu ý:**\n"

        text += "• Điểm danh mỗi ngày để giữ streak\n"

        text += "• Bỏ lỡ 1 ngày = mất streak về 0\n"

        text += "• Mỗi ngày chỉ điểm danh 1 lần\n\n"

        text += f"🔗 **Link điểm danh:**\n{checkin_link}\n\n"

        text += "📱 Nhấn vào link trên hoặc nút bên dưới để điểm danh!"

    

    markup = types.InlineKeyboardMarkup()

    markup.add(types.InlineKeyboardButton("🎁 Điểm Danh Ngay", url=checkin_link))

    

    # Cập nhật tin nhắn với nội dung đầy đủ và link chính xác

    await bot.edit_message_text(

        chat_id=chat_id,

        message_id=msg.message_id,

        text=text,

        reply_markup=markup,

        parse_mode='HTML' if premium_checkin_text else 'Markdown'

    )



@bot.message_handler(func=lambda message: message.text == '💥 Nhận Code Livestream 💥')

async def handle_link_game(message):

    user_id = message.from_user.id

    chat_id = message.chat.id

    if not await ensure_user_verified(chat_id, user_id):

        return

    markup = types.InlineKeyboardMarkup()

    markup.add(types.InlineKeyboardButton("🎁 THAM GIA NGAY 🎁", url=GAME_WEBSITE_URL))

    try:
        if LINK_GAME_IMAGE_URL:
            await bot.send_photo(
                chat_id,
                photo=LINK_GAME_IMAGE_URL,
                caption=(
                    "🎊 Tham gia phiên live hằng daily, Jun88 phát thưởng hội viên hàng ngàn code và nhiều ưu đãi cực khủng 🔥\n\n"
                    "✨ Nhanh tay tham gia ngay trước khi sự kiện kết thúc nhé! ⌛️\n\n"
                ),
                reply_markup=markup
            )
        else:
            await bot.send_message(
                chat_id,
                text=(
                    "🎊 Tham gia phiên live hằng daily, Jun88 phát thưởng hội viên hàng ngàn code và nhiều ưu đãi cực khủng 🔥\n\n"
                    "✨ Nhanh tay tham gia ngay trước khi sự kiện kết thúc nhé! ⌛️\n\n"
                ),
                reply_markup=markup,
                parse_mode='HTML'
            )
    except Exception as e:

        logger.error(f"Failed to send game link message to {user_id}: {e}")



@bot.message_handler(commands=['admin'])

async def handle_admin_panel(message):

    current_admins = await mb_get_admins()

    if message.from_user.id not in current_admins:

        await bot.reply_to(message, "❌ Bạn không có quyền truy cập bảng quản trị.")

        return

    

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    markup.add(
        types.KeyboardButton("🖼️ Sửa Ảnh Thông Báo Nhận Code 🎁"), types.KeyboardButton("🏧 Cài Min Rút"),
        types.KeyboardButton("👤 Thêm QTV"), types.KeyboardButton("📡 Cài kênh tham gia"),
        types.KeyboardButton("❤️ Cài kênh yc tym"), types.KeyboardButton("⚙️ Cài lượt đổi code"),
        types.KeyboardButton("💰 Tiền Mời Bạn"), types.KeyboardButton("🔗 Đổi Link Game"),
        types.KeyboardButton("🖼️ Sửa Ảnh Tham Gia"), types.KeyboardButton("🖼️ Sửa Ảnh Giới Thiệu BB"),
        types.KeyboardButton("⚡ Duyệt nhanh"), types.KeyboardButton("📡 Check QTV Kênh"), 
        types.KeyboardButton("📤 Gửi Thông Báo"), types.KeyboardButton("❌ Hủy Admin")
    )

    

    await bot.send_message(

        message.chat.id,

        "🛠 <b>BẢNG QUẢN TRỊ</b>\n\n✅ Chọn Một Chức Năng Bên Dưới Để Bắt Đầu SETUP BOT Hoàn Chỉnh👇.",

        reply_markup=markup,

        parse_mode='HTML'

    )



async def admin_check_qtv_all(message):

    """Kiểm tra quyền QTV của bot trên toàn bộ các kênh cấu hình."""

    join_channels = await mb_get_join_channels()

    tym_channels_raw = await mb_get_tym_channels()

    

    # Xử lý danh sách kênh tym (dạng @handle/loai)

    tym_channels = []

    for tc in tym_channels_raw:

        if '/' in tc:

            tym_channels.append(tc.split('/')[0])

        else:

            tym_channels.append(tc)

            

    # Gộp và deduplicate

    all_channels = list(set(join_channels + tym_channels))

    

    bot_info = _bot_me_cache if _bot_me_cache else await bot.get_me()

    bot_id = bot_info.id

    

    ok_admin = []

    need_admin = []

    no_access = []

    

    progress_msg = await bot.send_message(message.chat.id, f"⌛ Đang kiểm tra {len(all_channels)} kênh, vui lòng đợi...")

    

    for channel in all_channels:

        try:
            ch_to_check = channel.split('/')[0] if '/' in channel else channel

            member = await bot.get_chat_member(ch_to_check, bot_id)

            if member.status in ("administrator", "creator"):

                ok_admin.append(channel)

            else:

                need_admin.append(f"{channel} ({member.status})")

        except Exception as e:

            no_access.append(f"{channel} ({str(e)[:60]})")



    def _show(items, limit=30):

        if not items:

            return "(trống)"

        if len(items) <= limit:

            return "\n".join(items)

        return "\n".join(items[:limit]) + f"\n... và {len(items) - limit} kênh khác"



    report = [

        "📡 <b>KIỂM TRA QUYỀN QTV TOÀN BỘ KÊNH</b>",

        f"📊 Tổng kênh: {len(all_channels)}",

        f"✅ QTV OK: {len(ok_admin)}",

        f"⚠️ Có quyền xem nhưng chưa có QTV: {len(need_admin)}",

        f"❌ Không truy cập được: {len(no_access)}",

        "",

        "<b>1) KÊNH ĐÃ CÓ QTV:</b>",

        _show(ok_admin),

        "",

        "<b>2) KÊNH CẦN CẤP QTV:</b>",

        _show(need_admin),

        "",

        "<b>3) KÊNH KHÔNG TRUY CẬP ĐƯỢC:</b>",

        _show(no_access),

    ]

    

    await bot.delete_message(message.chat.id, progress_msg.message_id)

    await bot.send_message(message.chat.id, "\n".join(report), parse_mode='HTML')



@bot.message_handler(func=lambda m: m.text in [
    "🖼️ Sửa Ảnh Thông Báo Nhận Code 🎁", "🏧 Cài Min Rút",
    "👤 Thêm QTV", "📡 Cài kênh tham gia",
    "❤️ Cài kênh yc tym", "⚙️ Cài lượt đổi code", "💰 Tiền Mời Bạn", "🔗 Đổi Link Game",
    "🖼️ Sửa Ảnh Tham Gia", "🖼️ Sửa Ảnh Giới Thiệu BB",
    "⚡ Duyệt nhanh", "📡 Check QTV Kênh", "📤 Gửi Thông Báo", "❌ Hủy Admin"
])

async def admin_functions_router(message):

    current_admins = await mb_get_admins()

    if message.from_user.id not in current_admins:

        return

    user_id = message.from_user.id

    text = message.text

    

    if text == "❌ Hủy Admin":

        await bot.send_message(message.chat.id, "✅ Đã đóng bảng quản trị.", reply_markup=types.ReplyKeyboardRemove())

        _admin_states.pop(user_id, None)

        return

    elif text == "📤 Gửi Thông Báo":
        _admin_states[user_id] = {'step': 'waiting_for_broadcast_text'}
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.send_message(
            message.chat.id,
            "📨 Nhập nội dung thông báo bạn muốn gửi tới tất cả người dùng:\n"
            "📸 (Tùy chọn) Gửi ảnh sau khi nhập nội dung.",
            reply_markup=markup
        )
        return



    if text == "🏧 Cài Min Rút":

        _admin_states[user_id] = {'step': 'set_min_withdraw'}

        current = await mb_get_min_withdraw()

        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))

        await bot.send_message(message.chat.id, f"Nhập số tiền tối thiểu để rút code (VNĐ).\nHiện tại: {current:,} VNĐ", reply_markup=markup)



    elif text == "👤 Thêm QTV":

        _admin_states[user_id] = {'step': 'add_admin'}

        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))

        await bot.send_message(message.chat.id, "Nhập User ID của QTV mới muốn thêm.", reply_markup=markup)



    elif text == "📡 Cài kênh tham gia":

        channels = await mb_get_join_channels()

        _admin_states[user_id] = {'step': 'edit_join_channels'}

        text_ch = "\n".join([f"• {c}" for c in channels])

        markup = types.InlineKeyboardMarkup()

        markup.add(

            types.InlineKeyboardButton("➕ Thêm Kênh", callback_data="admin_add_join_ch"),

            types.InlineKeyboardButton("➖ Xóa Kênh", callback_data="admin_del_join_ch")

        )

        await bot.send_message(message.chat.id, f"Danh sách kênh join hiện tại:\n{text_ch}", reply_markup=markup)



    elif text == "❤️ Cài kênh yc tym":

        channels = await mb_get_tym_channels()

        _admin_states[user_id] = {'step': 'edit_tym_channels'}

        text_ch = "\n".join([f"• {c}" for c in channels])

        markup = types.InlineKeyboardMarkup()

        markup.add(

            types.InlineKeyboardButton("➕ Thêm Nhóm Tym", callback_data="admin_add_tym_ch"),

            types.InlineKeyboardButton("➖ Xóa Nhóm Tym", callback_data="admin_del_tym_ch")

        )

        await bot.send_message(message.chat.id, f"Danh sách nhóm tym hiện tại (handle/loai):\n{text_ch}", reply_markup=markup)



    elif text == "⚙️ Cài lượt đổi code":

        _admin_states[user_id] = {'step': 'set_daily_limit'}
        current = await get_redeem_limit()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.send_message(message.chat.id, f"📊 <b>Giới hạn hiện tại:</b> <code>{current}</code>", parse_mode='HTML')
        await bot.send_message(message.chat.id, "Nhập giới hạn số lần nhận code/ngày mới cho mỗi user:", reply_markup=markup)



    elif text == "💰 Tiền Mời Bạn":

        _admin_states[user_id] = {'step': 'set_invite_reward'}
        current = await mb_get_invite_reward()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.send_message(message.chat.id, f"💰 <b>Tiền thưởng hiện tại:</b> <code>{current:,}</code> VNĐ", parse_mode='HTML')
        await bot.send_message(message.chat.id, "Nhập số tiền thưởng khi mời 1 bạn bè mới (VNĐ):", reply_markup=markup)


    elif text == "🔗 Đổi Link Game":

        _admin_states[user_id] = {'step': 'set_game_link'}
        current = await mb_get_game_link()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.send_message(message.chat.id, f"🔗 <b>Link game hiện tại:</b>\n<code>{current}</code>", parse_mode='HTML')
        await bot.send_message(message.chat.id, "Nhập link game mới:", reply_markup=markup)



    elif text == "🖼️ Sửa Ảnh Tham Gia":
        _admin_states[user_id] = {'step': 'save_start_img'}
        current = await mb_get_start_image()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        msg_text = (
            "🖼️ <b>SỬA ẢNH THAM GIA (START)</b>\n\n"
            "Vui lòng gửi URL ảnh mới (hoặc gửi ảnh trực tiếp) để cập nhật ảnh Start.\n\n"
            f"🖼️ Ảnh hiện tại:\n<code>{current}</code>\n\n"
            "<i>(Nội dung chữ đã được gắn cứng, chỉ có thể sửa ảnh)</i>"
        )
        await bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode='HTML')

    elif text == "🖼️ Sửa Ảnh Giới Thiệu BB":
        _admin_states[user_id] = {'step': 'save_invite_img'}
        current = await mb_get_invite_image()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        msg_text = (
            "🖼️ <b>SỬA ẢNH GIỚI THIỆU BẠN BÈ</b>\n\n"
            "Vui lòng gửi URL ảnh mới (hoặc gửi ảnh trực tiếp) để cập nhật ảnh Mời bạn bè.\n\n"
            f"🖼️ Ảnh hiện tại:\n<code>{current}</code>\n\n"
            "<i>(Nội dung chữ đã được gắn cứng, chỉ có thể sửa ảnh)</i>"
        )
        await bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode='HTML')

    elif text == "🖼️ Sửa Ảnh Thông Báo Nhận Code 🎁":

        _admin_states[user_id] = {'step': 'set_notify_image'}
        current = await mb_get_notify_image()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        
        msg_text = (
            "💬 Cập Nhật URL Ảnh Thông Báo Mới\n\n"
            "🖼 Ảnh Cũ Hệ Thống:\n"
            f"<code>{current}</code>\n\n"
            "✅ Click Vào @SHOPMMOVIP_BOT Để Úp Ảnh Lấy Link Siêu Nhanh 🎉"
        )
        await bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode='HTML')



    elif text == "⚡ Duyệt nhanh":
        _admin_states[user_id] = {'step': 'bulk_action_list'}
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.send_message(message.chat.id, "💡 <b>DUYỆT NHANH / TỪ CHỐI NHANH</b>\n\nVui lòng gửi danh sách tài khoản web (mỗi tài khoản một dòng):", reply_markup=markup, parse_mode='HTML')

    elif text == "📡 Check QTV Kênh":

        await admin_check_qtv_all(message)



@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))

async def admin_callbacks(call):

    current_admins = await mb_get_admins()

    if call.from_user.id not in current_admins:

        await bot.answer_callback_query(call.id, "❌ Không có quyền.", show_alert=True)

        return

    user_id = call.from_user.id

    data = call.data

    

    if data == "admin_cancel":

        _admin_states.pop(user_id, None)

        await bot.edit_message_text("✅ Đã hủy thao tác.", call.message.chat.id, call.message.message_id)

        return

        

    elif data == "admin_clear_all_codes":

        await save_redeemable_codes([])

        await bot.edit_message_text("✅ Đã xóa toàn bộ code trong kho.", call.message.chat.id, call.message.message_id)



    elif data == "admin_add_join_ch":

        _admin_states[user_id] = {'step': 'save_add_join_ch'}

        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))

        await bot.edit_message_text("Nhập handle kênh muốn thêm (VD: @kenhmoi).", call.message.chat.id, call.message.message_id, reply_markup=markup)



    elif data == "admin_del_join_ch":

        _admin_states[user_id] = {'step': 'save_del_join_ch'}

        channels = await mb_get_join_channels()

        list_ch = "\n".join([f"- {c}" for c in channels]) if channels else "Không có kênh nào."

        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))

        await bot.edit_message_text(f"📋 Danh sách kênh hiện tại:\n{list_ch}\n\nNhập handle kênh muốn xóa (VD: @kenhmoi):", call.message.chat.id, call.message.message_id, reply_markup=markup)



    elif data == "admin_add_tym_ch":

        _admin_states[user_id] = {'step': 'save_add_tym_ch'}

        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))

        await bot.edit_message_text("Nhập handle kênh.\nVD: @nhommoi", call.message.chat.id, call.message.message_id, reply_markup=markup)



    elif data == "admin_edit_start_img":
        _admin_states[user_id] = {'step': 'save_start_img'}
        current = await mb_get_start_image()
        msg_text = (
            "💬 Cập Nhật URL Ảnh Mới Khi Ấn /start Truy Cập BOT\n\n"
            "🖼 Ảnh Cũ Hệ Thống:\n"
            f"<code>{current}</code>\n\n"
            "✅ Click Vào @SHOPMMOVIP_BOT Để Úp Ảnh Lấy Link Siêu Nhanh 🎉"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif data == "admin_edit_start_txt":
        await bot.answer_callback_query(call.id, "❌ Nội dung chữ đã được gắn cứng. Chỉ có thể đổi ảnh.", show_alert=True)

    elif data == "admin_edit_invite_img":
        _admin_states[user_id] = {'step': 'save_invite_img'}
        current = await mb_get_invite_image()
        msg_text = (
            "💬 Cập Nhật URL Ảnh Mời Bạn Mới\n\n"
            "🖼 Ảnh Cũ Hệ Thống:\n"
            f"<code>{current}</code>\n\n"
            "✅ Click Vào @SHOPMMOVIP_BOT Để Úp Ảnh Lấy Link Siêu Nhanh 🎉"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif data == "admin_edit_invite_txt":
        await bot.answer_callback_query(call.id, "❌ Text Mời Bạn đã được gắn cứng. Chỉ có thể đổi ảnh.", show_alert=True)

    elif data == "admin_del_tym_ch":

        _admin_states[user_id] = {'step': 'save_del_tym_ch'}

        channels = await mb_get_tym_channels()

        list_ch = "\n".join([f"- {c}" for c in channels]) if channels else "Không có nhóm nào."

        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))

        await bot.edit_message_text(f"📋 Danh sách nhóm tym hiện tại:\n{list_ch}\n\nNhập handle nhóm muốn xóa (VD: @nhommoi):", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "admin_bulk_approve" or data == "admin_bulk_reject":
        admin_id = call.from_user.id
        if admin_id not in _admin_states or 'accounts' not in _admin_states[admin_id]:
            await bot.answer_callback_query(call.id, "❌ Hết hạn thao tác hoặc dữ liệu trống.", show_alert=True)
            return
            
        accounts = _admin_states[admin_id]['accounts']
        is_approve = (data == "admin_bulk_approve")
        
        status_msg = await bot.send_message(call.message.chat.id, f"⏳ Đang xử lý {len(accounts)} tài khoản...")
        results = []
        
        for acc in accounts:
            request_ids = await get_pending_requests_by_web_account(acc)
            if not request_ids:
                results.append(f"❓ {acc}: Không có yêu cầu pending")
                continue
                
            rid = max(request_ids)
            if is_approve:
                success, result, _ = await approve_request_internal(rid)
                if success:
                    results.append(f"✅ {acc}: Thành công")
                else:
                    results.append(f"❌ {acc}: {result}")
            else:
                success, result, _ = await reject_request_internal(rid)
                if success:
                    results.append(f"❌ {acc}: Đã từ chối")
                else:
                    results.append(f"⚠️ {acc}: {result}")
        
        _admin_states.pop(admin_id, None)
        
        res_text = "<b>KẾT QUẢ XỬ LÝ HÀNG LOẠT:</b>\n\n" + "\n".join(results)
        if len(res_text) > 4000:
            for x in range(0, len(res_text), 4000):
                await bot.send_message(call.message.chat.id, res_text[x:x+4000], parse_mode='HTML')
        else:
            await bot.edit_message_text(res_text, call.message.chat.id, status_msg.message_id, parse_mode='HTML')
        
        await bot.answer_callback_query(call.id, "Đã xử lý xong!")



def clean_premium_emoji(html_str, edition):
    if not html_str:
        return html_str
    if edition == 2 or str(edition) == '2' or edition == 'premium':
        return html_str
    import re
    cleaned = re.sub(r'<tg-emoji[^>]*>', '', html_str)
    cleaned = re.sub(r'</tg-emoji>', '', cleaned)
    return cleaned

@bot.message_handler(func=lambda m: m.from_user.id in _admin_states, content_types=['text', 'photo'])
async def handle_admin_inputs(message):

    current_admins = await mb_get_admins()

    if message.from_user.id not in current_admins:

        return

    user_id = message.from_user.id

    state = _admin_states[user_id]

    step = state.get('step')

    text = message.text

    

    if not text and not message.photo:

        return



    main_menu_buttons = [
        "🎁 Sửa Nhận Code", "🏧 Cài Min Rút",
        "➕ Thêm Code", "📋 Check/Xóa Code", "👤 Thêm QTV", "📡 Cài kênh tham gia",
        "❤️ Cài kênh yc tym", "⚙️ Cài lượt đổi code", "💰 Tiền Mời Bạn", "🔗 Đổi Link Game",
        "🖼️ Sửa Ảnh Tham Gia", "🖼️ Sửa Ảnh Giới Thiệu BB",
        "🖼 Đổi Ảnh Thông Báo", "⚡ Duyệt nhanh", "📡 Check QTV Kênh", "📤 Gửi Thông Báo", "❌ Hủy Admin"
    ]

    cancel_keywords = ["hủy", "huy", "huỷ", "/cancel", "cancel", "hủy thao tác", "❌ hủy thao tác"]

    

    if text and (text in main_menu_buttons or text.lower() in cancel_keywords):

        _admin_states.pop(user_id, None)

        if text == "❌ Hủy Admin":

            await bot.send_message(message.chat.id, "✅ Đã đóng bảng quản trị.", reply_markup=types.ReplyKeyboardRemove())

        elif text in main_menu_buttons:

            await admin_functions_router(message)

        else:

            await bot.reply_to(message, "✅ Đã hủy thao tác hiện tại.")

        return



    if not text and step != 'waiting_for_broadcast_photo':

        await bot.reply_to(message, "❌ Vui lòng nhập nội dung dạng văn bản.")

        return



    if step == 'waiting_for_broadcast_text':
        state['broadcast_text'] = message.html_text or text
        state['step'] = 'waiting_for_broadcast_photo'
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Hủy Thao Tác", callback_data="admin_cancel"))
        await bot.reply_to(message, "📸 Gửi ảnh để đính kèm hoặc nhập 'skip' để bỏ qua:", reply_markup=markup)
        return

    elif step == 'waiting_for_broadcast_photo':
        photo = None
        if message.photo:
            photo = message.photo[-1].file_id
        elif text:
            if text.lower() == 'skip':
                photo = None
            else:
                photo = text.strip()
        else:
            await bot.reply_to(message, "❌ Vui lòng gửi ảnh hoặc nhập 'skip'.")
            return

        content = state.get('broadcast_text')
        
        # Get all users
        async with get_db_connection() as conn:
            async with conn.execute('SELECT user_id FROM users') as cursor:
                rows = await cursor.fetchall()
                target_users = [row['user_id'] for row in rows]
        
        success = 0
        fail = 0
        
        status_msg = await bot.send_message(message.chat.id, f"⌛ Đang gửi thông báo tới {len(target_users)} người dùng...")
        
        for u_id in target_users:
            try:
                if photo:
                    await bot.send_photo(int(u_id), photo=photo, caption=content, parse_mode='HTML')
                else:
                    await bot.send_message(int(u_id), content, parse_mode='HTML')
                success += 1
            except Exception as e:
                fail += 1
                logger.error(f"Không gửi được tới {u_id}: {e}")
        
        await bot.edit_message_text(f"✅ Đã gửi thông báo đến {success} người dùng.\n❌ Lỗi: {fail} người không nhận được.", message.chat.id, status_msg.message_id)
        _admin_states.pop(user_id, None)
        return

    elif step == 'set_min_withdraw':

        try:

            val = int(text.replace(",", "").replace(".", ""))

            await mb_save_min_withdraw(val)

            await bot.reply_to(message, f"✅ Đã đặt min rút là {val:,} VNĐ.")

            _admin_states.pop(user_id, None)

        except ValueError:

            await bot.reply_to(message, "❌ Vui lòng nhập số hợp lệ.")



    elif step == 'add_codes':

        new_codes = [c.strip() for c in text.splitlines() if c.strip()]

        existing = await load_redeemable_codes()

        await save_redeemable_codes(existing + new_codes)

        await bot.reply_to(message, f"✅ Đã thêm {len(new_codes)} code mới vào kho.")

        _admin_states.pop(user_id, None)



    elif step == 'add_admin':

        try:

            new_id = int(text)

            current_admins = await mb_get_admins()

            if new_id not in current_admins:

                current_admins.append(new_id)

                await mb_save_admins(current_admins)

                await bot.reply_to(message, f"✅ Đã thêm user {new_id} làm QTV.")

            else:

                await bot.reply_to(message, "User này đã là QTV.")

            _admin_states.pop(user_id, None)

        except ValueError:

            await bot.reply_to(message, "❌ User ID phải là số.")



    elif step == 'save_add_join_ch':
        channels = await mb_get_join_channels()
        items = [x.strip() for x in text.replace(',', '\n').split('\n') if x.strip()]
        added = []
        skipped = []
        for item in items:
            if item not in channels:
                channels.append(item)
                added.append(item)
            else:
                skipped.append(item)
        if added:
            await mb_save_join_channels(channels)
        result = ""
        if added:
            result += f"✅ Đã thêm {len(added)} kênh:\n" + "\n".join(f"  • {c}" for c in added)
        if skipped:
            if result: result += "\n"
            result += f"⚠️ Đã có sẵn ({len(skipped)}):\n" + "\n".join(f"  • {c}" for c in skipped)
        if not added and not skipped:
            result = "❌ Không có kênh nào để thêm."
        await bot.reply_to(message, result)
        _admin_states.pop(user_id, None)

    elif step == 'save_del_join_ch':
        channels = await mb_get_join_channels()
        items = [x.strip() for x in text.replace(',', '\n').split('\n') if x.strip()]
        deleted = []
        not_found = []
        for item in items:
            if item in channels:
                channels.remove(item)
                deleted.append(item)
            else:
                not_found.append(item)
        if deleted:
            await mb_save_join_channels(channels)
        result = ""
        if deleted:
            result += f"✅ Đã xóa {len(deleted)} kênh:\n" + "\n".join(f"  • {c}" for c in deleted)
        if not_found:
            if result: result += "\n"
            result += f"❌ Không tìm thấy ({len(not_found)}):\n" + "\n".join(f"  • {c}" for c in not_found)
        if not deleted and not not_found:
            result = "❌ Không có kênh nào để xóa."
        await bot.reply_to(message, result)
        _admin_states.pop(user_id, None)

    elif step == 'save_add_tym_ch':
        channels = await mb_get_tym_channels()
        items = [x.strip() for x in text.replace(',', '\n').split('\n') if x.strip()]
        added = []
        skipped = []
        for item in items:
            value = item
            if "/" not in value:
                value = f"{value}/1"
            if value not in channels:
                channels.append(value)
                added.append(value)
            else:
                skipped.append(value)
        if added:
            await mb_save_tym_channels(channels)
        result = ""
        if added:
            result += f"✅ Đã thêm {len(added)} nhóm tym:\n" + "\n".join(f"  • {c}" for c in added)
        if skipped:
            if result: result += "\n"
            result += f"⚠️ Đã có sẵn ({len(skipped)}):\n" + "\n".join(f"  • {c}" for c in skipped)
        if not added and not skipped:
            result = "❌ Không có nhóm nào để thêm."
        await bot.reply_to(message, result)
        _admin_states.pop(user_id, None)

    elif step == 'save_del_tym_ch':
        channels = await mb_get_tym_channels()
        items = [x.strip() for x in text.replace(',', '\n').split('\n') if x.strip()]
        deleted = []
        not_found = []
        for item in items:
            found = False
            if item in channels:
                channels.remove(item)
                found = True
            else:
                for c in list(channels):
                    if c == f"{item}/1" or c.startswith(f"{item}/"):
                        channels.remove(c)
                        found = True
                        break
            if found:
                deleted.append(item)
            else:
                not_found.append(item)
        if deleted:
            await mb_save_tym_channels(channels)
        result = ""
        if deleted:
            result += f"✅ Đã xóa {len(deleted)} nhóm:\n" + "\n".join(f"  • {c}" for c in deleted)
        if not_found:
            if result: result += "\n"
            result += f"❌ Không tìm thấy ({len(not_found)}):\n" + "\n".join(f"  • {c}" for c in not_found)
        if not deleted and not not_found:
            result = "❌ Không có nhóm nào để xóa."
        await bot.reply_to(message, result)
        _admin_states.pop(user_id, None)



    elif step == 'set_daily_limit':

        try:

            limit = int(text)

            await set_redeem_limit(limit)

            await bot.reply_to(message, f"✅ Đã đặt giới hạn đổi code là {limit} lần/ngày.")

            _admin_states.pop(user_id, None)

        except ValueError:

            await bot.reply_to(message, "❌ Vui lòng nhập số.")



    elif step == 'set_invite_reward':
        try:
            val = int(text.replace(",", "").replace(".", ""))
            await mb_save_invite_reward(val)
            await bot.reply_to(message, f"✅ Đã đặt tiền mời bạn là {val:,} VNĐ.")
            _admin_states.pop(user_id, None)
        except ValueError:
            await bot.reply_to(message, "❌ Vui lòng nhập số hợp lệ.")

    elif step == 'set_game_link':
        await mb_save_game_link(text.strip())
        await bot.reply_to(message, f"✅ Đã đặt link game thành công:\n{text}")
        _admin_states.pop(user_id, None)

    elif step == 'save_start_img':
        await mb_save_start_image(text.strip())
        await bot.reply_to(message, "✅ Đã cập nhật ảnh Start thành công.")
        _admin_states.pop(user_id, None)

    elif step == 'save_start_txt':
        cfg = await _mb_load_config()
        edition = cfg.get('edition', 1)
        input_text = message.html_text if message.text else (message.html_caption if message.caption else "")
        cleaned_text = clean_premium_emoji(input_text, edition)
        await mb_save_start_text(cleaned_text)
        await bot.reply_to(message, "✅ Đã cập nhật nội dung chữ Start thành công.")
        _admin_states.pop(user_id, None)

    elif step == 'save_invite_img':
        await mb_save_invite_image(text.strip())
        await bot.reply_to(message, "✅ Đã cập nhật ảnh Mời Bạn thành công.")
        _admin_states.pop(user_id, None)

    elif step == 'save_invite_txt':
        await bot.reply_to(message, "❌ Text Mời Bạn đã được gắn cứng. Chỉ có thể đổi ảnh.")
        _admin_states.pop(user_id, None)

    elif step == 'set_notify_image':
        await mb_save_notify_image(text.strip())
        await bot.reply_to(message, f"✅ Đã cập nhật ảnh thông báo thành công:\n{text}")
        _admin_states.pop(user_id, None)

    elif step == 'bulk_action_list':
        accounts = [line.strip() for line in text.splitlines() if line.strip()]
        if not accounts:
            await bot.reply_to(message, "❌ Danh sách trống. Vui lòng gửi lại:")
            return
        
        _admin_states[user_id]['accounts'] = accounts
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ CHẤP NHẬN TẤT CẢ", callback_data="admin_bulk_approve"),
            types.InlineKeyboardButton("❌ TỪ CHỐI TẤT CẢ", callback_data="admin_bulk_reject")
        )
        markup.add(types.InlineKeyboardButton("🔙 Hủy", callback_data="admin_cancel"))
        
        await bot.send_message(
            message.chat.id, 
            f"📋 Đã nhận danh sách <b>{len(accounts)}</b> tài khoản.\n\nBạn muốn làm gì với danh sách này?", 
            reply_markup=markup, 
            parse_mode='HTML'
        )



@bot.message_handler(commands=['addcoin'])

async def handle_addcoin_command(message):

    if message.from_user.id not in ADMINS:

        await bot.reply_to(message, "Bạn không có quyền thực hiện lệnh này.")

        return

    try:

        _, target_user_id, amount = message.text.split()

        target_user_id = int(target_user_id)

        amount = int(amount)

        await update_user_balance(target_user_id, amount)

        balance = await get_balance(target_user_id)

        await bot.reply_to(message, f"Đã cộng {amount} coins cho user {target_user_id}. Số dư hiện tại: {balance} coins")

    except ValueError:

        await bot.reply_to(message, "Vui lòng nhập theo cú pháp: /addcoin [user_id] [số tiền]")



@bot.message_handler(commands=['truemoney'])

async def handle_truemoney_command(message):

    if message.from_user.id not in ADMINS:

        await bot.reply_to(message, "Bạn không có quyền thực hiện lệnh này.")

        return

    try:

        _, target_user_id, amount = message.text.split()

        target_user_id = int(target_user_id)

        amount = int(amount)

        balance = await get_balance(target_user_id)

        if balance >= amount:

            await update_user_balance(target_user_id, -amount)

            balance = await get_balance(target_user_id)

            await bot.reply_to(message, f"Đã trừ {amount} coins từ user {target_user_id}. Số dư hiện tại: {balance} coins")

        else:

            await bot.reply_to(message, "Số dư không đủ để thực hiện giao dịch.")

    except ValueError:

        await bot.reply_to(message, "Vui lòng nhập theo cú pháp: /truemoney [user_id] [sò tiền]")



@bot.message_handler(commands=['gioihan'])

async def handle_gioihan_command(message):

    if message.from_user.id not in ADMINS:

        await bot.reply_to(message, "Bạn không có quyền thực hiện lệnh này.")

        return

    try:

        _, limit = message.text.split()

        limit = int(limit)

        if limit < 0:

            raise ValueError("Giới hạn phải là số không âm.")

        await set_redeem_limit(limit)

        await bot.reply_to(message, f"Đã đặt giới hạn đổi code là {limit} lần cho mỗi tài khoản.")

    except ValueError:

        await bot.reply_to(message, "Vui lòng nhập theo cú pháp: /gioihan [số lần]")



@bot.message_handler(commands=['doidiem'])

async def handle_withdraw_request(message):

    user_id = message.from_user.id

    chat_id = message.chat.id

    if not await ensure_user_verified(chat_id, user_id):

        return



    # Yêu cầu phải điểm danh mới được nhận code

    if await can_checkin_today(user_id):
        cfg_temp = await _mb_load_config()
        edition = cfg_temp.get('edition', 1)
        is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
        caption = None
        if is_premium:
            caption = load_premium_text('1')
        if not caption:
            caption = (
                "❌ Bạn Chưa Tham Gia Điểm Danh Ngày Hôm Nay‼️\n\n"
                "⚠️ Vui Lòng Bấm 👉 🎁 Điểm danh Để Có Thể Nhận Được Giftcode Từ Bot Nhé ❤️"
            )

        photo_url = "https://i.ibb.co/LDX7XpBx/image.png"
        try:
            await bot.send_photo(chat_id, photo_url, caption=caption, parse_mode='HTML' if is_premium else None)
        except Exception as e:
            logger.error(f"Failed to send checkin warning photo: {e}")
            await bot.send_message(chat_id, caption, parse_mode='HTML' if is_premium else None)

        return

    balance = await get_balance(user_id)
    min_withdraw = await mb_get_min_withdraw()
    
    details = message.text.split()
    if len(details) != 2:
        await bot.send_message(chat_id, f"🎖 Hướng Dẫn Nhận CODE: /doidiem {min_withdraw}")
        return

    _, amount_str = details

    try:

        amount = int(amount_str)

    except ValueError:

        await bot.send_message(chat_id, "🚫 Số tiền phải là một số nguyên hợp lệ.")

        return

    # min_withdraw = await mb_get_min_withdraw() # Moved up

    if amount < min_withdraw:

        await bot.send_message(chat_id, f"💎 Đổi Điểm Tối Thiểu Là {min_withdraw:,} VND")

        return

    if balance < amount:

        await bot.send_message(chat_id, "⛔️ Số dư của bạn không đủ để thực hiện giao dịch.")

        return

    

    # Kiểm tra giới hạn đổi code trong ngày

    

    redeem_count = await get_redeem_count(user_id)

    max_limit = await get_redeem_limit()

    if redeem_count >= max_limit:

        await bot.send_message(
            chat_id,
            f"<tg-emoji emoji-id=\"5213195952008997792\">❕</tg-emoji> <b>Bạn đã điểm danh ngày hôm nay rồi </b><b><tg-emoji emoji-id=\"5362049330825927922\">🤗</tg-emoji></b>\n\n"
            f"<tg-emoji emoji-id=\"5213125716408808971\">🛑</tg-emoji> <b>Tài khoản của bạn đã đạt giới hạn đổi code ({max_limit} lần) Không thể đổi thêm </b><b><tg-emoji emoji-id=\"5440660757194744323\">‼️</tg-emoji></b>\n\n"
            "<tg-emoji emoji-id=\"5409109841538994759\">🌈</tg-emoji> <b>Theo Dõi Kênh Để Nhận GIFTCODE Free Mỗi Ngày Nhé </b><b><tg-emoji emoji-id=\"5208541126583136130\">🎉</tg-emoji></b>\n"
            "<tg-emoji emoji-id=\"5215556805337296157\">➡️</tg-emoji> @khuyenmaicodenhacai <tg-emoji emoji-id=\"5220079633533250496\">👈</tg-emoji>",
            parse_mode='HTML'
        )

        return

    

    # Lưu thông tin vào state để xử lý khi user nhập tên tài khoản web

    telegram_account = get_full_name(message.from_user)

    await set_user_state(user_id, f"waiting_web_account:{amount}:{telegram_account}")

    game_link = await mb_get_game_link()

    cfg_temp = await _mb_load_config()
    edition = cfg_temp.get('edition', 1)
    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
    prompt_text = None
    if is_premium:
        prompt_text = load_premium_text('6')
    if prompt_text:
        prompt_text = prompt_text.replace("{link game}", game_link)
    else:
        prompt_text = (
            "✅ Vui Lòng Điền Tên Tài Khoản Trang Game Của Bạn Vào Đây👇:\n\n"

            "✈️ Nếu Chưa Có Tài Khoản Hãy Đăng Kí Tài Khoản Tại Đây Nhé‼️:\n"

            f"👉 {game_link}\n"
        )
    await bot.send_message(chat_id, prompt_text, parse_mode='HTML')



@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/'))

async def handle_text_message(message):

    """Xử lý tin nhắn text thông thường, bao gồm nhập tên tài khoản web"""

    user_id = message.from_user.id

    chat_id = message.chat.id

    state = await get_user_state(user_id)

    if state and state.startswith('waiting_game_username:'):
        parts = state.split(':')
        if len(parts) == 3:
            sent_msg_id = int(parts[1])
            record_id = int(parts[2])
            game_username = message.text.strip()
            
            if not game_username:
                await bot.send_message(chat_id, "❌ Tên tài khoản game không được để trống. Vui lòng nhập lại:")
                return
                
            # Xóa tin nhắn prompt và tin nhắn của user
            try:
                await bot.delete_message(chat_id, sent_msg_id)
            except Exception:
                pass
            try:
                await bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
                
            # Xóa trạng thái
            await remove_user_state(user_id)
            
            # Kích hoạt tài khoản và hoàn tất verification record
            async with get_db_connection() as conn:
                # Lấy IP từ record xác minh
                async with conn.execute(
                    "SELECT ip_address FROM task_human_verifications WHERE id = ?",
                    (record_id,)
                ) as cursor:
                    ver_row = await cursor.fetchone()
                ip_address = ver_row['ip_address'] if ver_row else 'UNKNOWN'
                
                # Cập nhật processed = 1
                await conn.execute(
                    "UPDATE task_human_verifications SET processed = 1, processed_time = ? WHERE id = ?",
                    (time.time(), record_id)
                )
                
                # Cập nhật checked = 1 và game_username
                await conn.execute(
                    "UPDATE users SET checked = 1, referral_status = 'confirmed', game_username = ? WHERE user_id = ?",
                    (game_username, str(user_id))
                )
                await conn.commit()
                
                # Cập nhật IP và trùng IP check
                await update_user_ip(user_id, ip_address)
                
                # Xử lý referral logic
                ref_id = await get_referrer(user_id)
                if ref_id:
                    if not await is_claimed_referral(user_id):
                        if await add_claimed_referral(user_id):
                            reward = await mb_get_invite_reward()
                            await update_user_balance(ref_id, reward)
                            try:
                                try:
                                    invited_user = await bot.get_chat(user_id)
                                    invited_full_name = get_full_name(invited_user)
                                except Exception:
                                    invited_full_name = f"User {user_id}"
                                
                                try:
                                    cfg_temp = await _mb_load_config()
                                    edition = cfg_temp.get('edition', 1)
                                    is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
                                    bonus_text = None
                                    if is_premium:
                                        bonus_text = load_premium_text('10')
                                    if bonus_text:
                                        bonus_text = bonus_text.replace("11,000 ᴠɴᴅ", f"{reward:,} ᴠɴ\u1d04")
                                        bonus_text = bonus_text.replace("Bin Siêu Quậy", f"<b>{invited_full_name}</b>")
                                    else:
                                        bonus_text = f"Bạn đã nhận được {reward:,} \u1d20\u0274\u1d04 khi mời <b>{invited_full_name}</b> tham gia."
                                    await bot.send_message(
                                        ref_id,
                                        bonus_text,
                                        parse_mode='HTML'
                                    )
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            await remove_invited_user(user_id)
                            
                # Thêm vào subscribed_users
                await add_subscribed_user(user_id)
                
            # Thông báo tham gia thành công
            full_name = get_full_name(message.from_user)
            cfg_temp = await _mb_load_config()
            edition = cfg_temp.get('edition', 1)
            is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
            welcome_ref = None
            if is_premium:
                welcome_ref = load_premium_text('9')
            if welcome_ref:
                welcome_ref = welcome_ref.replace("Cục Dàng Bin Siêu Quậy", f"<b>{full_name}</b>")
            else:
                welcome_ref = f"🎉 Chào Mừng <b>{full_name}</b> Đã Cùng Tham Gia!"
            await bot.send_message(
                chat_id,
                welcome_ref, 
                parse_mode='HTML'
            )
            
            # Kích hoạt start flow để show menu
            await trigger_start_flow_after_ip_check(user_id, chat_id)
            return

    # Chỉ xử lý nếu user đang chờ nhập tên tài khoản web
    if state and state.startswith('waiting_web_account:'):

        parts = state.split(':', 2)

        if len(parts) == 3:

            amount = int(parts[1])

            telegram_account = parts[2]

            web_account = message.text.strip()

            

            if not web_account:

                await bot.send_message(chat_id, "❌ Tên tài khoản web không được để trống. Vui lòng nhập lại:")

                return

            

            # Tạo yêu cầu đổi code

            request_id = await create_code_request(user_id, telegram_account, web_account, amount)

            

            # Trừ tiền từ tài khoản user

            await update_user_balance(user_id, -amount)

            

            # Xóa state

            await remove_user_state(user_id)

            

            # Gửi thông báo cho user

            cfg_temp = await _mb_load_config()
            edition = cfg_temp.get('edition', 1)
            is_premium = edition == 2 or str(edition) == '2' or edition == 'premium'
            _me = _bot_me_cache if _bot_me_cache else await bot.get_me()
            bot_link = f"https://t.me/{_me.username}"

            confirm_text = None
            if is_premium:
                confirm_text = load_premium_text('7')
            if confirm_text:
                confirm_text = confirm_text.replace("{bot_link}", bot_link)
            if not confirm_text:
                confirm_text = (
                    f"🎁 Hệ Thống Đã Gửi Yêu Cầu Đổi \n"
                    f"Điểm Thưởng CODE Đến Với Admin\n"
                    f"Vui Lòng Chờ Xử Lý Trong Giây Lát🎉\n\n"

                    "⚠️ Xin Hãy Lưu Ý ⚠️ : \n\n"

                    "- 🧧Yêu Cầu Thực Hiện Nạp Tiền \n"

                    "Vào TK Trong Ngày Để Đảm Bảo \n"

                    "Cộng Điểm CODE Thành Công‼️\n\n"

                    "- ✅ Trong Thời Gian Chờ Vui Lòng\n"

                    "Tham Gia Nhóm Bên Dưới Và Chụp \n"

                    "Lịch Sử Đổi Điểm Để Hệ Thống Xác \n"

                    "Minh Bạn Là Con Người Nha 👍🎊\n"
                    "https://t.me/sankeokhuyenmai8386\n"
                )
            await bot.send_message(chat_id, confirm_text, parse_mode='HTML')

            

            # Gửi thông tin đến admin với nút duyệt/từ chối

            full_name = get_full_name(message.from_user)

            admin_text = (

                f"📋 <b>Yêu cầu đổi code mới</b>\n\n"

                f"🆔 <b>Tài khoản Telegram:</b> {telegram_account} (@{message.from_user.username if message.from_user.username else 'N/A'})\n"

                f"🌐 <b>Tài khoản Web:</b> {web_account}\n"

                f"💰 <b>Số tiền:</b> {amount:,} VND\n"

                f"👤 <b>User ID:</b> {user_id}\n"

                f"📝 <b>Request ID:</b> {request_id}"

            )

            

            markup = types.InlineKeyboardMarkup(row_width=2)

            markup.add(

                types.InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_code:{request_id}"),

                types.InlineKeyboardButton("❌ Từ chối", callback_data=f"reject_code:{request_id}")

            )

            

            for admin_id in ADMINS:

                try:

                    await bot.send_message(

                        admin_id,

                        admin_text,

                        parse_mode='HTML',

                        reply_markup=markup

                    )

                except Exception as e:

                    logger.error(f"Failed to notify admin {admin_id}: {e}")

            return

    

    # Nếu không phải state đặc biệt, không xử lý gì (để các handler khác xử lý)



# ==================== THÔNG BÁO TỰ ĐỘNG HẰNG NGÀY ====================

async def send_daily_notification(user_id):
    """Gửi thông báo nhắc nhở hàng ngày cho một user"""
    try:
        text = (
            "🎯 NHẮC NHỞ HÀNG NGÀY 📆\n\n"
            "🎁 Đừng Quên Chia Sẽ Mời Bạn Bè Tham Gia Nhận Code Miễn Phí Mỗi Ngày Nhé 🎉\n\n"
            "✅ Vui Lòng Ấn /start Để Nhận Code\n\n"
            "🧧Hệ Thống Phát Code Đọc Quyền Chính Thức Với Cổng Game Nên Mọi Người Yên Tâm Trải Nghiệm Nha 🥰"
        )

        _me = _bot_me_cache if _bot_me_cache else await bot.get_me()
        bot_username = _me.username
        invite_link = f"https://t.me/{bot_username}?start={user_id}"
        
        min_withdraw = await mb_get_min_withdraw()
        min_wd_str = f"{min_withdraw // 1000}K"
        share_text = (
            f"👉 Rinh Ngay Code Khủng 🎉\n\n"
            f"✅ Ấn Tham Gia Link Bot:\n{invite_link}\n\n"
            f"🎁 Tham Gia Bot Rinh Code Tân Thủ Trị Giá {min_wd_str} Trải Nghiệm Miễn Phí Ko Cần Nạp 💥"
        )
        share_url = f"https://t.me/share/url?url={quote(invite_link)}&text={quote(share_text)}"

        btn_invite = types.InlineKeyboardButton("✅ Share Link Mời Bạn Bè", url=share_url)
        btn_checkin = types.InlineKeyboardButton("🧧Điểm Danh Mỗi Ngày", callback_data="daily_notif_checkin")
        btn_join_bot = types.InlineKeyboardButton("🎁 Tham Gia Nhận Code 🎁", url=f"https://t.me/{bot_username}?start=daily_notification")

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(btn_invite, btn_checkin, btn_join_bot)

        await bot.send_message(user_id, text, reply_markup=markup)
        return True
    except Exception as e:
        logger.error(f"Error sending daily notification to user {user_id}: {e}")
        return False

async def broadcast_daily_notifications():
    """Gửi thông báo nhắc nhở hằng ngày cho tất cả users"""
    try:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT user_id FROM users") as cursor:
                rows = await cursor.fetchall()
                target_users = [row['user_id'] for row in rows]
        
        if not target_users:
            logger.info("No users found for daily notification")
            return {'success': 0, 'fail': 0, 'total': 0}
        
        success = 0
        fail = 0
        total = len(target_users)
        
        logger.info(f"Starting daily notification broadcast to {total} users")
        
        for user_id in target_users:
            try:
                if await send_daily_notification(int(user_id)):
                    success += 1
                    await asyncio.sleep(0.05)  # Delay nhỏ để tránh spam
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                logger.error(f"Error sending notification to user {user_id}: {e}")
        
        logger.info(f"Daily notification broadcast completed: {success} success, {fail} failed")
        return {'success': success, 'fail': fail, 'total': total}
    except Exception as e:
        logger.error(f"Error in broadcast_daily_notifications: {e}")
        return {'success': 0, 'fail': 0, 'total': 0, 'error': str(e)}

async def schedule_daily_notifications():
    """Scheduler để gửi thông báo tự động mỗi 6 giờ (0h, 6h, 12h, 18h)"""
    while True:
        try:
            now = datetime.now(VIETNAM_TZ)
            current_hour = now.hour
            current_minute = now.minute
            
            # Gửi thông báo vào các giờ: 0h, 6h, 12h, 18h (vào phút 0)
            if current_hour in [0, 6, 12, 18] and current_minute == 0:
                logger.info(f"Sending daily notifications at {current_hour}:00")
                await broadcast_daily_notifications()
                
                # Reset điểm danh sau 23h59p chủ nhật (tức là 0h00p thứ 2)
                if now.weekday() == 0 and current_hour == 0:
                    logger.info("Resetting weekly checkins")
                    await reset_weekly_checkins()
                    
                # Chờ 60 giây để tránh gửi lại nhiều lần trong cùng phút
                await asyncio.sleep(60)
            else:
                # Kiểm tra mỗi phút
                await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in schedule_daily_notifications: {e}")
            await asyncio.sleep(60)

@bot.message_handler(commands=['guiallin'])
async def handle_guiallin(message):
    if message.from_user.id not in ADMINS:
        await bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    try:
        await bot.send_message(message.chat.id, "🚀 Đang gửi thông báo cho tất cả user...")
        
        async def broadcast_async():
            result = await broadcast_daily_notifications()
            if result and 'error' not in result:
                message_text = (
                    f"✅ **Đã hoàn thành gửi thông báo!**\n\n"
                    f"📊 **Thống kê:**\n"
                    f"• Tổng số user: {result.get('total', 0)}\n"
                    f"• Thành công: {result.get('success', 0)}\n"
                    f"• Thất bại: {result.get('fail', 0)}"
                )
            elif result and 'error' in result:
                message_text = f"❌ Lỗi khi gửi thông báo: {result.get('error', 'Unknown error')}"
            else:
                message_text = "✅ Đã hoàn thành gửi thông báo cho tất cả user!"
            
            await bot.send_message(message.chat.id, message_text, parse_mode='Markdown')
            
        asyncio.create_task(broadcast_async())
        
    except Exception as e:
        logger.error(f"Error in handle_guiallin: {e}")
        await bot.send_message(message.chat.id, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['ntkcute'])
async def handle_ntkcute(message):
    if message.from_user.id not in ADMINS:
        await bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    try:
        if await send_daily_notification(message.from_user.id):
            await bot.send_message(message.chat.id, "✅ Đã gửi thông báo hằng ngày thành công!")
        else:
            await bot.send_message(message.chat.id, "❌ Lỗi khi gửi thông báo hằng ngày.")
    except Exception as e:
        logger.error(f"Error in handle_ntkcute: {e}")
        await bot.send_message(message.chat.id, f"❌ Lỗi: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "daily_notif_checkin")
async def handle_daily_notif_checkin(call):
    await bot.answer_callback_query(call.id, "Đang tải thông tin điểm danh...")
    class FakeMessage:
        def __init__(self, from_user, chat_id):
            self.from_user = from_user
            self.chat = type('obj', (object,), {'id': chat_id})()
            self.text = '🎁 Điểm danh'
    
    fake_msg = FakeMessage(call.from_user, call.message.chat.id)
    await handle_checkin(fake_msg)

@bot.callback_query_handler(func=lambda call: call.data == "daily_notif_video")
async def handle_daily_notif_video(call):
    await bot.answer_callback_query(call.id, "Đang tải thông tin xem video...")
    
    user_id = call.from_user.id
    token_data = f"{user_id}_{int(time.time())}"
    token = base64.b64encode(token_data.encode()).decode()
    
    try:
        async with aiofiles.open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            content = await f.read()
            config = json.loads(content)
        domain = config.get('website_domain', 'https://mmovip247.online')
        bot_path = config.get('bot_path', '')
    except:
        domain = 'https://mmovip247.online'
        bot_path = ''
    
    if bot_path:
        video_link = f"{domain}/{bot_path}/mayman.php?token={token}"
    else:
        video_link = f"{domain}/mayman.php?token={token}"
        
    text = "🎬 **XEM VIDEO NHẬN THƯỞNG**\n\n"
    text += "💰 **Thông tin thưởng:**\n"
    text += "• Mỗi video: 150 VNĐ\n"
    text += "• Tối đa: 10 video/ngày\n"
    text += "• Tổng thưởng: 1,500 VNĐ/ngày\n\n"
    text += "⏰ **Lưu ý:**\n"
    text += "• Reset lượt xem sau 24h\n"
    text += "• Xem đầy đủ video để nhận thưởng\n\n"
    text += f"🔗 **Link xem video:**\n{video_link}\n\n"
    text += "📱 Nhấn vào link trên để bắt đầu xem video!"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 Xem Video Ngay", url=video_link))
    
    await bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')




@bot.message_handler(commands=['addcode'])

async def handle_addcode(message):

    if message.from_user.id not in ADMINS:

        await bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")

        return

    

    # Kiểm tra xem có reply tin nhắn không

    if not message.reply_to_message:

        await bot.reply_to(message, "Vui lòng reply tin nhắn chứa code để thêm vào danh sách.")

        return

    

    # Lấy nội dung từ tin nhắn được reply

    reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""

    if not reply_text:

        await bot.reply_to(message, "Tin nhắn được reply không có nội dung.")

        return

    

    # Trích xuất các code từ tin nhắn (mỗi dòng là một code)

    lines = reply_text.split('\n')

    new_codes = []

    for line in lines:
        line = line.strip()
        if line and len(line) > 3:
            new_codes.append(line)
    
    if not new_codes:
        await bot.reply_to(message, "Không tìm thấy mã code nào trong tin nhắn.")
        return
        
    try:
        current_codes = await load_redeemable_codes()
        current_codes.extend(new_codes)
        await save_redeemable_codes(current_codes)
        await bot.reply_to(message, f"✅ Đã thêm {len(new_codes)} mã code vào danh sách.")
    except Exception as e:
        logger.error(f"Failed to add codes: {e}")
        await bot.reply_to(message, "Đã xảy ra lỗi khi thêm mã code.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_code:', 'reject_code:')))
async def handle_code_approval(call):
    """Xử lý khi admin duyệt hoặc từ chối yêu cầu đổi code"""
    current_admins = await mb_get_admins()
    if call.from_user.id not in current_admins:
        await bot.answer_callback_query(call.id, "Bạn không có quyền thực hiện hành động này.", show_alert=True)
        return
    
    parts = call.data.split(':')
    action = parts[0]
    request_id = int(parts[1])
    
    # Lấy thông tin yêu cầu
    request = await get_code_request(request_id)
    if not request:
        await bot.answer_callback_query(call.id, "Không tìm thấy yêu cầu này.", show_alert=True)
        return
    
    if request['status'] != 'pending':
        await bot.answer_callback_query(call.id, "Yêu cầu này đã được xử lý rồi.", show_alert=True)
        return
    
    user_id = request['user_id']
    amount = request['amount']
    
    if action == 'approve_code':
        # Gọi logic duyệt nội bộ
        success, result, notification_sent = await approve_request_internal(request_id)
        if success:
            await bot.answer_callback_query(call.id, "Đã duyệt yêu cầu thành công!")
            
            # Cập nhật tin nhắn admin
            await bot.edit_message_text(
                f"✅ <b>Đã duyệt yêu cầu #{request_id}</b>\n\n"
                f"🆔 <b>Tài khoản Telegram:</b> {request['telegram_account']}\n"
                f"🌐 <b>Tài khoản Web:</b> {request['web_account']}\n"
                f"💰 <b>Số tiền:</b> {amount:,} VND\n"
                f"🎁 <b>Code đã phát:</b> <code>{result}</code>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        else:
            await bot.answer_callback_query(call.id, f"Lỗi: {result}", show_alert=True)
    
    elif action == 'reject_code':
        # Admin từ chối - hoàn tiền lại cho user
        await update_user_balance(user_id, amount)
        await update_code_request_status(request_id, 'rejected')
        
        # Thông báo cho user
        try:
            await bot.send_message(
                user_id,
                f"❌ Yêu cầu đổi code của bạn ({request['web_account']}) đã bị từ chối. Số tiền {amount:,} VND đã được hoàn lại vào tài khoản của bạn."
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
        
        # Cập nhật tin nhắn admin
        await bot.edit_message_text(
            f"❌ <b>Đã từ chối yêu cầu #{request_id}</b>\n\n"
            f"🆔 <b>Tài khoản Telegram:</b> {request['telegram_account']}\n"
            f"🌐 <b>Tài khoản Web:</b> {request['web_account']}\n"
            f"💰 <b>Số tiền:</b> {amount:,} VND\n"
            f"💵 <b>Đã hoàn tiền lại cho user</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
        await bot.answer_callback_query(call.id, "Đã từ chối yêu cầu và hoàn tiền lại cho user!")



# Task queue processor

async def process_task_queue():

    while True:

        task = await task_queue.get()

        try:

            await task

        except Exception as e:

            logger.error(f"Task failed: {e}")

        finally:

            task_queue.task_done()



async def trigger_start_flow_after_ip_check(user_id, chat_id):
    try:
        class _FakeFromUser:
            pass
        class _FakeChat:
            pass
        class _FakeMessage:
            pass
            
        fake_from = _FakeFromUser()
        fake_from.id = int(user_id)
        fake_from.username = None
        
        async with get_db_connection() as conn:
            async with conn.execute("SELECT username FROM users WHERE user_id = ?", (str(user_id),)) as cursor:
                row = await cursor.fetchone()
                if row and row['username']:
                    fake_from.username = row['username']
                    
        fake_chat = _FakeChat()
        fake_chat.id = int(chat_id)
        
        fake_message = _FakeMessage()
        fake_message.from_user = fake_from
        fake_message.chat = fake_chat
        fake_message.text = "/start"
        
        await handle_start(fake_message)
    except Exception as e:
        logger.error(f"Error triggering start flow after IP check for user {user_id}: {e}")

async def process_task_human_verifications():
    """Xử lý các xác minh 'tôi là con người' đã click từ web."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                """SELECT id, user_id, task_name, chat_id, source_message_id, ip_address
                   FROM task_human_verifications
                   WHERE used = 1 AND processed = 0
                   ORDER BY used_time ASC
                   LIMIT 20"""
            ) as cursor:
                rows = await cursor.fetchall()
            
            if not rows:
                return

            for row in rows:
                record_id, user_id, task_name, chat_id, source_message_id, ip_address = row
                
                if task_name == JOIN_HUMAN_VERIFY_TASK:
                    # Đánh dấu processed = 2 để khóa
                    await conn.execute(
                        "UPDATE task_human_verifications SET processed = 2 WHERE id = ? AND processed = 0",
                        (record_id,)
                    )
                    await conn.commit()
                    
                    async with conn.execute(
                        "SELECT processed FROM task_human_verifications WHERE id = ?",
                        (record_id,)
                    ) as cursor:
                        check_row = await cursor.fetchone()
                        
                    if not check_row or check_row['processed'] != 2:
                        continue
                else:
                    # Đánh dấu processed = 1
                    await conn.execute(
                        "UPDATE task_human_verifications SET processed = 1, processed_time = ? WHERE id = ? AND processed = 0",
                        (time.time(), record_id)
                    )
                    await conn.commit()
                    
                    async with conn.execute(
                        "SELECT processed FROM task_human_verifications WHERE id = ?",
                        (record_id,)
                    ) as cursor:
                        check_row = await cursor.fetchone()
                        
                    if not check_row or check_row['processed'] != 1:
                        continue

                try:
                    if not ip_address or str(ip_address).upper() == "UNKNOWN":
                        logger.warning(f"Skip human verification record {record_id}: missing IP")
                        continue

                    user_id_int = int(user_id)
                    chat_id_int = int(chat_id)
                    source_message_id_int = int(source_message_id) if source_message_id else 0

                    if task_name == JOIN_HUMAN_VERIFY_TASK:
                        await cleanup_messages(user_id_int, chat_id_int)
                        if source_message_id_int > 0:
                            try:
                                await bot.delete_message(chat_id_int, source_message_id_int)
                            except Exception:
                                pass
                        
                        game_link = await mb_get_game_link()
                        prompt_text = (
                            "✅ Gửi Tài Khoản Game Nhận Code Miễn Phí, Nếu Chưa Đăng Kí Vui Lòng Đăng Kí Link Dưới Và Gửi Tên TK Game Để Kích Hoạt Bot Nha ❤️\n\n"
                            "🌈 Link Đăng Kí Game 👇:\n"
                            f"{game_link}"
                        )
                        sent_msg = await bot.send_message(chat_id_int, prompt_text, parse_mode='HTML')
                        await set_user_state(user_id_int, f"waiting_game_username:{sent_msg.message_id}:{record_id}")
                    else:
                        await update_user_ip(user_id_int, ip_address)

                except Exception as e:
                    logger.error(f"Error processing human verification record {record_id}: {e}")
    except Exception as e:
        logger.error(f"Error in process_task_human_verifications: {e}")

async def task_human_verification_worker():
    """Worker xử lý xác minh con người định kỳ."""
    while True:
        try:
            await process_task_human_verifications()
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error in task_human_verification_worker: {e}")
            await asyncio.sleep(5)

async def main():
    logger.info("Starting bot...")
    try:
        await init_db()
        await initialize_data()
        # Start task queue processor
        asyncio.create_task(process_task_queue())
        # Start daily notifications scheduler
        asyncio.create_task(schedule_daily_notifications())
        # Start human verification worker task
        asyncio.create_task(task_human_verification_worker())
        # Polling with all necessary updates enabled
        await bot.infinity_polling(
            # NOTE: `timeout` is long-poll wait; `request_timeout` must be > `timeout`
            # or the HTTP client will time out before Telegram responds.
            timeout=60,
            request_timeout=90,
            allowed_updates=['message', 'callback_query', 'message_reaction', 'chat_member']
        )
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise



if __name__ == "__main__":

    asyncio.run(main())


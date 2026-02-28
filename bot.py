import logging
import asyncio
import re
from datetime import datetime
from contextlib import suppress

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

from config import BOT_TOKEN, ADMIN_IDS, SECRET_GROUP_ID, USER_LIMIT, TIME_WINDOW
from database import Database
from downloader import VideoDownloader
from middlewares import ForceJoinMiddleware, RateLimitMiddleware
from admin_panel import AdminPanel, AdminStates, process_broadcast, process_forward, process_inline_text, process_inline_buttons, process_channel_add, process_channel_remove, process_admin_add, process_admin_remove

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot va dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Database
db = Database('bot_database.db')

# Video downloader
downloader = VideoDownloader(bot, SECRET_GROUP_ID)

# Middleware'lar
dp.message.middleware(ForceJoinMiddleware(db, bot))
dp.message.middleware(RateLimitMiddleware(db, USER_LIMIT, TIME_WINDOW))

# Admin panel
admin_panel = AdminPanel(dp, db, bot)

class UserStates(StatesGroup):
    waiting_for_link = State()

@dp.message(CommandStart())
async def start_command(message: Message):
    """Start komandasi - faqat bot ma'lumoti"""
    user = message.from_user
    
    # Foydalanuvchini ma'lumotlar bazasiga qo'shish
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Bot haqida to'liq ma'lumot (kanallarsiz)
    text = (
        f"👋 Salom, {user.first_name}! Xush kelibsiz!\n\n"
        "Men — **TopldiBot** 🤖\n"
        "Instagram va TikTok videolarini bir zumda yuklab beraman ⚡\n\n"
        "📥 **Nimalar qila olaman?**\n"
        "• Instagram videolarni yuklab beraman\n"
        "• TikTok videolarni watermark-siz chiqaraman\n"
        "• Link orqali ishlayman — oson va tez\n"
        "• Oldin yuklangan video bo‘lsa, 1 soniyada yetkazaman 🚀\n"
        "• Video sifati maksimal bo‘ladi\n\n"
        "🧠 **Qanday ishlaydi?**\n"
        "1️⃣ Instagram yoki TikTok video linkini nusxa ol\n"
        "2️⃣ Shu yerga tashla\n"
        "3️⃣ Video tayyor 🎬\n\n"
        "Boshlash uchun link yuboring 👇"
    )
    
    await message.reply(text, parse_mode="Markdown")

@dp.message(Command("help"))
async def help_command(message: Message):
    """Yordam komandasi"""
    await message.reply(
        "📚 **Yordam**\n\n"
        "**Qanday ishlaydi?**\n"
        "1. Instagram yoki TikTok video linkini yuboring\n"
        "2. Bot videoni yuklab oladi\n"
        "3. Sizga video sifatli holatda yuboriladi\n\n"
        "**Qo'llab-quvvatlanadigan linklar:**\n"
        "• Instagram post/reel\n"
        "• TikTok video\n\n"
        "**Buyruqlar:**\n"
        "/start - Botni ishga tushirish\n"
        "/help - Yordam\n"
        "/stats - Statistikangiz",
        parse_mode="Markdown"
    )

@dp.message(Command("stats"))
async def user_stats(message: Message):
    """Foydalanuvchi statistikasi"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Siz haqingizda ma'lumot topilmadi.")
        return
    
    await message.reply(
        f"📊 **Sizning statistikangiz**\n\n"
        f"📥 Yuklagan videolaringiz: {user['total_downloads']}\n"
        f"🕐 Qo'shilgan sana: {user['joined_date'][:10] if user['joined_date'] else 'N/A'}\n"
        f"📅 Oxirgi faollik: {user['last_activity'][:10] if user['last_activity'] else 'N/A'}",
        parse_mode="Markdown"
    )

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    """Holatni bekor qilish"""
    current_state = await state.get_state()
    if current_state is None:
        await message.reply("Bekor qilish uchun hech narsa yo'q.")
        return
    
    await state.clear()
    await message.reply("✅ Amal bekor qilindi.")

# ========== MAJBURIY OBUNA CHECK ==========
@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    """Obunani tekshirish va tasdiqlash"""
    user_id = callback.from_user.id
    
    # Kanallarni olish
    channels = await db.get_channels()
    if not channels:
        await callback.answer("Kanallar mavjud emas!", show_alert=True)
        return
    
    not_joined = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel['channel_id'],
                user_id=user_id
            )
            
            if member.status in ['left', 'kicked']:
                not_joined.append(channel)
        except Exception as e:
            print(f"Xatolik: {e}")
            not_joined.append(channel)
    
    if not_joined:
        # Hali ham obuna bo'lmagan kanallar
        text = "❌ Siz hali ham quyidagi kanallarga obuna bo'lmagansiz:\n\n"
        
        keyboard = []
        for channel in not_joined:
            if channel['channel_username']:
                text += f"• {channel['channel_title']}\n"
                btn = InlineKeyboardButton(
                    text=f"📢 {channel['channel_title']}", 
                    url=f"https://t.me/{channel['channel_username'].replace('@', '')}"
                )
                keyboard.append([btn])
        
        keyboard.append([InlineKeyboardButton(
            text="🔄 Qayta tekshirish", 
            callback_data="check_subscription"
        )])
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer("Obuna bo'lmagan kanallar bor!", show_alert=True)
    else:
        # Barcha kanallarga obuna bo'lgan
        await callback.message.delete()
        await callback.message.answer(
            "✅ Obuna tasdiqlandi! Endi video yuklab olishingiz mumkin.\n\n"
            "Menga Instagram yoki TikTok video linkini yuboring 👇"
        )
        await callback.answer("Obuna tasdiqlandi!", show_alert=True)

# ========== ADMIN STATE HANDLERS (BIRINCHI TEKSHIRILADI) ==========
@dp.message(AdminStates.waiting_for_admin_add)
async def admin_add_state_handler(message: Message, state: FSMContext):
    """Admin qo'shish state handler"""
    logger.info(f"Admin qo'shish state: {message.text}")
    await process_admin_add(message, state, db)

@dp.message(AdminStates.waiting_for_admin_remove)
async def admin_remove_state_handler(message: Message, state: FSMContext):
    """Admin o'chirish state handler"""
    logger.info(f"Admin o'chirish state: {message.text}")
    await process_admin_remove(message, state, db)

@dp.message(AdminStates.waiting_for_channel_add)
async def channel_add_state_handler(message: Message, state: FSMContext):
    """Kanal qo'shish state handler"""
    logger.info(f"Kanal qo'shish state: {message.text}")
    await process_channel_add(message, state, db, bot)

@dp.message(AdminStates.waiting_for_channel_remove)
async def channel_remove_state_handler(message: Message, state: FSMContext):
    """Kanal o'chirish state handler"""
    logger.info(f"Kanal o'chirish state: {message.text}")
    await process_channel_remove(message, state, db)

@dp.message(AdminStates.waiting_for_broadcast)
async def broadcast_state_handler(message: Message, state: FSMContext):
    """Broadcast state handler"""
    logger.info(f"Broadcast state: {message.text}")
    await process_broadcast(message, state, db, bot)

@dp.message(AdminStates.waiting_for_forward)
async def forward_state_handler(message: Message, state: FSMContext):
    """Forward state handler"""
    logger.info(f"Forward state: {message.text}")
    await process_forward(message, state, db, bot)

@dp.message(AdminStates.waiting_for_inline_text)
async def inline_text_state_handler(message: Message, state: FSMContext):
    """Inline xabar matnini qabul qilish"""
    logger.info(f"Inline text state: {message.text}")
    await process_inline_text(message, state, db, bot)

@dp.message(AdminStates.waiting_for_inline_buttons)
async def inline_buttons_state_handler(message: Message, state: FSMContext):
    """Inline xabar tugmalarini qabul qilish"""
    logger.info(f"Inline buttons state: {message.text}")
    await process_inline_buttons(message, state, db, bot)

# ========== VIDEO LINK HANDLER ==========
@dp.message(F.text)
async def handle_link(message: Message, state: FSMContext):
    """Linklarni qayta ishlash (faqat state bo'lmasa)"""
    
    # Agar state bo'lsa, bu handler ishlamasligi kerak
    current_state = await state.get_state()
    if current_state is not None:
        logger.info(f"State mavjud: {current_state}, link handler ishlamaydi")
        return
    
    url = message.text.strip()
    logger.info(f"Link keldi: {url}")
    
    # Aktivlikni yangilash
    await db.update_activity(message.from_user.id)
    
    # Linkni tekshirish
    if not re.search(r'https?://', url):
        await message.reply(
            "❌ Iltimos, to'g'ri video link yuboring!\n\n"
            "Misol: https://www.instagram.com/p/XXXXX/"
        )
        return
    
    # Platformani aniqlash
    platform = None
    if 'instagram.com' in url or 'instagr.am' in url or 'ddinstagram.com' in url:
        platform = 'instagram'
    elif 'tiktok.com' in url or 'vm.tiktok.com' in url or 'musical.ly' in url:
        platform = 'tiktok'
    
    if not platform:
        await message.reply(
            "❌ Faqat Instagram va TikTok linklari qabul qilinadi!"
        )
        return
    
    # Yuklashni boshlash
    status_msg = await message.reply("⏳ Video yuklanmoqda...")
    
    try:
        # Bazada video borligini tekshirish
        cached_video = await db.get_video(url)
        
        if cached_video and cached_video.get('group_message_id') and cached_video['group_message_id'] != 0:
            # Keshdan olingan video
            await status_msg.edit_text("⚡️ Video tayyor, yuborilmoqda...")
            
            try:
                # Videoni guruhdan olish
                file_id = await downloader.get_video_from_group(cached_video['group_message_id'])
                
                if file_id:
                    await message.reply_video(
                        video=file_id,
                        caption=f"✅ Video tayyor! (keshlangan)\n\n"
                                f"📊 Ko'rishlar: {cached_video['access_count'] + 1}\n"
                                f"📱 Platforma: {cached_video['platform']}",
                        supports_streaming=True
                    )
                    
                    # Yuklash tarixiga qo'shish
                    await db.add_download(
                        user_id=message.from_user.id,
                        video_url=url,
                        platform=platform,
                        from_cache=True
                    )
                    
                    await status_msg.delete()
                    return
            except Exception as e:
                logger.error(f"Keshdan olishda xatolik: {e}")
                # Agar xatolik bo'lsa, qayta yuklashga o'tamiz
        
        # Yangi video yuklash
        await status_msg.edit_text("⏳")
        
        file_id, error = await downloader.download_video(url)
        
        if error:
            await status_msg.edit_text(f"❌ {error}")
            return
        
        # Videoni foydalanuvchiga yuborish
        await status_msg.edit_text("📤 Video yuborilmoqda...")
        
        await message.reply_video(
            video=file_id,
            caption=f"@TopldiSaveBot orqali yuklab olindi.",
            supports_streaming=True
        )
        
        # Videoni bazaga qo'shish (group_message_id keyinroq qo'shiladi)
        try:
            await db.add_video(
                video_url=url,
                platform=platform,
                video_id=url.split('/')[-1][:50],
                file_id=file_id,
                group_message_id=0
            )
        except Exception as e:
            logger.error(f"Videoni bazaga qo'shishda xatolik: {e}")
        
        # Yuklash tarixiga qo'shish
        await db.add_download(
            user_id=message.from_user.id,
            video_url=url,
            platform=platform,
            from_cache=False
        )
        
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await status_msg.edit_text(
            "❌ Videoni yuklashda xatolik yuz berdi.\n"
            "Iltimos, qaytadan urinib ko'ring yoki boshqa link yuboring."
        )

@dp.message()
async def handle_unknown(message: Message):
    """Noma'lum xabarlar"""
    await message.reply(
        "❌ Iltimos, video link yuboring!\n\n"
        "Misol: https://www.instagram.com/p/XXXXX/"
    )

async def on_startup():
    """Bot ishga tushganda"""
    logger.info("Bot ishga tushmoqda...")
    
    # Ma'lumotlar bazasini yaratish
    await db.init_db()
    
    # Adminlarni qo'shish
    for admin_id in ADMIN_IDS:
        await db.add_admin(admin_id)
        logger.info(f"Admin qo'shildi: {admin_id}")
    
    # Maxfiy guruhni tekshirish
    try:
        chat = await bot.get_chat(SECRET_GROUP_ID)
        logger.info(f"Maxfiy guruh ulandi: {chat.title}")
        
        # Botni guruhda adminlikka tekshirish
        bot_member = await bot.get_chat_member(SECRET_GROUP_ID, bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            logger.warning("Bot guruhda admin emas! Iltimos, botni guruhga admin qiling!")
    except Exception as e:
        logger.error(f"Maxfiy guruhga ulanishda xatolik: {e}")
        logger.warning("Iltimos, botni maxfiy guruhga admin qiling! ID: " + str(SECRET_GROUP_ID))
    
    logger.info("Bot muvaffaqiyatli ishga tushdi!")

async def on_shutdown():
    """Bot to'xtaganda"""
    logger.info("Bot to'xtatilmoqda...")
    await bot.session.close()
    logger.info("Bot to'xtatildi.")

async def main():
    """Asosiy funksiya"""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
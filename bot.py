import logging
import asyncio
import re
import os
from datetime import datetime
from contextlib import suppress

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

from config import BOT_TOKEN, ADMIN_IDS, SECRET_GROUP_ID, USER_LIMIT, TIME_WINDOW
from database import Database
from downloader import VideoDownloader
from middlewares import ForceJoinMiddleware, RateLimitMiddleware
from admin_panel import AdminPanel, AdminStates, process_broadcast, process_forward, process_inline, process_channel_add, process_channel_remove, process_admin_add, process_admin_remove

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

# Database (D diskida)
db = Database('D:/topldibot_database.db')

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
    """Start komandasi"""
    user = message.from_user
    
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    text = (
        f"👋 Salom, {user.first_name}! Xush kelibsiz!\n\n"
        "🤖 Men — TopildiSaveBot\n"
        "Instagram platformasida sizga video va reels larni tez yuklab beraman\n\n"
        "⚡️ Qanday ishlayman?\n"
        "1️⃣ Instagram'dan video linkini nusxa oling\n"
        "2️⃣ Menga tashlang\n"
        "3️⃣ Men bir zumda yuklab beraman\n\n"
        "📥 Yuklaydigan formatlar:\n"
        "• 📱 Post (foto/video)\n"
        "• 🎬 Reel (qisqa video)\n\n"
        "🔥 Tezlik:\n"
        "• Birinchi marta: 5-10 soniya\n"
        "• Keyingi marta: 1-2 soniya\n\n"
        "✨ Qulayliklar:\n"
        "• ✅ Bepul va cheksiz\n"
        "• ✅ Yuqori sifat (1080p)\n"
        "• ✅ Ortiqcha reklamalar yo'q\n\n"
        "⚠️ Faqat Instagram linklari qabul qilinadi!\n\n"
        "Endi menga link tashlang! 👇"
    )
    
    await message.reply(text)

@dp.message(Command("help"))
async def help_command(message: Message):
    """Yordam komandasi"""
    text = (
        "👨‍💻 Admin: @azbeyy\n\n"
        "📌 Buyruqlar:\n"
        "/start - Botni ishga tushirish\n"
        "/stats - Statistikangiz\n"
        "/help - Yordam"
    )
    await message.reply(text)

@dp.message(Command("stats"))
async def user_stats(message: Message):
    """Foydalanuvchi statistikasi"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Siz haqingizda ma'lumot topilmadi.")
        return
    
    await message.reply(
        f"📊 Sizning statistikangiz\n\n"
        f"📥 Yuklagan videolaringiz: {user['total_downloads']}\n"
        f"🕐 Qo'shilgan sana: {user['joined_date'][:10] if user['joined_date'] else 'N/A'}\n"
        f"📅 Oxirgi faollik: {user['last_activity'][:10] if user['last_activity'] else 'N/A'}"
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

# ========== ADMIN STATE HANDLERS ==========
@dp.message(AdminStates.waiting_for_broadcast)
async def broadcast_state_handler(message: Message, state: FSMContext):
    await process_broadcast(message, state, db, bot)

@dp.message(AdminStates.waiting_for_forward)
async def forward_state_handler(message: Message, state: FSMContext):
    await process_forward(message, state, db, bot)

@dp.message(AdminStates.waiting_for_inline)
async def inline_state_handler(message: Message, state: FSMContext):
    await process_inline(message, state, db, bot)

@dp.message(AdminStates.waiting_for_channel_add)
async def channel_add_state_handler(message: Message, state: FSMContext):
    await process_channel_add(message, state, db, bot)

@dp.message(AdminStates.waiting_for_channel_remove)
async def channel_remove_state_handler(message: Message, state: FSMContext):
    await process_channel_remove(message, state, db)

@dp.message(AdminStates.waiting_for_admin_add)
async def admin_add_state_handler(message: Message, state: FSMContext):
    await process_admin_add(message, state, db)

@dp.message(AdminStates.waiting_for_admin_remove)
async def admin_remove_state_handler(message: Message, state: FSMContext):
    await process_admin_remove(message, state, db)

# ========== INSTAGRAM VIDEO HANDLER ==========
@dp.message(F.text)
async def handle_instagram_link(message: Message, state: FSMContext):
    """Faqat Instagram linklarini qayta ishlash"""
    
    # Agar state bo'lsa, uni bajaramiz
    current_state = await state.get_state()
    if current_state is not None:
        return
    
    url = message.text.strip()
    logger.info(f"Link keldi: {url}")
    
    # Aktivlikni yangilash
    await db.update_activity(message.from_user.id)
    
    # Link borligini tekshirish
    if not re.search(r'https?://', url):
        await message.reply("❌ Xato!\n\nBu link emas. Iltimos, Instagram video linkini yuboring.")
        return
    
    # FAQAT INSTAGRAM linklarini tekshirish
    instagram_patterns = [
        r'instagram\.com/(p|reel|tv)/',
        r'instagr\.am/',
        r'ddinstagram\.com/'
    ]
    
    is_instagram = False
    for pattern in instagram_patterns:
        if re.search(pattern, url):
            is_instagram = True
            break
    
    if not is_instagram:
        await message.reply(
            "❌ Noto'g'ri link!\n\n"
            "Bu bot FAQAT INSTAGRAM videolarini yuklab beradi.\n"
            "Iltimos, Instagram video linkini yuboring.\n\n"
            "Misol: https://www.instagram.com/reel/xxxxx/"
        )
        return
    
    # Yuklashni boshlash - FAQAT QUM SOAT
    status_msg = await message.reply("⏳")
    
    try:
        # BAZADA VIDEO BORLIGINI TEKSHIRISH (KESH)
        cached_video = await db.get_video(url)
        
        if cached_video:
            # Keshdan olish
            try:
                # Bazadan file_id ni olish
                file_id = cached_video.get('file_id')
                
                # Agar file_id bo'lmasa yoki eskirgan bo'lsa, guruhdan olish
                if not file_id and cached_video.get('group_message_id'):
                    file_id = await downloader.get_video_from_group(cached_video['group_message_id'])
                
                if file_id:
                    await message.reply_video(
                        video=file_id,
                        caption=f"📥 @TopildiSaveBot orqali yuklab olindi",
                        supports_streaming=True
                    )
                    
                    await db.add_download(
                        user_id=message.from_user.id,
                        video_url=url,
                        platform='instagram',
                        from_cache=True
                    )
                    
                    await status_msg.delete()
                    return
                else:
                    logger.warning("Keshda video topilmadi, qayta yuklanmoqda")
            except Exception as e:
                logger.error(f"Keshdan olishda xatolik: {e}")
        
        # YANGI VIDEO YUKLASH
        # 3 ta qiymat qaytadi: file_id, error, group_message_id
        file_id, error, group_message_id = await downloader.download_instagram_video(url)
        
        if error:
            await status_msg.edit_text(error)
            return
        
        if file_id:
            # File ID bilan video yuborish
            await message.reply_video(
                video=file_id,
                caption=f"📥 @TopildiSaveBot orqali yuklab olindi",
                supports_streaming=True
            )
            
            # BAZAGA QO'SHISH (group_message_id bilan)
            try:
                await db.add_video(
                    video_url=url,
                    platform='instagram',
                    video_id=url.split('/')[-1][:50],
                    file_id=file_id,
                    group_message_id=group_message_id if group_message_id else 0
                )
                logger.info(f"✅ Video bazaga qo'shildi")
            except Exception as e:
                logger.error(f"Videoni bazaga qo'shishda xatolik: {e}")
            
            await db.add_download(
                user_id=message.from_user.id,
                video_url=url,
                platform='instagram',
                from_cache=False
            )
            
            await status_msg.delete()
        else:
            await message.reply("❌ Video yuklanmadi")
        
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await message.reply("⚠️ Kutilmagan xatolik! Iltimos, qaytadan urinib ko'ring.")

@dp.message()
async def handle_unknown(message: Message):
    """Noma'lum xabarlar"""
    await message.reply(
        "❌ Noto'g'ri buyruq!\n\n"
        "Bu bot FAQAT INSTAGRAM videolarini yuklab beradi.\n"
        "Iltimos, Instagram video linkini yuboring.\n\n"
        "Misol: https://www.instagram.com/reel/xxxxx/"
    )

# ========== MAJBURIY OBUNA CHECK ==========
@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    """Obunani tekshirish va tasdiqlash"""
    user_id = callback.from_user.id
    
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
        text = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
        
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
            text="✅ Obuna bo'ldim", 
            callback_data="check_subscription"
        )])
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer("Obuna bo'lmagan kanallar bor!", show_alert=True)
    else:
        await callback.message.delete()
        await callback.message.answer(
            "✅ Obuna tasdiqlandi!\n\n"
            "Endi Instagram videolarini yuklab olishingiz mumkin."
        )
        await callback.answer("Obuna tasdiqlandi!", show_alert=True)

async def on_startup():
    """Bot ishga tushganda"""
    logger.info("Bot ishga tushmoqda...")
    
    # D:/temp papkasini yaratish
    if not os.path.exists("D:/temp"):
        os.makedirs("D:/temp")
        logger.info("D:/temp papkasi yaratildi")
    
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
        
        bot_member = await bot.get_chat_member(SECRET_GROUP_ID, bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            logger.warning("Bot guruhda admin emas! Iltimos, botni guruhga admin qiling!")
    except Exception as e:
        logger.error(f"Maxfiy guruhga ulanishda xatolik: {e}")
        logger.warning("Iltimos, botni maxfiy guruhga admin qiling! ID: " + str(SECRET_GROUP_ID))
    
    # Cookies faylini tekshirish
    if os.path.exists("cookies.txt"):
        logger.info("Cookies fayli topildi")
    else:
        logger.warning("Cookies fayli topilmadi! Instagram video yuklanmasligi mumkin.")
    
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
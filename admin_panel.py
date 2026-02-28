from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from datetime import datetime
import asyncio

from database import Database

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_forward = State()
    waiting_for_inline_text = State()
    waiting_for_inline_buttons = State()
    waiting_for_channel_add = State()
    waiting_for_channel_remove = State()
    waiting_for_admin_add = State()
    waiting_for_admin_remove = State()

class AdminPanel:
    def __init__(self, dp: Dispatcher, db: Database, bot: Bot):
        self.dp = dp
        self.db = db
        self.bot = bot
        self._register_handlers()
    
    def _register_handlers(self):
        """Admin handlerlarini ro'yxatdan o'tkazish"""
        
        @self.dp.message(Command("admin"))
        async def admin_panel(message: Message):
            """Admin panelni ochish"""
            # Admin tekshirish
            is_admin = await self.db.is_admin(message.from_user.id)
            if not is_admin:
                await message.reply("❌ Bu buyruq faqat adminlar uchun!")
                return
            
            # Tugmalar
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
                [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
                [InlineKeyboardButton(text="📢 Oddiy xabar", callback_data="admin_broadcast")],
                [InlineKeyboardButton(text="📢 Forward xabar", callback_data="admin_forward")],
                [InlineKeyboardButton(text="🔘 Tugmali xabar", callback_data="admin_inline")],
                [InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels")],
                [InlineKeyboardButton(text="👤 Adminlar", callback_data="admin_admins")],
                [InlineKeyboardButton(text="⚙️ Majburiy obuna", callback_data="admin_force_join")],
                [InlineKeyboardButton(text="❌ Chiqish", callback_data="admin_exit")]
            ])
            
            await message.reply(
                "👑 Admin Panel\n\n"
                "Kerakli bo'limni tanlang:",
                reply_markup=keyboard
            )
        
        @self.dp.callback_query(F.data.startswith("admin_"))
        async def admin_callback(callback: CallbackQuery, state: FSMContext):
            """Admin callback'larini boshqarish"""
            
            action = callback.data.replace("admin_", "")
            
            # Orqaga tugmasi uchun alohida tekshirish
            if action == "back":
                await self._show_main_menu(callback.message)
                await callback.answer()
                return
            
            # Qolgan actionlar uchun admin tekshirish
            is_admin = await self.db.is_admin(callback.from_user.id)
            if not is_admin:
                await callback.answer("Siz admin emassiz!", show_alert=True)
                return
            
            if action == "stats":
                await self._show_stats(callback)
            elif action == "users":
                await self._show_users(callback)
            elif action == "broadcast":
                await self._start_broadcast(callback, state)
            elif action == "forward":
                await self._start_forward(callback, state)
            elif action == "inline":
                await self._start_inline(callback, state)
            elif action == "channels":
                await self._manage_channels(callback)
            elif action == "admins":
                await self._manage_admins(callback)
            elif action == "force_join":
                await self._manage_force_join(callback)
            elif action == "exit":
                await callback.message.delete()
                await callback.answer("Panel yopildi")
            elif action == "add_channel":
                await self._add_channel_start(callback, state)
            elif action == "remove_channel":
                await self._remove_channel_start(callback, state)
            elif action == "add_admin":
                await self._add_admin_start(callback, state)
            elif action == "remove_admin":
                await self._remove_admin_start(callback, state)
            elif action == "force_join_on":
                await self.db.set_force_join(True)
                await callback.answer("✅ Majburiy obuna yoqildi")
                await self._manage_force_join(callback)
            elif action == "force_join_off":
                await self.db.set_force_join(False)
                await callback.answer("❌ Majburiy obuna o'chirildi")
                await self._manage_force_join(callback)
            
            await callback.answer()
    
    async def _show_main_menu(self, message: Message):
        """Asosiy admin menyusini ko'rsatish"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📢 Oddiy xabar", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📢 Forward xabar", callback_data="admin_forward")],
            [InlineKeyboardButton(text="🔘 Tugmali xabar", callback_data="admin_inline")],
            [InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels")],
            [InlineKeyboardButton(text="👤 Adminlar", callback_data="admin_admins")],
            [InlineKeyboardButton(text="⚙️ Majburiy obuna", callback_data="admin_force_join")],
            [InlineKeyboardButton(text="❌ Chiqish", callback_data="admin_exit")]
        ])
        
        await message.edit_text(
            "👑 Admin Panel\n\n"
            "Kerakli bo'limni tanlang:",
            reply_markup=keyboard
        )
    
    async def _show_stats(self, callback: CallbackQuery):
        """Statistika ko'rsatish"""
        total_users = await self.db.get_user_count()
        daily_active = await self.db.get_active_users('day')
        weekly_active = await self.db.get_active_users('week')
        monthly_active = await self.db.get_active_users('month')
        total_downloads = await self.db.get_total_downloads()
        
        text = (
            f"📊 Statistika\n\n"
            f"👥 Umumiy: {total_users}\n"
            f"📅 Kunlik: {daily_active}\n"
            f"📆 Haftalik: {weekly_active}\n"
            f"📊 Oylik: {monthly_active}\n"
            f"📥 Yuklamalar: {total_downloads}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _show_users(self, callback: CallbackQuery):
        """Foydalanuvchilar ro'yxati"""
        users = await self.db.get_all_users()
        text = f"👥 Foydalanuvchilar: {len(users)}\n\n"
        
        for i, user in enumerate(users[:5], 1):
            username = f"@{user['username']}" if user['username'] else "No username"
            text += f"{i}. {user['first_name']} {username}\n"
            text += f"   📥 {user['total_downloads']} ta video\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _start_broadcast(self, callback: CallbackQuery, state: FSMContext):
        """Oddiy xabar yuborishni boshlash"""
        await state.set_state(AdminStates.waiting_for_broadcast)
        await callback.message.edit_text(
            "📢 Oddiy xabar yuborish\n\n"
            "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:"
        )
    
    async def _start_forward(self, callback: CallbackQuery, state: FSMContext):
        """Forward xabar yuborishni boshlash"""
        await state.set_state(AdminStates.waiting_for_forward)
        await callback.message.edit_text(
            "📢 Forward xabar yuborish\n\n"
            "Barcha foydalanuvchilarga forward qilmoqchi bo'lgan xabaringizni yuboring:"
        )
    
    async def _start_inline(self, callback: CallbackQuery, state: FSMContext):
        """Tugmali xabar yuborishni boshlash - 1-qadam: matn"""
        await state.set_state(AdminStates.waiting_for_inline_text)
        await callback.message.edit_text(
            "🔘 Tugmali xabar yuborish (1/2)\n\n"
            "Xabar matnini yozing:"
        )
    
    async def _manage_channels(self, callback: CallbackQuery):
        """Kanallarni boshqarish"""
        channels = await self.db.get_channels()
        
        text = "📢 Kanallar\n\n"
        if not channels:
            text += "Hozircha kanallar yo'q"
        else:
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['channel_title']}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qo'shish", callback_data="admin_add_channel")],
            [InlineKeyboardButton(text="➖ O'chirish", callback_data="admin_remove_channel")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _manage_admins(self, callback: CallbackQuery):
        """Adminlarni boshqarish"""
        admins = await self.db.get_admins()
        
        text = "👤 Adminlar\n\n"
        if not admins:
            text += "Hozircha adminlar yo'q"
        else:
            for i, admin_id in enumerate(admins, 1):
                user = await self.db.get_user(admin_id)
                name = user['first_name'] if user else "Noma'lum"
                text += f"{i}. {name} - {admin_id}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qo'shish", callback_data="admin_add_admin")],
            [InlineKeyboardButton(text="➖ O'chirish", callback_data="admin_remove_admin")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _manage_force_join(self, callback: CallbackQuery):
        """Majburiy obunani boshqarish"""
        enabled = await self.db.is_force_join_enabled()
        channels = await self.db.get_channels()
        
        status = "✅ Yoqilgan" if enabled else "❌ O'chirilgan"
        text = f"⚙️ Majburiy obuna\n\nHolati: {status}\nKanallar: {len(channels)}"
        
        btn_text = "❌ O'chirish" if enabled else "✅ Yoqish"
        btn_data = "admin_force_join_off" if enabled else "admin_force_join_on"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data=btn_data)],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _add_channel_start(self, callback: CallbackQuery, state: FSMContext):
        """Kanal qo'shishni boshlash"""
        await state.set_state(AdminStates.waiting_for_channel_add)
        await callback.message.edit_text(
            "➕ Kanal qo'shish\n\n"
            "Kanal ID yoki @username yuboring:\n"
            "Misol: @kanal yoki -1001234567890"
        )
    
    async def _remove_channel_start(self, callback: CallbackQuery, state: FSMContext):
        """Kanal o'chirishni boshlash"""
        await state.set_state(AdminStates.waiting_for_channel_remove)
        await callback.message.edit_text(
            "➖ Kanal o'chirish\n\n"
            "O'chirmoqchi bo'lgan kanal ID sini yuboring:"
        )
    
    async def _add_admin_start(self, callback: CallbackQuery, state: FSMContext):
        """Admin qo'shishni boshlash"""
        await state.set_state(AdminStates.waiting_for_admin_add)
        await callback.message.edit_text(
            "➕ Admin qo'shish\n\n"
            "Admin qilmoqchi bo'lgan foydalanuvchi ID sini yuboring:\n"
            "Misol: 123456789"
        )
    
    async def _remove_admin_start(self, callback: CallbackQuery, state: FSMContext):
        """Admin o'chirishni boshlash"""
        await state.set_state(AdminStates.waiting_for_admin_remove)
        await callback.message.edit_text(
            "➖ Admin o'chirish\n\n"
            "O'chirmoqchi bo'lgan admin ID sini yuboring:"
        )


# ========== State Handlerlar ==========
# Inline xabar uchun vaqtinchalik ma'lumotlar
inline_data = {}

async def process_broadcast(message: Message, state: FSMContext, db: Database, bot: Bot):
    users = await db.get_all_users()
    sent = 0
    failed = 0
    
    status = await message.reply("📤 Yuborilmoqda...")
    
    for user in users:
        try:
            await bot.copy_message(
                chat_id=user['user_id'],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await status.delete()
    await message.reply(f"✅ Yuborildi: {sent}\n❌ Xatolik: {failed}")
    await state.clear()

async def process_forward(message: Message, state: FSMContext, db: Database, bot: Bot):
    users = await db.get_all_users()
    sent = 0
    failed = 0
    
    status = await message.reply("📤 Yuborilmoqda...")
    
    for user in users:
        try:
            await bot.forward_message(
                chat_id=user['user_id'],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await status.delete()
    await message.reply(f"✅ Yuborildi: {sent}\n❌ Xatolik: {failed}")
    await state.clear()

async def process_inline_text(message: Message, state: FSMContext, db: Database, bot: Bot):
    """Tugmali xabar 1-qadam: matnni saqlash"""
    # Matnni saqlash
    inline_data[message.from_user.id] = {'text': message.text}
    
    # 2-qadamga o'tish
    await state.set_state(AdminStates.waiting_for_inline_buttons)
    await message.reply(
        "🔘 Tugmali xabar yuborish (2/2)\n\n"
        "Tugmalarni yuboring:\n"
        "Format: Tugma1:link1, Tugma2:link2\n\n"
        "Misol: Kanal:https://t.me/kanal, Sayt:https://example.com"
    )

async def process_inline_buttons(message: Message, state: FSMContext, db: Database, bot: Bot):
    """Tugmali xabar 2-qadam: tugmalarni qo'shish va yuborish"""
    try:
        # Matnni olish
        user_id = message.from_user.id
        if user_id not in inline_data:
            await message.reply("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
            await state.clear()
            return
        
        text = inline_data[user_id]['text']
        buttons_text = message.text.strip()
        
        # Tugmalarni yaratish
        buttons = []
        for btn in buttons_text.split(','):
            if ':' in btn:
                name, url = btn.split(':', 1)
                buttons.append([InlineKeyboardButton(text=name.strip(), url=url.strip())])
        
        if not buttons:
            await message.reply("❌ Hech qanday tugma topilmadi!")
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Barcha foydalanuvchilarga yuborish
        users = await db.get_all_users()
        sent = 0
        failed = 0
        
        status = await message.reply("📤 Yuborilmoqda...")
        
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user['user_id'],
                    text=text.strip(),
                    reply_markup=keyboard
                )
                sent += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        
        await status.delete()
        await message.reply(f"✅ Yuborildi: {sent}\n❌ Xatolik: {failed}")
        
        # Vaqtinchalik ma'lumotni tozalash
        del inline_data[user_id]
        
    except Exception as e:
        await message.reply(f"❌ Xatolik: {str(e)}")
    
    await state.clear()

async def process_channel_add(message: Message, state: FSMContext, db: Database, bot: Bot):
    try:
        text = message.text.strip()
        
        if text.startswith('@'):
            chat = await bot.get_chat(text)
            channel_id = chat.id
            username = text
        else:
            channel_id = int(text)
            chat = await bot.get_chat(channel_id)
            username = chat.username if chat.username else None
        
        await db.add_channel(
            channel_id=channel_id,
            channel_username=username,
            channel_title=chat.title,
            added_by=message.from_user.id
        )
        
        await message.reply(f"✅ Kanal qo'shildi: {chat.title}")
        
    except Exception as e:
        await message.reply(f"❌ Xatolik: {str(e)}")
    
    await state.clear()

async def process_channel_remove(message: Message, state: FSMContext, db: Database):
    try:
        channel_id = int(message.text.strip())
        await db.remove_channel(channel_id)
        await message.reply(f"✅ Kanal o'chirildi")
    except:
        await message.reply("❌ Noto'g'ri ID")
    
    await state.clear()

async def process_admin_add(message: Message, state: FSMContext, db: Database):
    try:
        user_id = int(message.text.strip())
        await db.add_admin(user_id)
        
        # Foydalanuvchi ma'lumotini olish
        user = await db.get_user(user_id)
        name = user['first_name'] if user else "Noma'lum"
        
        await message.reply(f"✅ Admin qo'shildi: {name} ({user_id})")
    except Exception as e:
        await message.reply(f"❌ Xatolik: {str(e)}")
    
    await state.clear()

async def process_admin_remove(message: Message, state: FSMContext, db: Database):
    try:
        user_id = int(message.text.strip())
        await db.remove_admin(user_id)
        await message.reply(f"✅ Admin o'chirildi: {user_id}")
    except:
        await message.reply("❌ Noto'g'ri ID")
    
    await state.clear()


# Eksport
__all__ = ['AdminPanel', 'AdminStates', 'process_broadcast', 'process_forward', 
           'process_inline_text', 'process_inline_buttons', 'process_channel_add', 
           'process_channel_remove', 'process_admin_add', 'process_admin_remove']
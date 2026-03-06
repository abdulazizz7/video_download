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
    waiting_for_inline = State()
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
            is_admin = await self.db.is_admin(message.from_user.id)
            if not is_admin:
                await message.reply("❌ Bu buyruq faqat adminlar uchun!")
                return
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
                 InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
                [InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast"),
                 InlineKeyboardButton(text="📢 Forward xabar", callback_data="admin_forward")],
                [InlineKeyboardButton(text="🔘 Inline xabar", callback_data="admin_inline"),
                 InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels")],
                [InlineKeyboardButton(text="👤 Adminlar", callback_data="admin_admins"),
                 InlineKeyboardButton(text="⚙️ Majburiy obuna", callback_data="admin_force_join")],
                [InlineKeyboardButton(text="❌ Chiqish", callback_data="admin_exit")]
            ])
            
            await message.reply(
                "👑 Admin Panel\n\nKerakli bo'limni tanlang:",
                reply_markup=keyboard
            )
        
        @self.dp.callback_query(F.data.startswith("admin_"))
        async def admin_callback(callback: CallbackQuery, state: FSMContext):
            """Admin callback'larini boshqarish"""
            
            if callback.data == "admin_back":
                await self._show_main_menu(callback.message)
                await callback.answer()
                return
            
            is_admin = await self.db.is_admin(callback.from_user.id)
            if not is_admin:
                await callback.answer("Siz admin emassiz!", show_alert=True)
                return
            
            action = callback.data.replace("admin_", "")
            
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
        """Asosiy menyu"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
             InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast"),
             InlineKeyboardButton(text="📢 Forward xabar", callback_data="admin_forward")],
            [InlineKeyboardButton(text="🔘 Inline xabar", callback_data="admin_inline"),
             InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels")],
            [InlineKeyboardButton(text="👤 Adminlar", callback_data="admin_admins"),
             InlineKeyboardButton(text="⚙️ Majburiy obuna", callback_data="admin_force_join")],
            [InlineKeyboardButton(text="❌ Chiqish", callback_data="admin_exit")]
        ])
        await message.edit_text(
            "👑 Admin Panel\n\nKerakli bo'limni tanlang:",
            reply_markup=keyboard
        )
    
    async def _show_stats(self, callback: CallbackQuery):
        """Statistika"""
        total_users = await self.db.get_user_count()
        daily_active = await self.db.get_active_users('day')
        weekly_active = await self.db.get_active_users('week')
        monthly_active = await self.db.get_active_users('month')
        total_downloads = await self.db.get_total_downloads()
        
        text = (
            f"📊 Statistika\n\n"
            f"👥 Umumiy foydalanuvchilar: {total_users}\n"
            f"📅 Kunlik aktiv: {daily_active}\n"
            f"📆 Haftalik aktiv: {weekly_active}\n"
            f"📊 Oylik aktiv: {monthly_active}\n"
            f"📥 Yuklamalar: {total_downloads}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _show_users(self, callback: CallbackQuery):
        """Foydalanuvchilar"""
        users = await self.db.get_all_users()
        text = f"👥 Foydalanuvchilar ({len(users)})\n\n"
        
        for i, user in enumerate(users[:10], 1):
            username = f"@{user['username']}" if user['username'] else "No username"
            text += f"{i}. {user['first_name']} ({username})\n"
            text += f"   📥 {user['total_downloads']} ta video\n"
            text += f"   🕐 {user['joined_date'][:10] if user['joined_date'] else 'N/A'}\n\n"
        
        if len(users) > 10:
            text += f"... va yana {len(users) - 10} ta foydalanuvchi"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _start_broadcast(self, callback: CallbackQuery, state: FSMContext):
        await state.set_state(AdminStates.waiting_for_broadcast)
        await callback.message.edit_text(
            "📢 Oddiy xabar yuborish\n\nBarcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:\n(Bekor qilish uchun /cancel yozing)"
        )
    
    async def _start_forward(self, callback: CallbackQuery, state: FSMContext):
        await state.set_state(AdminStates.waiting_for_forward)
        await callback.message.edit_text(
            "📢 Forward xabar yuborish\n\nBarcha foydalanuvchilarga forward qilmoqchi bo'lgan xabaringizni yuboring:\n(Bekor qilish uchun /cancel yozing)"
        )
    
    async def _start_inline(self, callback: CallbackQuery, state: FSMContext):
        await state.set_state(AdminStates.waiting_for_inline)
        await callback.message.edit_text(
            "📢 Tugmali xabar yuborish\n\nXabarni yozing va tugmalarni quyidagi formatda qo'shing:\nMatn|Tugma1:link1,Tugma2:link2\n\nMisol:\nSalom|Kanal:https://t.me/kanal,Sayt:https://example.com\n\n(Bekor qilish uchun /cancel yozing)"
        )
    
    async def _manage_channels(self, callback: CallbackQuery):
        channels = await self.db.get_channels()
        
        text = "📢 Kanallar\n\n"
        if not channels:
            text += "Hozircha kanallar mavjud emas."
        else:
            for i, channel in enumerate(channels, 1):
                text += f"{i}. {channel['channel_title']}"
                if channel['channel_username']:
                    text += f" (@{channel['channel_username']})\n"
                else:
                    text += "\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Qo'shish", callback_data="admin_add_channel"),
                InlineKeyboardButton(text="➖ O'chirish", callback_data="admin_remove_channel")
            ],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _manage_admins(self, callback: CallbackQuery):
        admins = await self.db.get_admins()
        
        text = "👤 Adminlar\n\n"
        if not admins:
            text += "Hozircha adminlar mavjud emas."
        else:
            for i, admin_id in enumerate(admins, 1):
                user = await self.db.get_user(admin_id)
                if user:
                    username = f"@{user['username']}" if user['username'] else "No username"
                    text += f"{i}. {user['first_name']} ({username}) - {admin_id}\n"
                else:
                    text += f"{i}. {admin_id}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Qo'shish", callback_data="admin_add_admin"),
                InlineKeyboardButton(text="➖ O'chirish", callback_data="admin_remove_admin")
            ],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _manage_force_join(self, callback: CallbackQuery):
        enabled = await self.db.is_force_join_enabled()
        channels = await self.db.get_channels()
        
        text = (
            f"⚙️ Majburiy obuna sozlamalari\n\n"
            f"Holati: {'✅ Yoqilgan' if enabled else '❌ Ochirilgan'}\n"
            f"Kanallar soni: {len(channels)}\n\n"
        )
        
        if channels:
            text += "Kanallar:\n"
            for channel in channels:
                text += f"• {channel['channel_title']}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ O'chirish" if enabled else "✅ Yoqish",
                callback_data="admin_force_join_off" if enabled else "admin_force_join_on"
            )],
            [InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    async def _add_channel_start(self, callback: CallbackQuery, state: FSMContext):
        await state.set_state(AdminStates.waiting_for_channel_add)
        await callback.message.edit_text(
            "➕ Kanal qo'shish\n\nKanal ID sini yoki @username ni yuboring:\nMisol: @kanal_nomi yoki -1001234567890\n\n(Bekor qilish uchun /cancel yozing)"
        )
    
    async def _remove_channel_start(self, callback: CallbackQuery, state: FSMContext):
        channels = await self.db.get_channels()
        if not channels:
            await callback.answer("Kanallar mavjud emas!", show_alert=True)
            return
        
        await state.set_state(AdminStates.waiting_for_channel_remove)
        
        text = "➖ Kanal o'chirish\n\nO'chirmoqchi bo'lgan kanal ID sini yuboring:\n\n"
        for channel in channels:
            text += f"• {channel['channel_title']}: {channel['channel_id']}\n"
        
        text += "\n(Bekor qilish uchun /cancel yozing)"
        
        await callback.message.edit_text(text)
    
    async def _add_admin_start(self, callback: CallbackQuery, state: FSMContext):
        await state.set_state(AdminStates.waiting_for_admin_add)
        await callback.message.edit_text(
            "➕ Admin qo'shish\n\nAdmin qilmoqchi bo'lgan foydalanuvchining ID sini yuboring:\nMisol: 123456789\n\n(Bekor qilish uchun /cancel yozing)"
        )
    
    async def _remove_admin_start(self, callback: CallbackQuery, state: FSMContext):
        admins = await self.db.get_admins()
        if not admins:
            await callback.answer("Adminlar mavjud emas!", show_alert=True)
            return
        
        await state.set_state(AdminStates.waiting_for_admin_remove)
        
        text = "➖ Admin o'chirish\n\nO'chirmoqchi bo'lgan admin ID sini yuboring:\n\n"
        for admin_id in admins:
            user = await self.db.get_user(admin_id)
            if user:
                text += f"• {user['first_name']}: {admin_id}\n"
            else:
                text += f"• {admin_id}\n"
        
        text += "\n(Bekor qilish uchun /cancel yozing)"
        
        await callback.message.edit_text(text)


# ========== State Handlerlar ==========
async def process_broadcast(message: Message, state: FSMContext, db: Database, bot: Bot):
    if message.text == '/cancel':
        await state.clear()
        await message.reply("❌ Xabar yuborish bekor qilindi")
        return
    
    users = await db.get_all_users()
    sent = 0
    failed = 0
    
    status_msg = await message.reply("📤 Xabar yuborilmoqda...")
    
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
    
    await status_msg.delete()
    await message.reply(f"✅ Xabar yuborildi!\n\nYuborildi: {sent}\nXatolik: {failed}")
    await state.clear()

async def process_forward(message: Message, state: FSMContext, db: Database, bot: Bot):
    if message.text == '/cancel':
        await state.clear()
        await message.reply("❌ Xabar yuborish bekor qilindi")
        return
    
    users = await db.get_all_users()
    sent = 0
    failed = 0
    
    status_msg = await message.reply("📤 Xabar yuborilmoqda...")
    
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
    
    await status_msg.delete()
    await message.reply(f"✅ Xabar yuborildi!\n\nYuborildi: {sent}\nXatolik: {failed}")
    await state.clear()

async def process_inline(message: Message, state: FSMContext, db: Database, bot: Bot):
    if message.text == '/cancel':
        await state.clear()
        await message.reply("❌ Xabar yuborish bekor qilindi")
        return
    
    try:
        if '|' not in message.text:
            raise ValueError("Noto'g'ri format")
        
        text_part, buttons_part = message.text.split('|', 1)
        buttons = []
        
        for btn in buttons_part.split(','):
            if ':' not in btn:
                continue
            btn_name, btn_url = btn.split(':', 1)
            buttons.append([InlineKeyboardButton(text=btn_name.strip(), url=btn_url.strip())])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        
        users = await db.get_all_users()
        sent = 0
        failed = 0
        
        status_msg = await message.reply("📤 Xabar yuborilmoqda...")
        
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user['user_id'],
                    text=text_part.strip(),
                    reply_markup=keyboard
                )
                sent += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        
        await status_msg.delete()
        await message.reply(f"✅ Xabar yuborildi!\n\nYuborildi: {sent}\nXatolik: {failed}")
        
    except Exception as e:
        await message.reply(f"❌ Xatolik: {str(e)}")
    
    await state.clear()

async def process_channel_add(message: Message, state: FSMContext, db: Database, bot: Bot):
    if message.text == '/cancel':
        await state.clear()
        await message.reply("❌ Kanal qo'shish bekor qilindi")
        return
    
    try:
        channel_input = message.text.strip()
        channel_id = None
        channel_username = None
        
        if channel_input.startswith('@'):
            channel_username = channel_input
            chat = await bot.get_chat(channel_username)
            channel_id = chat.id
        else:
            channel_id = int(channel_input)
            chat = await bot.get_chat(channel_id)
            channel_username = chat.username if chat.username else None
        
        await db.add_channel(
            channel_id=channel_id,
            channel_username=channel_username,
            channel_title=chat.title,
            added_by=message.from_user.id
        )
        
        await message.reply(f"✅ Kanal qo'shildi: {chat.title}")
        
    except Exception as e:
        await message.reply(f"❌ Xatolik: {str(e)}")
    
    await state.clear()

async def process_channel_remove(message: Message, state: FSMContext, db: Database):
    if message.text == '/cancel':
        await state.clear()
        await message.reply("❌ Kanal o'chirish bekor qilindi")
        return
    
    try:
        channel_id = int(message.text.strip())
        await db.remove_channel(channel_id)
        await message.reply(f"✅ Kanal o'chirildi: {channel_id}")
    except:
        await message.reply("❌ Noto'g'ri ID")
    
    await state.clear()

async def process_admin_add(message: Message, state: FSMContext, db: Database):
    if message.text == '/cancel':
        await state.clear()
        await message.reply("❌ Admin qo'shish bekor qilindi")
        return
    
    try:
        user_id = int(message.text.strip())
        await db.add_admin(user_id)
        await message.reply(f"✅ Admin qo'shildi: {user_id}")
    except:
        await message.reply("❌ Noto'g'ri ID")
    
    await state.clear()

async def process_admin_remove(message: Message, state: FSMContext, db: Database):
    if message.text == '/cancel':
        await state.clear()
        await message.reply("❌ Admin o'chirish bekor qilindi")
        return
    
    try:
        user_id = int(message.text.strip())
        await db.remove_admin(user_id)
        await message.reply(f"✅ Admin o'chirildi: {user_id}")
    except:
        await message.reply("❌ Noto'g'ri ID")
    
    await state.clear()


# Eksport
__all__ = ['AdminPanel', 'AdminStates', 'process_broadcast', 'process_forward', 
           'process_inline', 'process_channel_add', 'process_channel_remove', 
           'process_admin_add', 'process_admin_remove']
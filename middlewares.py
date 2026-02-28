from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from config import BOT_TOKEN
import re

class ForceJoinMiddleware(BaseMiddleware):
    """Majburiy obuna middleware"""
    
    def __init__(self, db: Database, bot):
        self.db = db
        self.bot = bot
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Har bir xabarni tekshirish"""
        if not event.from_user:
            return await handler(event, data)
        
        # Adminlarni tekshirmaslik
        if await self.db.is_admin(event.from_user.id):
            return await handler(event, data)
        
        # Majburiy obuna yoqilganmi?
        if not await self.db.is_force_join_enabled():
            return await handler(event, data)
        
        # Kanallarni olish
        channels = await self.db.get_channels()
        if not channels:
            return await handler(event, data)
        
        # Faqat linklarni tekshirish (start va help dan tashqari)
        if event.text and not re.search(r'https?://', event.text):
            return await handler(event, data)
        
        not_joined = []
        for channel in channels:
            try:
                member = await self.bot.get_chat_member(
                    chat_id=channel['channel_id'],
                    user_id=event.from_user.id
                )
                
                if member.status in ['left', 'kicked']:
                    not_joined.append(channel)
            except Exception as e:
                print(f"Kanal tekshirishda xatolik: {e}")
                not_joined.append(channel)
        
        if not_joined:
            # Kanallar ro'yxatini chiqarish
            text = "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
            
            keyboard = []
            for channel in not_joined:
                if channel['channel_username']:
                    # Kanalga obuna bo'lish tugmasi
                    btn = InlineKeyboardButton(
                        text=f"📢 {channel['channel_title']}", 
                        url=f"https://t.me/{channel['channel_username'].replace('@', '')}"
                    )
                    keyboard.append([btn])
            
            # Tasdiqlash tugmasi
            keyboard.append([InlineKeyboardButton(
                text="✅ Obuna bo'ldim", 
                callback_data="check_subscription"
            )])
            
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await event.reply(text, reply_markup=reply_markup)
            return  # Handlerga o'tkazmaslik
        
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, db: Database, limit: int, window: int):
        self.db = db
        self.limit = limit
        self.window = window
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Rate limitni tekshirish"""
        if not event.from_user or not event.text:
            return await handler(event, data)
        
        # Faqat linklarni tekshirish
        if not re.search(r'https?://', event.text):
            return await handler(event, data)
        
        # Adminlarni tekshirmaslik
        if await self.db.is_admin(event.from_user.id):
            return await handler(event, data)
        
        is_limited = await self.db.check_rate_limit(
            event.from_user.id,
            self.limit,
            self.window
        )
        
        if is_limited:
            await event.reply(
                "⚠️ Juda ko'p so'rov yubordingiz. "
                f"Iltimos, {self.window // 60} daqiqa kuting."
            )
            return  # Handlerga o'tkazmaslik
        
        return await handler(event, data)
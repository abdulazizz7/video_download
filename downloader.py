import asyncio
import os
import tempfile
import uuid
import re
import logging
from typing import Optional, Tuple
import yt_dlp
from aiogram import Bot
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)

class VideoDownloader:
    def __init__(self, bot: Bot, secret_group_id: int):
        self.bot = bot
        self.secret_group_id = secret_group_id
        self.downloading = set()
        self.download_lock = asyncio.Lock()
        
    async def download_instagram_video(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Faqat Instagram videoni yuklab olish va kesh uchun guruhga yuborish"""
        
        if url in self.downloading:
            logger.info(f"Video allaqachon yuklanmoqda: {url}")
            for i in range(30):
                await asyncio.sleep(1)
                if url not in self.downloading:
                    break
        
        async with self.download_lock:
            try:
                self.downloading.add(url)
                logger.info(f"Instagram video yuklanmoqda: {url}")
                
                # Vaqtinchalik fayl (D diskiga)
                temp_dir = "D:/temp"
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                temp_filename = f"{temp_dir}/{uuid.uuid4()}.mp4"
                
                # Cookies fayli borligini tekshirish
                cookies_file = "cookies.txt"
                if os.path.exists(cookies_file):
                    logger.info("✅ Cookies fayli topildi")
                else:
                    logger.warning("❌ Cookies fayli topilmadi!")
                
                # Instagram uchun maxsus sozlamalar
                ydl_opts = {
                    'format': 'best[height<=1080][ext=mp4]/best',
                    'outtmpl': temp_filename,
                    'quiet': True,
                    'no_warnings': True,
                    'cookiefile': cookies_file if os.path.exists(cookies_file) else None,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    },
                }
                
                loop = asyncio.get_event_loop()
                
                def download():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        try:
                            info = ydl.extract_info(url, download=True)
                            return info
                        except Exception as e:
                            raise e
                
                try:
                    video_info = await loop.run_in_executor(None, download)
                    logger.info(f"✅ Video muvaffaqiyatli yuklandi: {url}")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ Yuklab olishda xatolik: {error_msg}")
                    
                    if "Unsupported URL" in error_msg:
                        return None, "❌ Noto'g'ri Instagram linki"
                    elif "Video unavailable" in error_msg:
                        return None, "❌ Video mavjud emas yoki o'chirilgan"
                    elif "Private" in error_msg:
                        return None, "❌ Video shaxsiy (private) profilda"
                    elif "login" in error_msg.lower() or "cookies" in error_msg.lower():
                        return None, "❌ Instagram login talab qiladi. Iltimos, cookies.txt faylini tekshiring."
                    else:
                        return None, f"❌ Yuklab olishda xatolik: {error_msg[:100]}"
                
                if not os.path.exists(temp_filename):
                    return None, "❌ Video fayli topilmadi"
                
                # Fayl hajmini tekshirish (50MB limit)
                file_size = os.path.getsize(temp_filename)
                logger.info(f"📊 Video hajmi: {file_size} bayt ({file_size/1024/1024:.2f} MB)")
                
                if file_size > 50 * 1024 * 1024:
                    os.remove(temp_filename)
                    return None, "❌ Video hajmi 50MB dan katta"
                
                # --- KESH TIZIMI UCHUN MUHIM QISM ---
                try:
                    # Videoni maxfiy guruhga yuborish (kesh uchun)
                    logger.info(f"📤 Videoni maxfiy guruhga yuborish: {self.secret_group_id}")
                    video_file = FSInputFile(temp_filename)
                    group_message = await self.bot.send_video(
                        chat_id=self.secret_group_id,
                        video=video_file,
                        caption=f"#instagram\n{url}",
                        supports_streaming=True
                    )
                    
                    group_message_id = group_message.message_id
                    file_id = group_message.video.file_id
                    
                    logger.info(f"✅ Video maxfiy guruhga yuborildi. Message ID: {group_message_id}, File ID: {file_id}")
                    
                    # Vaqtinchalik faylni o'chirish
                    os.remove(temp_filename)
                    
                    # File ID ni qaytarish (foydalanuvchiga yuborish uchun)
                    return file_id, None
                    
                except Exception as e:
                    logger.error(f"❌ Guruhga yuborishda xatolik: {e}")
                    # Agar guruhga yuborib bo'lmasa, to'g'ridan-to'g'ri fayldan yuborish
                    logger.info("📤 To'g'ridan-to'g'ri fayldan yuborish")
                    return temp_filename, None  # Fayl nomini qaytar
                
            except Exception as e:
                logger.error(f"❌ Instagram video yuklashda xatolik: {e}")
                return None, f"❌ Xatolik: {str(e)[:100]}"
            finally:
                if url in self.downloading:
                    self.downloading.remove(url)
    
    async def get_video_from_group(self, group_message_id: int) -> Optional[str]:
        """Guruhdan video olish (keshdan olish uchun)"""
        try:
            logger.info(f"🔄 Guruhdan video olish: Message ID {group_message_id}")
            message = await self.bot.forward_message(
                chat_id=self.secret_group_id,
                from_chat_id=self.secret_group_id,
                message_id=group_message_id
            )
            if message.video:
                logger.info(f"✅ Guruhdan video olindi: {message.video.file_id}")
                return message.video.file_id
            else:
                logger.warning("❌ Guruhda video topilmadi")
                return None
        except Exception as e:
            logger.error(f"❌ Guruhdan video olishda xatolik: {e}")
            return None
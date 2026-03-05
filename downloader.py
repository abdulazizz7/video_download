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
        """Faqat Instagram videoni yuklab olish"""
        
        if url in self.downloading:
            for i in range(30):
                await asyncio.sleep(1)
                if url not in self.downloading:
                    break
        
        async with self.download_lock:
            try:
                self.downloading.add(url)
                
                # Vaqtinchalik fayl
                temp_filename = f"{tempfile.gettempdir()}/{uuid.uuid4()}.mp4"
                
                # Instagram uchun maxsus sozlamalar
                ydl_opts = {
                    'format': 'best[height<=1080][ext=mp4]/best',
                    'outtmpl': temp_filename,
                    'quiet': True,
                    'no_warnings': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
                except Exception as e:
                    error_msg = str(e)
                    if "Unsupported URL" in error_msg:
                        return None, "❌ Noto'g'ri Instagram linki"
                    elif "Video unavailable" in error_msg:
                        return None, "❌ Video mavjud emas yoki o'chirilgan"
                    else:
                        return None, f"❌ Yuklab olishda xatolik: {error_msg[:100]}"
                
                if not os.path.exists(temp_filename):
                    return None, "❌ Video fayli topilmadi"
                
                # Fayl hajmini tekshirish (50MB limit)
                file_size = os.path.getsize(temp_filename)
                if file_size > 50 * 1024 * 1024:
                    os.remove(temp_filename)
                    return None, "❌ Video hajmi 50MB dan katta"
                
                # Videoni maxfiy guruhga yuborish
                video_file = FSInputFile(temp_filename)
                message = await self.bot.send_video(
                    chat_id=self.secret_group_id,
                    video=video_file,
                    caption=f"#instagram\n{url}",
                    supports_streaming=True
                )
                
                os.remove(temp_filename)
                file_id = message.video.file_id
                
                return file_id, None
                
            except Exception as e:
                logger.error(f"Instagram video yuklashda xatolik: {e}")
                return None, f"❌ Xatolik: {str(e)[:100]}"
            finally:
                self.downloading.remove(url)
    
    async def get_video_from_group(self, group_message_id: int) -> Optional[str]:
        """Guruhdan video olish"""
        try:
            message = await self.bot.forward_message(
                chat_id=self.secret_group_id,
                from_chat_id=self.secret_group_id,
                message_id=group_message_id
            )
            return message.video.file_id if message.video else None
        except:
            return None
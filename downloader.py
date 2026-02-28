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

# Logging
logger = logging.getLogger(__name__)

class VideoDownloader:
    def __init__(self, bot: Bot, secret_group_id: int):
        self.bot = bot
        self.secret_group_id = secret_group_id
        self.downloading = set()
        self.download_lock = asyncio.Lock()
        self.cache = {}  # Tez kesh xotira
        
    async def download_video(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Videoni tez yuklab olish"""
        
        # 1. Tez keshni tekshirish
        if url in self.cache:
            logger.info(f"Keshdan olindi: {url}")
            return self.cache[url], None
        
        # 2. Yuklanayotgan videolarni tekshirish
        if url in self.downloading:
            for i in range(10):  # 10 soniya kutish (kamaytirildi)
                await asyncio.sleep(0.5)
                if url not in self.downloading:
                    break
        
        async with self.download_lock:
            try:
                self.downloading.add(url)
                
                # Platformani aniqlash
                platform = self._detect_platform(url)
                if not platform:
                    return None, "Noto'g'ri platforma"
                
                # Vaqtinchalik fayl
                temp_filename = f"{tempfile.gettempdir()}/{uuid.uuid4()}.mp4"
                
                # TEZ yuklab olish sozlamalari
                ydl_opts = {
                    'format': 'best[ext=mp4]',  # Eng tez format
                    'outtmpl': temp_filename,
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    },
                    # TEZLIKNI OSHIRISH UCHUN:
                    'buffersize': 1024 * 1024,  # 1MB buffer
                    'fragment_retries': 3,
                    'retries': 3,
                    'file_access_retries': 3,
                    'extractor_retries': 3,
                    'throttledratelimit': 1024 * 1024,  # 1MB/s dan past bo'lsa qayta urin
                    'sleep_interval': 0,  # Kutish YO'Q
                    'max_sleep_interval': 0,
                    'sleep_interval_requests': 0,
                }
                
                # Platformaga qarab optimallashtirish
                if platform == 'tiktok':
                    ydl_opts['format'] = 'best[ext=mp4]/best'
                    ydl_opts['extractor_args'] = {'tiktok': {'watermark': False}}
                    ydl_opts['socket_timeout'] = 10  # 10 soniya timeout
                
                # TEZ yuklab olish
                loop = asyncio.get_event_loop()
                
                def download():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=True)
                
                # Yuklab olish
                video_info = await loop.run_in_executor(None, download)
                
                # Faylni tekshirish
                if not os.path.exists(temp_filename):
                    return None, "Video topilmadi"
                
                # TEZ yuborish
                video_file = FSInputFile(temp_filename)
                message = await self.bot.send_video(
                    chat_id=self.secret_group_id,
                    video=video_file,
                    caption=f"#{platform}",
                    supports_streaming=True,
                    protect_content=False  # Tezroq yuborish uchun
                )
                
                # Faylni o'chirish
                os.remove(temp_filename)
                
                file_id = message.video.file_id
                
                # Keshga saqlash
                self.cache[url] = file_id
                
                # 1 soatdan keyin keshdan o'chirish
                asyncio.create_task(self._clear_cache_after(url, 3600))
                
                return file_id, None
                
            except Exception as e:
                logger.error(f"Xatolik: {e}")
                return None, f"Xatolik: {str(e)[:100]}"
            finally:
                self.downloading.remove(url)
    
    async def _clear_cache_after(self, url: str, seconds: int):
        """Keshni tozalash"""
        await asyncio.sleep(seconds)
        if url in self.cache:
            del self.cache[url]
    
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
    
    def _detect_platform(self, url: str) -> Optional[str]:
        """Platformani aniqlash"""
        url = url.lower()
        
        if re.search(r'instagram\.com/(p|reel|tv)|instagr\.am', url):
            return 'instagram'
        elif re.search(r'tiktok\.com|vm\.tiktok\.com|musical\.ly', url):
            return 'tiktok'
        
        return None
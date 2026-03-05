import asyncio
import os
import tempfile
import uuid
import logging
from typing import Optional, Tuple, Dict
import yt_dlp
from datetime import datetime

logger = logging.getLogger(__name__)

class MusicDownloader:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.downloading = set()
        self.cache = {}
        
    async def search_and_download(self, query: str, user_id: int) -> Tuple[Optional[bytes], Optional[str], Optional[Dict]]:
        """To'g'ridan-to'g'ri yt-dlp bilan qidirish va yuklash"""
        
        cache_key = f"music:{query.lower().strip()}"
        if cache_key in self.cache:
            logger.info(f"Keshdan olindi: {query}")
            cached = self.cache[cache_key]
            return cached['data'], None, cached['info']
        
        async with asyncio.Lock():
            try:
                self.downloading.add(query)
                logger.info(f"Musiqa yuklash boshlandi: {query}")
                
                # Vaqtinchalik fayl
                temp_dir = tempfile.gettempdir()
                random_name = str(uuid.uuid4())
                temp_file = os.path.join(temp_dir, f"{random_name}.%(ext)s")
                
                # yt-dlp sozlamalari
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': temp_file,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'ffmpeg_location': 'C:\\ffmpeg',
                    'default_search': 'ytsearch1',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                loop = asyncio.get_event_loop()
                
                def download():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        # To'g'ridan-to'g'ri qidirish
                        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                        
                        if info and 'entries' in info and len(info['entries']) > 0:
                            first = info['entries'][0]
                            duration = first.get('duration', 0)
                            minutes = duration // 60
                            seconds = duration % 60
                            
                            return {
                                'title': first.get('title', query),
                                'duration': f"{minutes}:{seconds:02d}",
                                'duration_seconds': duration,
                                'link': first.get('webpage_url', '')
                            }
                        return None
                
                song_info = await loop.run_in_executor(None, download)
                
                if not song_info:
                    return None, "❌ Qo'shiq topilmadi", None
                
                # MP3 faylni topish
                mp3_file = os.path.join(temp_dir, f"{random_name}.mp3")
                
                if not os.path.exists(mp3_file):
                    # Agar boshqa nom bo'lsa
                    import glob
                    mp3_files = glob.glob(os.path.join(temp_dir, f"{random_name}*.mp3"))
                    if mp3_files:
                        mp3_file = mp3_files[0]
                    else:
                        return None, "❌ Musiqa fayli topilmadi", None
                
                # Faylni o'qish
                with open(mp3_file, 'rb') as f:
                    audio_data = f.read()
                
                # Faylni o'chirish
                try:
                    os.remove(mp3_file)
                except:
                    pass
                
                # Keshga saqlash
                self.cache[cache_key] = {
                    'data': audio_data,
                    'info': song_info,
                    'time': datetime.now()
                }
                asyncio.create_task(self._clear_cache(cache_key, 3600))
                
                return audio_data, None, song_info
                
            except Exception as e:
                logger.error(f"Xatolik: {e}")
                return None, f"❌ Xatolik: {str(e)}", None
            finally:
                self.downloading.remove(query)
    
    async def _clear_cache(self, key: str, seconds: int):
        await asyncio.sleep(seconds)
        if key in self.cache:
            del self.cache[key]
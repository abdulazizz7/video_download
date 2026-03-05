import asyncio
from downloader import VideoDownloader
from aiogram import Bot
from config import BOT_TOKEN, SECRET_GROUP_ID

async def test_download():
    bot = Bot(token=BOT_TOKEN)
    downloader = VideoDownloader(bot, SECRET_GROUP_ID)
    
    url = "https://www.instagram.com/reel/DVbl3hOjBF2/"
    
    print(f"Yuklanmoqda: {url}")
    file_id, error = await downloader.download_instagram_video(url)
    
    if error:
        print(f"❌ Xatolik: {error}")
    else:
        print(f"✅ Video yuklandi! File ID: {file_id}")

asyncio.run(test_download())
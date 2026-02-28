import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import aiosqlite
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_db(self):
        """Ma'lumotlar bazasini yaratish"""
        async with aiosqlite.connect(self.db_path) as db:
            # Foydalanuvchilar
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    joined_date TIMESTAMP,
                    last_activity TIMESTAMP,
                    is_admin BOOLEAN DEFAULT 0,
                    is_banned BOOLEAN DEFAULT 0,
                    total_downloads INTEGER DEFAULT 0
                )
            ''')
            
            # Videolar (keshlangan)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_url TEXT UNIQUE,
                    platform TEXT,
                    video_id TEXT,
                    file_id TEXT,
                    group_message_id INTEGER,
                    downloaded_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                )
            ''')
            
            # Yuklashlar tarixi
            await db.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    video_url TEXT,
                    platform TEXT,
                    downloaded_at TIMESTAMP,
                    from_cache BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Kanallar (majburiy obuna)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    channel_username TEXT,
                    channel_title TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP
                )
            ''')
            
            # Sozlamalar
            await db.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Rate limiting
            await db.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER,
                    request_time TIMESTAMP,
                    PRIMARY KEY (user_id, request_time)
                )
            ''')
            
            await db.commit()
            logger.info("Ma'lumotlar bazasi muvaffaqiyatli yaratildi")
    
    # ========== USER METHODS ==========
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Yangi foydalanuvchi qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, joined_date, last_activity)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, 
                  datetime.now(), datetime.now()))
            await db.commit()
    
    async def update_activity(self, user_id: int):
        """Foydalanuvchi aktivligini yangilash"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users SET last_activity = ? WHERE user_id = ?
            ''', (datetime.now(), user_id))
            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Foydalanuvchi ma'lumotlarini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Barcha foydalanuvchilarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM users ORDER BY joined_date DESC')
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_user_count(self) -> int:
        """Foydalanuvchilar soni"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT COUNT(*) FROM users')
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def get_active_users(self, period: str = 'day') -> int:
        """Aktiv foydalanuvchilar soni"""
        now = datetime.now()
        if period == 'day':
            start_time = now - timedelta(days=1)
        elif period == 'week':
            start_time = now - timedelta(weeks=1)
        elif period == 'month':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT COUNT(DISTINCT user_id) FROM downloads WHERE downloaded_at > ?',
                (start_time,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    # ========== ADMIN METHODS ==========
    async def add_admin(self, user_id: int):
        """Admin qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (user_id,))
            await db.commit()
    
    async def remove_admin(self, user_id: int):
        """Adminni o'chirish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET is_admin = 0 WHERE user_id = ?', (user_id,))
            await db.commit()
    
    async def get_admins(self) -> List[int]:
        """Adminlar ro'yxati"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT user_id FROM users WHERE is_admin = 1')
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def is_admin(self, user_id: int) -> bool:
        """Foydalanuvchi adminligini tekshirish"""
        user = await self.get_user(user_id)
        return user and user.get('is_admin', False)
    
    # ========== VIDEO METHODS ==========
    async def add_video(self, video_url: str, platform: str, video_id: str, 
                        file_id: str, group_message_id: int):
        """Videoni ma'lumotlar bazasiga qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO videos 
                (video_url, platform, video_id, file_id, group_message_id, downloaded_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (video_url, platform, video_id, file_id, group_message_id, datetime.now(), 0))
            await db.commit()
    
    async def get_video(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Videoni URL orqali qidirish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM videos WHERE video_url = ?', 
                (video_url,)
            )
            row = await cursor.fetchone()
            
            if row:
                # Kirishlar sonini oshirish
                await db.execute(
                    'UPDATE videos SET access_count = access_count + 1 WHERE video_url = ?',
                    (video_url,)
                )
                await db.commit()
                return dict(row)
            return None
    
    async def get_video_by_message_id(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Videoni guruh xabari ID si orqali qidirish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM videos WHERE group_message_id = ?', 
                (message_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_total_downloads(self) -> int:
        """Umumiy yuklamalar soni"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT COUNT(*) FROM downloads')
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    # ========== DOWNLOAD HISTORY ==========
    async def add_download(self, user_id: int, video_url: str, platform: str, from_cache: bool = False):
        """Yuklash tarixiga qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO downloads (user_id, video_url, platform, downloaded_at, from_cache)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, video_url, platform, datetime.now(), from_cache))
            
            # User total_downloads ni oshirish
            await db.execute('''
                UPDATE users SET total_downloads = total_downloads + 1 WHERE user_id = ?
            ''', (user_id,))
            
            await db.commit()
    
    # ========== CHANNEL METHODS ==========
    async def add_channel(self, channel_id: int, channel_username: str, channel_title: str, added_by: int):
        """Kanal qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO channels (channel_id, channel_username, channel_title, added_by, added_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (channel_id, channel_username, channel_title, added_by, datetime.now()))
            await db.commit()
    
    async def remove_channel(self, channel_id: int):
        """Kanal o'chirish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
            await db.commit()
    
    async def get_channels(self) -> List[Dict[str, Any]]:
        """Kanallar ro'yxati"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM channels ORDER BY added_at DESC')
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ========== SETTINGS ==========
    async def get_setting(self, key: str, default=None):
        """Sozlamani olish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = await cursor.fetchone()
            return row[0] if row else default
    
    async def set_setting(self, key: str, value: str):
        """Sozlamani o'rnatish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (key, value))
            await db.commit()
    
    async def is_force_join_enabled(self) -> bool:
        """Majburiy obuna yoqilganmi?"""
        value = await self.get_setting('force_join_enabled', 'false')
        return value.lower() == 'true'
    
    async def set_force_join(self, enabled: bool):
        """Majburiy obuna holatini o'rnatish"""
        await self.set_setting('force_join_enabled', str(enabled))
    
    # ========== RATE LIMITING ==========
    async def check_rate_limit(self, user_id: int, limit: int, window: int) -> bool:
        """Rate limitni tekshirish (True = limitdan oshgan)"""
        cutoff = datetime.now() - timedelta(seconds=window)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Eski yozuvlarni tozalash
            await db.execute(
                'DELETE FROM rate_limits WHERE request_time < ?',
                (cutoff,)
            )
            
            # Joriy so'rovlar sonini hisoblash
            cursor = await db.execute(
                'SELECT COUNT(*) FROM rate_limits WHERE user_id = ? AND request_time > ?',
                (user_id, cutoff)
            )
            row = await cursor.fetchone()
            
            if row and row[0] >= limit:
                return True  # Limitdan oshgan
            
            # Yangi so'rovni qo'shish
            await db.execute(
                'INSERT INTO rate_limits (user_id, request_time) VALUES (?, ?)',
                (user_id, datetime.now())
            )
            await db.commit()
            return False  # Limitdan oshmagan
    
    # ========== STATISTICS METHODS ==========
    async def get_downloads_by_platform(self) -> Dict[str, int]:
        """Platformalar bo'yicha yuklamalar statistikasi"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT platform, COUNT(*) FROM downloads GROUP BY platform'
            )
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows if row[0]}
    
    async def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Eng ko'p yuklagan foydalanuvchilar"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT user_id, username, first_name, total_downloads 
                FROM users 
                WHERE total_downloads > 0 
                ORDER BY total_downloads DESC 
                LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Kunlik statistika"""
        start_date = datetime.now() - timedelta(days=days)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT DATE(downloaded_at) as date, COUNT(*) as count,
                       SUM(CASE WHEN from_cache = 1 THEN 1 ELSE 0 END) as cached,
                       SUM(CASE WHEN from_cache = 0 THEN 1 ELSE 0 END) as new
                FROM downloads 
                WHERE downloaded_at > ?
                GROUP BY DATE(downloaded_at)
                ORDER BY date DESC
            ''', (start_date,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
import sqlite3
import hashlib
import os
from datetime import datetime

# Use absolute path to ensure data consistency
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "analysis_results.db")

class DBHandler:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY,
                    video_id TEXT,
                    author_name TEXT,
                    author_hash TEXT,
                    content TEXT,
                    published_at TEXT,
                    like_count INTEGER,
                    reply_count INTEGER,
                    is_reply BOOLEAN,
                    parent_id TEXT,
                    sentiment TEXT,
                    sentiment_score REAL,
                    toxicity_score REAL,
                    intent TEXT,
                    aisas_stage TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS insights (
                    video_id TEXT PRIMARY KEY,
                    summary TEXT,
                    ai_score INTEGER,
                    status TEXT,
                    last_updated TEXT
                )
            """)
            conn.commit()

    def clear_video_data(self, video_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM comments WHERE video_id = ?", (video_id,))
            cursor.execute("DELETE FROM insights WHERE video_id = ?", (video_id,))
            conn.commit()

    def save_comments(self, video_id, comments_df):
        if comments_df.empty: return
        data = []
        for i, row in comments_df.iterrows():
            author_name = row.get('author_handle', 'anonymous')
            author_hash = hashlib.sha256(str(author_name).encode()).hexdigest()
            row_id = f"{video_id}_{i}_{datetime.now().timestamp()}"
            data.append((
                row_id, video_id, author_name, author_hash,
                row.get('content', ''), row.get('published_at', ''),
                row.get('like_count', 0), row.get('reply_count', 0),
                bool(row.get('is_reply', False)), str(row.get('parent_id', ''))
            ))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO comments (
                    id, video_id, author_name, author_hash, content, published_at, 
                    like_count, reply_count, is_reply, parent_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            conn.commit()

    def update_analysis(self, video_id, comment_id, res):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE comments SET sentiment=?, sentiment_score=?, intent=?, aisas_stage=?
                WHERE id=?
            """, (res.get('sentiment'), res.get('sentiment_score'), res.get('intent'), res.get('aisas_stage'), comment_id))
            conn.commit()

    def save_advanced_stats(self, video_id, stats):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch existing to avoid overwriting summary if we only update status
            cursor.execute("SELECT summary, ai_score, status FROM insights WHERE video_id=?", (video_id,))
            existing = cursor.fetchone()
            
            summary = stats.get('insight') or (existing[0] if existing else "AI 요약 대기 중...")
            ai_score = stats.get('ai_score') or (existing[1] if existing else 0)
            status = stats.get('status') or (existing[2] if existing else "idle")

            cursor.execute("""
                INSERT OR REPLACE INTO insights (video_id, summary, ai_score, status, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """, (video_id, summary, ai_score, status, datetime.now().isoformat()))
            conn.commit()

    def get_advanced_stats(self, video_id):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Real Sentiment Distribution (Fixing the 0% issue)
            cursor.execute("SELECT sentiment, COUNT(*) as count FROM comments WHERE video_id=? AND sentiment IS NOT NULL GROUP BY sentiment", (video_id,))
            senti_rows = cursor.fetchall()
            sentiment_distribution = {"positive": 0, "neutral": 0, "negative": 0}
            for r in senti_rows:
                s = r['sentiment'].lower()
                if 'pos' in s: sentiment_distribution['positive'] += r['count']
                elif 'neg' in s: sentiment_distribution['negative'] += r['count']
                else: sentiment_distribution['neutral'] += r['count']

            # 2. Temporal Analysis (By Hour & Stacked)
            cursor.execute("""
                SELECT strftime('%H', published_at) as hour, is_reply, COUNT(*) as count 
                FROM comments WHERE video_id=? GROUP BY hour, is_reply
            """, (video_id,))
            temporal = {"comments": [0]*24, "replies": [0]*24}
            for r in cursor.fetchall():
                if r['hour'] and r['hour'].isdigit():
                    h = int(r['hour'])
                    if r['is_reply']: temporal["replies"][h] = r['count']
                    else: temporal["comments"][h] = r['count']

            # 3. Temporal Analysis (By Day) - Mon=0, Sun=6
            cursor.execute("""
                SELECT strftime('%w', published_at) as day, COUNT(*) as count 
                FROM comments WHERE video_id=? GROUP BY day
            """, (video_id,))
            temporal_day = [0] * 7
            for r in cursor.fetchall():
                if r['day']: temporal_day[int(r['day'])] = r['count']

            # 4. Top Liked Comments (NOT USERS)
            cursor.execute("""
                SELECT author_name, content, like_count, is_reply
                FROM comments WHERE video_id=? ORDER BY like_count DESC LIMIT 10
            """, (video_id,))
            top_comments = [dict(row) for row in cursor.fetchall()]

            # 5. Network Map for D3 visualization
            cursor.execute("SELECT id, author_name, parent_id, content FROM comments WHERE video_id=?", (video_id,))
            all_nodes = {r['id']: r['author_name'] for r in cursor.fetchall()}
            cursor.execute("SELECT id, parent_id FROM comments WHERE video_id=? AND is_reply=1", (video_id,))
            edges = [{"source": r['parent_id'], "target": r['id']} for r in cursor.fetchall() if r['parent_id'] in all_nodes]
            network_map = {"nodes": [{"id": k, "name": v} for k,v in all_nodes.items()], "edges": edges}

            # 6. Bot/Coordinated Action Detection
            cursor.execute("""
                SELECT author_name, COUNT(*) as cnt FROM comments WHERE video_id=? GROUP BY author_name ORDER BY cnt DESC LIMIT 5
            """, (video_id,))
            top_posters = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT summary, ai_score, status FROM insights WHERE video_id=?", (video_id,))
            insight_row = cursor.fetchone()
            
            cursor.execute("SELECT content FROM comments WHERE video_id=?", (video_id,))
            all_txt = " ".join([str(r[0]) for r in cursor.fetchall() if r[0]])
            keywords = self._simple_keywords(all_txt)

            return {
                "sentiment_distribution": sentiment_distribution,
                "temporal": temporal,
                "temporal_day": temporal_day,
                "top_comments": top_comments,
                "top_posters": top_posters,
                "network_map": network_map,
                "insight": insight_row['summary'] if insight_row else "AI 요약 대기 중...",
                "ai_score": insight_row['ai_score'] if insight_row else 0,
                "status": insight_row['status'] if insight_row else "idle",
                "keywords": keywords
            }

    def _simple_keywords(self, text):
        import re
        from collections import Counter
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', text)
        stop = {'합니다', '하는', '정말', '진짜', '너무', '좋네요', '보고', '댓글', '영상', '감사합니다'}
        filtered = [w for w in words if w not in stop]
        return Counter(filtered).most_common(25)

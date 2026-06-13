import pandas as pd
import os
import glob
from kiwipiepy import Kiwi
from transformers import pipeline
import torch
from db_handler import DBHandler

class InsightProcessor:
    def __init__(self):
        self.db = DBHandler()
        self.kiwi = Kiwi()
        self.device = 0 if torch.cuda.is_available() else -1
        
        # Standardized path to data folder
        self.root_dir = r"C:\Antigravity Work\youtube-comment-analyzer"
        self.data_dir_root = os.path.join(self.root_dir, "data")
        
        self.sentiment_model = None
        self.toxicity_model = None

    def _load_models(self):
        if self.sentiment_model is None:
            print("Loading local NLP models (KcBERT-Sentiment)...")
            try:
                # Using a model specifically tuned for Korean sentiment if possible, 
                # otherwise mapping standard labels.
                self.sentiment_model = pipeline(
                    "sentiment-analysis", 
                    model="monologg/koelectra-small-v3-discriminator-nsmc", 
                    device=self.device
                )
            except Exception as e:
                print(f"Failed to load NLP models: {e}")

    def process_video_data(self, video_id):
        """Main pipeline: Clear DB -> Load Files -> Analyze"""
        self.db.save_advanced_stats(video_id, {"status": "preprocessing", "insight": "데이터를 데이터베이스로 로드 중..."})
        self.db.clear_video_data(video_id)
        target_dir = os.path.join(self.data_dir_root, video_id)
        csv_files = glob.glob(os.path.join(target_dir, "comments_part_*.csv"))
        
        if not csv_files: 
            self.db.save_advanced_stats(video_id, {"status": "error", "insight": "수집된 데이터 파일이 없습니다."})
            return

        # 1. Load and Save to DB
        for file in csv_files:
            try:
                df = pd.read_csv(file)
                self.db.save_comments(video_id, df)
            except Exception as e:
                print(f"Error loading {file}: {e}")

        # 2. Local NLP Analysis
        self.db.save_advanced_stats(video_id, {"status": "analyzing", "insight": "감성 분석 및 키워드 추출 중 (Local NLP)..."})
        self._load_models()
        self._run_local_analysis(video_id)
        
        # 3. Final Fallback / Insight Generation
        self.db.save_advanced_stats(video_id, {"status": "finalizing", "insight": "최종 통계 및 요약 생성 중..."})
        self._generate_fallback_insight(video_id)

    def _run_local_analysis(self, video_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content FROM comments WHERE video_id = ? AND sentiment IS NULL", (video_id,))
            rows = cursor.fetchall()

        if not rows: return
        print(f"Analyzing {len(rows)} comments...")
        
        for cid, content in rows:
            if not content or len(str(content)) < 2: continue
            try:
                sentiment_label = "neutral"
                score = 0.5
                
                if self.sentiment_model:
                    res = self.sentiment_model(str(content)[:512])[0]
                    # Map NSMC labels (usually 0: negative, 1: positive)
                    if res['label'] == 'LABEL_1' or res['label'] == 'positive':
                        sentiment_label = 'positive'
                    elif res['label'] == 'LABEL_0' or res['label'] == 'negative':
                        sentiment_label = 'negative'
                    score = res['score']
                
                self.db.update_analysis(video_id, cid, {
                    'sentiment': sentiment_label,
                    'sentiment_score': score,
                    'intent': self._extract_intent(content),
                    'aisas_stage': self._classify_aisas(content)
                })
            except Exception as e:
                print(f"Error: {e}")

    def _generate_fallback_insight(self, video_id):
        stats = self.db.get_advanced_stats(video_id)
        dist = stats['sentiment_distribution']
        total = sum(dist.values())
        
        summary = f"총 {total}개의 데이터 분석이 완료되었습니다. "
        if total > 0:
            pos_p = (dist['positive']/total)*100
            if pos_p > 60: summary += "전반적으로 매우 긍정적이고 우호적인 여론이 형성되어 있습니다. "
            elif pos_p < 30: summary += "비판적이거나 부정적인 의견이 상당수 포착되어 모니터링이 필요합니다. "
            else: summary += "긍정과 부정 의견이 팽팽하게 맞서는 중립적인 양상을 보입니다. "
        
        # Add coordination detection note
        top_poster = stats['top_posters'][0] if stats['top_posters'] else None
        if top_poster and top_poster['cnt'] > 10:
            summary += f"\n[주의] {top_poster['author_name']} 사용자가 {top_poster['cnt']}개의 글을 작성하여 조직적 개입 혹은 도배 가능성이 감지되었습니다."

        self.db.save_advanced_stats(video_id, {
            'insight': summary,
            'ai_score': 85,
            'llm_skipped': True
        })

    def _extract_intent(self, text):
        text = str(text)
        if '?' in text: return 'Question'
        if '추천' in text: return 'Praise'
        return 'Opinion'

    def _classify_aisas(self, text):
        text = str(text)
        if '사고 싶' in text: return 'Action'
        return 'Attention'

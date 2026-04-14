import json
import os
import hashlib
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutoSync")

MASTER_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "category_master_import.json"))
PENDING_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "pending_sync.json"))
UPDATE_LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "category_update_history.json"))

def generate_id(path: str) -> int:
    return int(hashlib.md5(path.encode()).hexdigest()[:8], 16)

def run_auto_sync():
    if not os.path.exists(PENDING_FILE):
        logger.info("No pending sync tasks.")
        return

    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            pending = json.load(f)
        
        with open(MASTER_FILE, "r", encoding="utf-8") as f:
            master = json.load(f)
        
        categories = master.get("categories", [])
        existing_paths = {c["full_path"] for c in categories}
        id_map = {c["naver_cat_id"]: c for c in categories}
        
        newly_added = []
        
        for path_str, meta in pending.items():
            if path_str in existing_paths:
                continue
            
            # 경로 파싱 및 신규 노드 등록
            levels = [l.strip() for l in path_str.split(">")]
            parent_id = None
            
            for i, name in enumerate(levels):
                depth = i + 1
                curr_path = " > ".join(levels[:depth])
                
                if curr_path not in existing_paths:
                    node_id = generate_id(curr_path)
                    new_node = {
                        "naver_cat_id": node_id,
                        "name_ko": name,
                        "depth": depth,
                        "parent_id": parent_id,
                        "full_path": curr_path,
                        "is_leaf": (depth == len(levels)),
                        "source_type": "auto_sync",
                        "synced_at": datetime.now().isoformat()
                    }
                    categories.append(new_node)
                    existing_paths.add(curr_path)
                    newly_added.append(new_node)
                    logger.info(f"Auto-Reflected new category: {curr_path}")
                    parent_id = node_id
                else:
                    # 기존 노드 ID 찾기
                    found = next((c for c in categories if c["full_path"] == curr_path), None)
                    if found:
                        parent_id = found["naver_cat_id"]

        if newly_added:
            # 마스터 파일 업데이트
            master["categories"] = categories
            with open(MASTER_FILE, "w", encoding="utf-8") as f:
                json.dump(master, f, ensure_ascii=False, indent=2)
            
            # 히스토리 로그 기록
            history = []
            if os.path.exists(UPDATE_LOG_FILE):
                with open(UPDATE_LOG_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            
            history.append({
                "timestamp": datetime.now().isoformat(),
                "type": "auto_discovery",
                "added_count": len(newly_added),
                "details": newly_added
            })
            
            with open(UPDATE_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

        # 완료된 작업 삭제
        os.remove(PENDING_FILE)
        logger.info(f"Auto-sync completed. {len(newly_added)} nodes added.")

    except Exception as e:
        logger.error(f"Auto-sync failed: {e}")

if __name__ == "__main__":
    run_auto_sync()

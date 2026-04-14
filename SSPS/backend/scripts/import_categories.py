import pandas as pd
import json
import os
import hashlib
from typing import Dict, List, Any, Optional

# 네이버 데이터랩 표준 12대 분야 (v2.41)
STANDARD_D1 = [
    "패션의류", "패션잡화", "화장품/미용", "디지털/가전", "가구/인테리어", 
    "출산/육아", "식품", "스포츠/레저", "생활/건강", "여가/생활편의", "면세점", "도서"
]

NORMALIZATION_MAP = {
    "화장품/미용 분야": "화장품/미용",
    "화장품": "화장품/미용",
    "미용": "화장품/미용",
    # 추가적인 변형이 발견되면 여기에 등록
}

class CategoryImporter:
    def __init__(self, xls_path: str, txt_path: str):
        self.xls_path = xls_path
        self.txt_path = txt_path
        self.categories: Dict[int, Dict[str, Any]] = {}  # naver_cat_id -> info
        self.name_path_to_id: Dict[str, int] = {}
        self.errors: List[Dict[str, Any]] = []

    def _normalize_name(self, name: str, depth: int) -> str:
        """이름 정규화 (특히 1단계)"""
        if depth == 1:
            return NORMALIZATION_MAP.get(name, name)
        return name

    def _generate_id(self, path: str) -> int:
        """ID가 없는 부모 노드를 위한 고정 ID 생성 (해시 활용)"""
        return int(hashlib.md5(path.encode()).hexdigest()[:8], 16)

    def parse_excel(self):
        print(f"Parsing Excel: {self.xls_path}")
        df = pd.read_excel(self.xls_path)
        
        for _, row in df.iterrows():
            cat_id = int(row.iloc[0])
            raw_levels = [str(row.iloc[i]).strip() for i in range(1, 5) if pd.notna(row.iloc[i]) and str(row.iloc[i]).strip().lower() != 'nan']
            
            # 정규화된 레벨 구성
            levels = []
            for i, name in enumerate(raw_levels):
                levels.append(self._normalize_name(name, i + 1))

            full_path = ""
            parent_id = None
            
            for i, name in enumerate(levels):
                depth = i + 1
                full_path = " > ".join(levels[:depth])
                is_row_leaf = (depth == len(levels))
                
                if full_path in self.name_path_to_id:
                    node_id = self.name_path_to_id[full_path]
                else:
                    if is_row_leaf:
                        node_id = cat_id
                    else:
                        node_id = self._generate_id(full_path)
                    
                    self.name_path_to_id[full_path] = node_id
                    self.categories[node_id] = {
                        "naver_cat_id": node_id,
                        "name_ko": name,
                        "depth": depth,
                        "parent_id": parent_id,
                        "full_path": full_path,
                        "is_leaf": False,
                        "source_type": "excel"
                    }
                
                parent_id = node_id

        # is_leaf 처리
        parent_ids = {cat["parent_id"] for cat in self.categories.values() if cat["parent_id"] is not None}
        for cat_id, cat in self.categories.items():
            if cat_id not in parent_ids:
                cat["is_leaf"] = True

    def parse_txt(self):
        """사용자가 제공한 텍스트 파일(화장품/미용)의 수동 구조를 반영"""
        print(f"Parsing Text: {self.txt_path}")
        if not os.path.exists(self.txt_path):
            print("Warning: Text file not found.")
            return

        with open(self.txt_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        current_hierarchy = [None, None, None, None]
        
        for line in lines:
            line = line.replace('\t', '    ')
            indent = len(line) - len(line.lstrip())
            depth = (indent // 3) + 1
            
            content = line.strip()
            if not content or '.' not in content: continue
            
            raw_name = content.split('.', 1)[1].strip()
            if ':' in raw_name: raw_name = raw_name.split(':', 1)[0].strip()
            
            name = self._normalize_name(raw_name, depth)
            current_hierarchy[depth-1] = name
            for j in range(depth, 4): current_hierarchy[j] = None
            
            full_path = " > ".join([n for n in current_hierarchy[:depth] if n])
            
            if full_path not in self.name_path_to_id:
                node_id = self._generate_id(full_path)
                parent_path = " > ".join([n for n in current_hierarchy[:depth-1] if n])
                parent_id = self.name_path_to_id.get(parent_path)
                
                self.name_path_to_id[full_path] = node_id
                self.categories[node_id] = {
                    "naver_cat_id": node_id,
                    "name_ko": name,
                    "depth": depth,
                    "parent_id": parent_id,
                    "full_path": full_path,
                    "is_leaf": True,
                    "source_type": "manual"
                }
                if parent_id and parent_id in self.categories:
                    self.categories[parent_id]["is_leaf"] = False

    def validate(self):
        print("Validating data...")
        to_remove = []

        for cid, cat in self.categories.items():
            # 1단계 검증
            if cat["depth"] == 1 and cat["name_ko"] not in STANDARD_D1:
                print(f"Warning: Non-standard D1 category found: {cat['name_ko']}")
                # 필요 시 여기서 자동 제거하거나 에러 처리 가능

            if cat["depth"] > 1 and cat["parent_id"] not in self.categories:
                self.errors.append({"naver_cat_id": cid, "error": "Parent missing", "data": cat})
                to_remove.append(cid)
            elif cat["depth"] < 1 or cat["depth"] > 4:
                self.errors.append({"naver_cat_id": cid, "error": "Invalid Depth", "data": cat})
                to_remove.append(cid)
        
        for cid in to_remove:
            if cid in self.categories:
                del self.categories[cid]
            
        print(f"Validation complete. Valid nodes: {len(self.categories)}, Errors: {len(self.errors)}")

    def get_closure_data(self) -> List[Dict[str, Any]]:
        closure = []
        for cid in self.categories:
            closure.append({"ancestor_id": cid, "descendant_id": cid, "depth": 0})
            curr = self.categories[cid]
            dist = 1
            while curr["parent_id"] is not None:
                pid = curr["parent_id"]
                if pid not in self.categories: break
                closure.append({"ancestor_id": pid, "descendant_id": cid, "depth": dist})
                curr = self.categories[pid]
                dist += 1
        return closure

    def save_to_json(self):
        output = {
            "categories": list(self.categories.values()),
            "closure": self.get_closure_data(),
            "summary": {
                "total": len(self.categories),
                "depth1": len([c for c in self.categories.values() if c["depth"] == 1]),
                "depth1_names": sorted(list({c["name_ko"] for c in self.categories.values() if c["depth"] == 1})),
                "depth4": len([c for c in self.categories.values() if c["depth"] == 4])
            }
        }
        with open("c:/Antigravity Work/backend/data/category_master_import.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("Saved to backend/data/category_master_import.json")

if __name__ == "__main__":
    importer = CategoryImporter(
        xls_path=r'C:\Antigravity Work\category_20260413_154020.xls',
        txt_path=r'C:\Antigravity Work\화장품 미용 분야 네이버 데이터랩 계층구조.txt'
    )
    importer.parse_excel()
    importer.parse_txt()
    importer.validate()
    importer.save_to_json()

if __name__ == "__main__":
    importer = CategoryImporter(
        xls_path=r'C:\Antigravity Work\category_20260413_154020.xls',
        txt_path=r'C:\Antigravity Work\화장품 미용 분야 네이버 데이터랩 계층구조.txt'
    )
    importer.parse_excel()
    importer.parse_txt()
    importer.validate()
    importer.save_to_json()

import pandas as pd
import json

def analyze_categories():
    df = pd.read_excel(r'C:\Antigravity Work\category_20260413_154020.xls')
    
    # 엑셀의 컬럼명이 깨졌을 수 있으므로 인덱스로 접근
    # 0: ID, 1: 대, 2: 중, 3: 소, 4: 세
    
    tree = {}
    id_map = {} # name_path -> naver_cat_id
    
    for _, row in df.iterrows():
        cat_id = row.iloc[0]
        d1 = str(row.iloc[1]).strip()
        d2 = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else None
        d3 = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None
        d4 = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else None
        
        # 실제 리프 노드의 이름과 경로 파악
        path_nodes = [d for d in [d1, d2, d3, d4] if d and d != 'nan']
        leaf_name = path_nodes[-1]
        full_path = " > ".join(path_nodes)
        
        # 리프 노드에 해당하는 ID 저장
        id_map[full_path] = int(cat_id)
        
    print(f"Total leaf categories processed: {len(id_map)}")
    
    # 중복 체크 및 구조 확인
    sample_keys = list(id_map.keys())[:10]
    for k in sample_keys:
        print(f"{k} : {id_map[k]}")

if __name__ == "__main__":
    analyze_categories()

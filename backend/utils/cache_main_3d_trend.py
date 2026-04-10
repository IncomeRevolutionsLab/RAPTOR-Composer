import sys
import os
import json
from pathlib import Path

# backend 모듈을 로드하기 위해 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.connectors.naver_connector import NaverConnector

def build_cache():
    print("[*] 네이버 데이터랩 API 통신 시작: 3D 차트 전용 데이터 캐싱")
    connector = NaverConnector()
    
    # 데이터랩 분야 명칭(10대 기준)으로 통일
    categories = [
        "패션의류", "화장품/미용", "디지털/가전", "가구/인테리어", "출산/육아",
        "식품", "스포츠/레저", "생활/건강", "여가/생활편의", "패션잡화"
    ]
    
    output_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "data" / "main_trend_3d.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    all_series = []
    months_keys = []
    
    # fetch_datalab_trend는 한 번에 5개의 키워드 배열을 받습니다.
    # 10개의 카테고리를 5개씩 2번에 나누어 호출합니다.
    for i in range(0, 10, 5):
        chunk = categories[i:i+5]
        print(f"  - Fetching {chunk}...")
        result = connector.fetch_datalab_trend(chunk)
        
        if result.get("status") == "FAIL":
            print(f"  [오류 발생] {result.get('reason')}")
            print("  API 키를 다시 확인해주세요.")
            return

        ts = result.get("trend_series", {})
        series_array = ts.get("series", [])
        
        if not months_keys:
            months_keys = ts.get("categories", ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"])
            
        for s in series_array:
            all_series.append({"name": s["name"], "data": s["data"]})
            
            
    # X: 카테고리(10개), Y: 시간(12개월), Z: 트렌드값(0~100)
    # app.js 요구사항에 맞춰 3차원 배열 생성
    data_3d = []
    names = categories
    months = months_keys if months_keys else ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]

    # 이름을 정렬된 원래의 10대 카테고리 순서대로 맞추기
    # API 응답 순서가 다를 수 있으므로 dict 처리
    series_dict = {s["name"]: s["data"] for s in all_series}

    for i, cat_name in enumerate(categories):
        pts = series_dict.get(cat_name, [0]*12)
        for j, val in enumerate(pts):
            if j < len(months):
                data_3d.append([j, i, int(val)])
                
    final_payload = {
        "categories": names,
        "months": months,
        "data": data_3d
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)
        
    print(f"[*] 캐시 생성 성공! ({output_path})")

if __name__ == "__main__":
    build_cache()

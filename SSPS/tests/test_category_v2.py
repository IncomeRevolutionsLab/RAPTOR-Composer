from backend.engine.category_manager import CategoryManager
import json

def test_category_engine():
    mgr = CategoryManager()
    
    # 1. 탑 레벨 카테고리 확인 (12개 목표)
    print(f"Top Level Categories ({len(mgr.top_level_categories)}): {mgr.top_level_categories}")
    
    # 2. 중의성 테스트 (마스크/팩)
    kw = "마스크/팩"
    match = mgr.match_from_keyword(kw)
    print(f"\nKeyword '{kw}' ambiguity test:")
    print(f" - Is Ambiguous: {match.get('is_ambiguous')}")
    print(f" - Found Paths: {len(match.get('all_paths', []))}")
    for i, p in enumerate(match.get('all_paths', [])):
        print(f"   [{i+1}] {' > '.join(p)}")

    # 3. TOP 5 트렌드 분석 테스트
    analysis = mgr.get_depth_trend_analysis(["패션의류", "여성의류"])
    if analysis:
        ranking = analysis.get('ranking', [])
        print(f"\nSub-category trend for Women Clothing: {len(ranking)} items found (Target: Max 5).")
        for r in ranking:
            print(f" - {r['rank']}. {r['name']} (Score: {r['avg_score']})")

if __name__ == "__main__":
    test_category_engine()

if __name__ == "__main__":
    test_category_engine()

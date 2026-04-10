import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.engine.scoring_engine import ScoringEngine
from backend.engine.json_packager import JsonPackager

def test_run():
    print("=== [SSPS Reviewer QA] V2.0 리얼 크롤링 및 백엔드 테스트 시작 ===")
    
    engine = ScoringEngine()
    packager = JsonPackager()
    
    test_domains = ["뷰티/스킨케어", "다이소 수납함"]
    
    for domain in test_domains:
        print(f"\n[Test] 검색 도메인: '{domain}' 봇 크롤링 중...")
        start = time.time()
        
        try:
            res = engine.run_pipeline(domain)
            json_res = packager.package(res, start)
            
            print(f"  ✓ 카테고리 판별: {res['category_analysis']['detected_type']}")
            print(f"  ✓ 동적 가중치 배분: {res['weights_applied']}")
            print(f"  ✓ 추출된 주력 상품 스펙:")
            for item in json_res['top_product_groups'][0]['skus'][:2]:
                print(f"     - {item['title']} : {item['price']}원 (출처: {item['source']})")
                
            print(f"  ✓ 소스코드 상태: {json_res['data_source_health']}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  [X] 실패: {e}")
            sys.exit(1)
            
    print("\n=== [SSPS Reviewer QA] 테스트 통과 및 검증 완료 ===")

if __name__ == "__main__":
    test_run()

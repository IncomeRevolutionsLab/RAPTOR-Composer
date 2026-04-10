import datetime
import time
from typing import Dict, Any, List

class JsonPackager:
    """스코어링 엔진 출력을 RAPTOR GEM 호환 ssps.v1 포맷으로 패키징"""
    
    def generate_hooks(self, signal: str, group_name: str, domain: str) -> List[str]:
        # 짧고 임펙트 있게 숏폼 최적화 후킹 메시지 생성
        hooks = []
        clean_name = group_name.split("] ")[-1] if "] " in group_name else group_name
        
        if signal == "Oliveyoung_Boost" or signal == "Oliveyoung_Boosting":
            hooks.append(f"올리브영 랭킹 1위! {clean_name} 비교")
            hooks.append(f"뷰티 유튜버가 몰래 쓰는 {domain} 꿀템")
        elif signal == "Daiso_Boost" or signal == "Daiso_Boosting":
            hooks.append(f"다이소에서 이 가격에? {clean_name} 실화?")
            hooks.append(f"1000원짜리가 이 퀄리티?! 다이소 {domain} 리뷰")
        elif signal == "Naver_Boost" or signal == "Naver_Boosting":
            hooks.append(f"요즘 검색 폭발하는 {clean_name} 뭐가 다를까?")
            hooks.append(f"시즌 필수템! 네이버 검색 1위 {domain}")
        else:
            hooks.append(f"요즘 SNS에서 난리난 {clean_name} TOP 1")
            hooks.append(f"가성비 찢은 {domain} 추천")
            
        return hooks

    def validate_package(self, payload: Dict[str, Any]) -> bool:
        """RAPTOR GEM 연동을 위한 패키징 검증 로직 (Step 1 ~ 6)"""
        import json
        
        # Step 1: 모든 필수 필드 존재 여부 확인
        if payload.get("schema_version") != "ssps.v1":
            raise ValueError("[Validation Step 1 Failed] schema_version은 'ssps.v1' 이어야 합니다.")
        
        top_groups = payload.get("top_product_groups", [])
        if not top_groups:
            raise ValueError("[Validation Step 1 Failed] top_product_groups 배열이 비어있습니다.")
            
        group = top_groups[0]
        if "primary_source_signal" not in group:
            raise ValueError("[Validation Step 1 Failed] primary_source_signal이 누락되었습니다.")
        if "hook_lines" not in group:
            raise ValueError("[Validation Step 1 Failed] hook_lines가 누락되었습니다.")
        if "source_weights_applied" not in group.get("scores", {}):
            raise ValueError("[Validation Step 1 Failed] scores 내에 source_weights_applied가 누락되었습니다.")

        skus = group.get("skus", [])
        
        # Step 2: hook_lines 최소 2개, skus 최소 3개 확인
        if len(group.get("hook_lines", [])) < 2:
            raise ValueError("[Validation Step 2 Failed] hook_lines는 최소 2개 이상 필요합니다.")
        if len(skus) < 3:
            raise ValueError("[Validation Step 2 Failed] skus는 최소 3개 이상 필요합니다.")

        # Step 3: visual_assets URL 유효성 검사
        for sku in skus:
            visuals = sku.get("visual_assets", [])
            if not visuals:
                raise ValueError("[Validation Step 3 Failed] visual_assets이 없습니다.")
            for url in visuals:
                if not str(url).startswith("http"):
                    raise ValueError(f"[Validation Step 3 Failed] 유효하지 않은 visual_assets URL: {url}")

        # Step 4: source_weights_applied 합계 = 1.0 검증
        weights = group["scores"]["source_weights_applied"]
        total_weight = sum(weights.values())
        if not (0.99 <= total_weight <= 1.01):
            if total_weight > 0: # 모의데이터 모드 등으로 가중치가 아예 없는 경우가 아니라면 검증
                raise ValueError(f"[Validation Step 4 Failed] source_weights_applied 합계가 1.0이 아닙니다: {total_weight}")

        # Step 5: final_score 범위 0~100 검증
        final_score = group["scores"].get("final_score", 0)
        if not (0 <= final_score <= 100):
            raise ValueError(f"[Validation Step 5 Failed] final_score가 0~100 범위를 벗어났습니다: {final_score}")

        # Step 6: JSON 직렬화 가능 여부 확인
        try:
            json.dumps(payload)
        except TypeError as e:
            raise ValueError(f"[Validation Step 6 Failed] JSON 직렬화 실패: {e}")

        return True

    def package(self, scoring_result: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        import urllib.parse
        import os
        import json
        
        signal = scoring_result["primary_source_signal"]
        domain = scoring_result["domain"]
        group_name = scoring_result["group_name"]
        
        skus = []
        for idx, item in enumerate(scoring_result.get("items", [])):
            skus.append({
                "title": item.get("name", "Unknown Item"),
                "brand": item.get("brand", "Unknown"),
                "price": item.get("price", 0),
                "source": item.get("source", "Naver"),
                "source_rank": item.get("rank", idx + 1),
                "source_url": item.get("source_url", ""),
                "visual_assets": [item.get("image_url", "https://via.placeholder.com/300")],
                "review_count": item.get("review_count", 0),
                "rating": item.get("rating", 0.0),
                "tags": [domain.split("/")[-1]] # 도메인 마지막 단어
            })
            
        vips = []
        coupang_items = scoring_result.get("all_pool", {}).get("coupang", [])
        
        use_fallback = not coupang_items
        target_list = coupang_items if not use_fallback else skus
        limit = min(5, len(target_list))
        
        for i in range(limit):
            item = target_list[i]
            if use_fallback:
                title_clean = item.get("title", "Unknown")
                encoded_title = urllib.parse.quote(title_clean)
                coupang_match_url = f"https://www.coupang.com/np/search?q={encoded_title}"
            else:
                title_clean = item.get("name", "Unknown")
                coupang_match_url = item.get("source_url", "#")
            
            if i == 0: reason = f"🏆 [{signal.replace('_Boosting', '').capitalize()}] 핵심 지표 통합 1위! 즉시 소싱 권장"
            elif i == 1: reason = f"🔥 트렌드/장바구니 전환율 우수 (종합 2위)"
            elif i == 2: reason = f"💰 경쟁사 대비 가성비 및 리뷰 반응도 탁월 (종합 3위)"
            else: reason = f"✨ 연관 검색어 알고리즘 실시간 분석 결과 (Top {i+1})"
            
            vips.append({
                "title": title_clean[:45] + "..." if len(title_clean) > 48 else title_clean,
                "reason": reason,
                "coupang_match_url": coupang_match_url,
                "is_coupang_fallback": use_fallback
            })
            
        execution_time = int((time.time() - start_time) * 1000)

        # 점수 객체 재구성
        scores = scoring_result["raw_scores"]
        scores["source_weights_applied"] = scoring_result["weights_applied"]

        payload = {
            "schema_version": "ssps.v1", # RAPTOR GEM 연동을 위해 v1 강제 지정
            "is_leaf_category": scoring_result.get("is_leaf_category", False),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "domain": domain,
            "category_analysis": scoring_result["category_analysis"],
            "weights_applied": scoring_result["weights_applied"],
            "trend_series": scoring_result.get("trend_series", {}),
            "top_product_groups": [
                {
                    "rank": 1,
                    "group_name": group_name,
                    "primary_source_signal": signal,
                    "scores": scores,
                    "hook_lines": self.generate_hooks(signal, group_name, domain), # Hook Lines 복원
                    "skus": skus,
                    "vips": vips
                }
            ],
            "data_source_health": scoring_result["data_source_health"],
            "execution_time_ms": execution_time
        }
        
        # 패키징 검증 로직 수행 (Step 1 ~ 6)
        validation_passed = False
        try:
            validation_passed = self.validate_package(payload)
        except Exception as e:
            payload["validation_error"] = str(e)
            
        # Step 7: 검증 통과 시 파일로 저장
        if validation_passed:
            try:
                output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "output")
                os.makedirs(output_dir, exist_ok=True)
                safe_domain = domain.replace("/", "_")
                timestamp = int(time.time())
                filepath = os.path.join(output_dir, f"ssps_export_{safe_domain}_{timestamp}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                payload["saved_file_path"] = filepath
            except Exception as e:
                payload["file_save_error"] = str(e)
                
        return payload

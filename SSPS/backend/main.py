import os
import sys
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.scoring_engine import ScoringEngine
from backend.engine.json_packager import JsonPackager
from backend.engine.raptor_engine import raptor_engine
from backend.engine.raptor_bridge import raptor_bridge
from backend.connectors.supabase_client import SupabaseClient
from backend.utils.cache_manager import cache

app = Flask(__name__, static_folder="../frontend")
supabase = SupabaseClient()

# CORS 설정: 클라우드 배포(Render/Vercel) 환경에서는 완전 개방하여 통신 안정성 확보
# 로컬 개발 환경(포트 정보 없음)에서만 특정 origin 제한
if os.environ.get("PORT"):
    CORS(app)  # Render/Cloud 환경에서는 모든 연결 허용
else:
    CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:3000"])

engine = ScoringEngine()
packager = JsonPackager()

@app.route("/api/v1/analyze", methods=["POST"])
def analyze_domain():
    try:
        data = request.get_json()
        if not data or "domain" not in data:
            return jsonify({"error": "domain is required"}), 400
            
        domain = data["domain"]
        m_olive = data.get("manual_oliveyoung", "")
        m_daiso = data.get("manual_daiso", "")
        fallback_choice = data.get("fallback_choice", "coupang")  # 쿠팡 디폴트, 'naver' 선택 가능
        start_time = time.time()
        
        # [파이프라인 진행]
        scoring_res = engine.run_pipeline(domain, manual_olive=m_olive, manual_daiso=m_daiso, fallback_choice=fallback_choice)
        
        # 에러 판독(전체 봇 실패 시)
        if "error" in scoring_res:
            return jsonify({"error": scoring_res["error"]}), 400
            
        final_json = packager.package(scoring_res, start_time)
        
        cache.set(domain, "json_output", final_json)
        
        # [v2.35] 분석 성공 시 실시간 카운트 증가
        supabase.increment_analysis_count()
        
        return jsonify(final_json)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/category_node", methods=["POST"])
def category_node():
    """N-Depth 동적 재귀 라우터 (근본 단일 파이프라인 처리)"""
    try:
        data = request.get_json()
        path = (data or {}).get("path", [])
        keyword = (data or {}).get("keyword", "")

        # 키워드 기반 검색일 경우 강제로 트리 경로(path) 최적화 변환 수행
        if keyword and not path:
            matched_path = engine.router.cat_mgr.get_path_from_keyword(keyword)
            if matched_path:
                path = matched_path
                
        if not path or not isinstance(path, list):
            return jsonify({"error": "path array or valid keyword is required"}), 400
            
        result = engine.run_category_node(path)
        if "error" in result:
            return jsonify(result), 400
            
        # [v2.35] N-Depth 분석 성공 시에도 실시간 카운트 증가
        supabase.increment_analysis_count()
        
        return jsonify(result)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/popular_keywords", methods=["GET"])
def popular_keywords():
    """최근 1주일 인기 검색어 목록 반환 (v2.52: 안정성 강화)"""
    from backend.connectors.naver_connector import NaverConnector
    import os
    
    domain = request.args.get("domain", "패션의류")
    try:
        naver = NaverConnector()
        res = naver.fetch_popular_keywords(domain)
        
        # 파일 로드 실패 시에도 서비스 유지를 위해 빈 배열보다는 Fallback 제공
        if not res or (isinstance(res, dict) and "items" in res and not res["items"]):
             return jsonify({"domain": domain, "items": ["여름코디", "가성비템", "신상품", "추천상품"], "period": "실시간"})
             
        return jsonify(res)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logger.error(f"[Main] Popular Keywords Error: {error_msg}")
        return jsonify({
            "domain": domain, 
            "items": ["에러 발생"], 
            "error_detail": error_msg,
            "period": "-"
        }), 200

@app.route("/api/v1/stats", methods=["GET"])
def get_site_stats():
    """[v2.55 복구] 실시간 분석 통계(누적 분석 수 등) 반환"""
    try:
        stats = supabase.get_site_stats()
        return jsonify(stats)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logger.error(f"[Main] Stats API Error: {error_msg}")
        return jsonify({
            "total_analysis": 0, 
            "top_domain": "식품", 
            "top_domain_desc": "-",
            "error_detail": error_msg
        }), 200

@app.route("/api/v1/domains/trend", methods=["GET"])
def get_domain_trend():
    """[v2.52] 12대 분야 전역 정합성 트렌드 API (강력한 Fallback 포함)"""
    try:
        from backend.connectors.naver_connector import NaverConnector
        naver = NaverConnector()
        
        domains = [
            {'name': '패션의류', 'cid': 50000000}, {'name': '패션잡화', 'cid': 50000001},
            {'name': '화장품/미용', 'cid': 50000002}, {'name': '디지털/가전', 'cid': 50000003},
            {'name': '가구/인테리어', 'cid': 50000004}, {'name': '출산/육아', 'cid': 50000005},
            {'name': '식품', 'cid': 50000006}, {'name': '스포츠/레저', 'cid': 50000007},
            {'name': '생활/건강', 'cid': 50000008}, {'name': '여가/생활편의', 'cid': 50000009},
            {'name': '도서', 'cid': 50000010}, {'name': '면세점', 'cid': 50000011}
        ]
        
        anchor = domains[0]
        global_series = []
        months = []
        
        # 1. 네이버 실시간 데이터 수집 시도 (5개 단위 정석 배치)
        try:
            # [v2.55] 5개씩 3번 나누어 조회 (네이버 API 제한 준수)
            batch1 = domains[0:5]
            batch2 = domains[5:10]
            batch3 = domains[10:12]
            
            for batch in [batch1, batch2, batch3]:
                if not batch: continue
                res = naver.fetch_multi_shopping_trend(batch)
                if res.get("status") == "OK":
                    trend = res.get("trend_series", {})
                    batch_series = trend.get("series", [])
                    if batch_series:
                        if not months: months = trend.get("categories", [])
                        global_series.extend(batch_series)
                else: 
                    logger.warning(f"[Main] Batch failed: {res.get('reason')}")
        except Exception as api_e:
            logger.warning(f"[Main] Naver API Domain Trend failed: {api_e}")

        # 2. 데이터가 부족할 경우 로컬 수집 데이터 또는 Fallback 생성 (차트 실종 방지)
        if not global_series or len(global_series) < 12:
            import random
            logger.info("[Main] Using Fallback Data for Domain Trend")
            months = months or ["04월", "05월", "06월", "07월", "08월", "09월", "10월", "11월", "12월", "01월", "02월", "03월"]
            base_scores = [85, 45, 78, 62, 55, 64, 82, 65, 72, 47, 40, 30]
            global_series = []
            for idx, domain in enumerate(domains):
                base = base_scores[idx]
                global_series.append({
                    "name": domain['name'],
                    "data": [max(10, min(100, base + random.randint(-15, 15))) for _ in range(len(months))]
                })

        # Echarts 3D 데이터로 변환 (v2.53: 정렬 보증 및 데이터 유효성 검증 강화)
        categories = [d['name'] for d in domains]
        data_points = []
        sorted_series = []
        
        for d in domains:
            s_item = next((s for s in global_series if s['name'] == d['name']), None)
            if s_item:
                sorted_series.append(s_item)
            else:
                # 특정 분야 데이터가 누락된 경우 즉석에서 안전한 기본값 생성 (Blackout 방지)
                logger.warning(f"[Main] Data missing for domain: {d['name']}. generating safety default.")
                sorted_series.append({
                    "name": d['name'],
                    "data": [random.randint(20, 50) for _ in range(len(months))]
                })

        for cat_idx, s in enumerate(sorted_series):
            for m_idx, val in enumerate(s.get('data', [])):
                data_points.append([m_idx, cat_idx, val])
                
        logger.info(f"[Main] Domain Trend API success. Points: {len(data_points)}")
        return jsonify({
            "status": "success",
            "months": months,
            "categories": categories,
            "data": data_points
        })
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logger.error(f"[Main] Domain Trend Global Error: {error_msg}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "error_detail": error_msg
        }), 500

@app.route("/api/v1/raptor/generate-plan", methods=["POST"])
async def raptor_generate_plan():
    """[v2.4] RAPTOR GEM: AI 숏폼 기획안 생성"""
    try:
        data = request.json
        ssps_data = data.get("ssps_data")
        duration = int(data.get("duration", 30))
        
        if not ssps_data:
            return jsonify({"error": "SSPS 데이터가 누락되었습니다."}), 400
            
        # [v2.45] Gemini 3.1 Pro (High) 엔진 호출 (Official Raptor Gem)
        plan_result = await raptor_engine.generate_plan(ssps_data, duration)
        return jsonify(plan_result)
    except Exception as e:
        logger.error(f"[Main] Raptor Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/raptor/generate-video", methods=["POST"])
async def raptor_generate_video():
    """[v2.4] RAPTOR Extended: AI 숏폼 영상 생성 (BYOK 방식)"""
    try:
        data = request.json
        engine = data.get("engine")
        # 프론트엔드 LocalStorage에서 전달된 API Key (서버 저장 안함)
        api_key = data.get("api_key")
        payload = data.get("payload", {})
        
        if not engine or not api_key:
            return jsonify({"error": "engine 타입과 api_key가 필요합니다."}), 400
            
        # 브릿지를 통해 외부 엔진(Veo/Kling 등) 호출
        result = await raptor_bridge.generate_video_request(engine, api_key, payload)
        return jsonify(result)
    except Exception as e:
        logger.error(f"[Main] Raptor Video Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/reset_stats_only", methods=["GET"])
def reset_stats_only():
    """[임시] DB 통계를 0으로 초기화"""
    try:
        # id=1 레코드를 0으로 강제 업데이트
        supabase.client.table('site_stats').upsert({
            "id": 1, 
            "total_analysis": 0, 
            "top_domain": "식품", 
            "top_domain_desc": "(최근 7일 클릭 지수 1위)"
        }).execute()
        return "Reset Success"
    except Exception as e:
        return f"Reset Failed: {e}"

# [Cold Start 대응] Render 무료 서버 웜업용 헬스체크 엔드포인트
# 프론트엔드가 페이지 로드 시 이 주소를 호출해 잠든 서버를 깨웁니다.
@app.route("/api/v1/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "SSPS Engine is running!"}), 200

# 디폴트 라우터: index.html 렌더링 (대시보드 표시)
@app.route("/")
def serve_dashboard():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    from backend.config import settings
    # 클라우드 호스팅(Render 등) 환경변수를 우선 적용하고 없으면 로컬 settings.port(5000)를 사용합니다.
    port = int(os.environ.get("PORT", settings.port))
    app.run(host="0.0.0.0", port=port, debug=False)

import os
import sys
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engine.scoring_engine import ScoringEngine
from backend.engine.json_packager import JsonPackager
from backend.engine.raptor_engine import raptor_engine
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
    """최근 1주일 인기 검색어 목록 반환"""
    from backend.connectors.naver_connector import NaverConnector
    domain = request.args.get("domain", "패션의류")
    try:
        naver = NaverConnector()
        res = naver.fetch_popular_keywords(domain)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/status", methods=["GET"])
def get_status():
    from backend.connectors.naver_connector import naver_shopping_cb
    from backend.connectors.oliveyoung_scraper import oliveyoung_cb
    from backend.connectors.daiso_scraper import daiso_cb
    return jsonify({
        "status": "Running (Flask)",
        "cache_stats": cache.stats(),
        "circuit_breakers": [
            naver_shopping_cb.get_status(),
            oliveyoung_cb.get_status(),
            daiso_cb.get_status()
        ]
    })

@app.route("/api/v1/stats", methods=["GET"])
def get_site_stats():
    """실시간 누적 분석 횟수 및 Top 분야 정보 반환"""
    stats = supabase.get_site_stats()
    return jsonify(stats)

@app.route("/api/v1/raptor/generate-plan", methods=["POST"])
async def raptor_generate_plan():
    """[v2.4] RAPTOR GEM: AI 숏폼 기획안 생성"""
    try:
        data = request.json
        ssps_data = data.get("ssps_data")
        duration = int(data.get("duration", 30))
        
        if not ssps_data:
            return jsonify({"error": "SSPS 데이터가 누락되었습니다."}), 400
            
        # Gemini 1.5 Pro 엔진 호출
        plan_result = await raptor_engine.generate_plan(ssps_data, duration)
        return jsonify(plan_result)
    except Exception as e:
        logger.error(f"[Main] Raptor Error: {e}")
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

import os
import json
import logging
import datetime
import google.generativeai as genai
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class RaptorEngine:
    """
    RAPTOR GEM: AI Short-form Planning Engine (v2.45)
    - SSPS의 시장 분석 데이터를 기반으로 Gemini 3.1 Pro (High)를 활용하여 초정밀 마케팅 기획안을 생성합니다.
    - [Sustainable Structure]: 데이터 정제(Refinement) 층을 두어 엔진과 데이터 간의 결합도를 낮췄습니다.
    """

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model_name = "gemini-3.1-pro-high-latest"
        self.version = "v2.45-Official-High"
        self.is_ready = False

        if self.api_key and self.api_key != "YOUR_GEMINI_API_KEY":
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.is_ready = True
                logger.info(f"[RaptorEngine] Gemini 3.1 Pro (High) Initialized. Version: {self.version}")
            except Exception as e:
                logger.error(f"[RaptorEngine] Initialization Failed: {e}")
        else:
            logger.warning("[RaptorEngine] Gemini API Key is missing. Running in Mock Mode.")

    async def generate_plan(self, ssps_data: Dict[str, Any], duration: int = 30) -> Dict[str, Any]:
        """
        SSPS 분석 데이터를 마케팅 언어로 정제한 후 숏폼 기획안을 생성합니다.
        """
        if not self.is_ready:
            return self._generate_mock_plan(ssps_data, duration)

        # 1. 데이터 정제 (Data Refinement - 근본적 구조 해결)
        refined_data = self._refine_ssps_data(ssps_data)
        
        # 2. 다이내믹 프롬프트 구성
        prompt = self._build_prompt(refined_data, duration)

        try:
            # 3. Gemini 3.1 Pro (High) 추론 호출
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.8, # 창의성 극대화
                    top_p=0.95,
                    max_output_tokens=2500,
                )
            )

            return {
                "status": "success",
                "engine": f"Gemini 3.1 Pro (High) - {self.version}",
                "duration_target": f"{duration}초",
                "generated_at": datetime.datetime.now().isoformat(),
                "planning_document": response.text
            }

        except Exception as e:
            logger.error(f"[RaptorEngine] AI Generation Error: {e}")
            return {"status": "error", "message": f"AI 기획 중 오류 발생: {str(e)}"}

    def _refine_ssps_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        [Structural Fix] SSPS 날것의 데이터를 AI 기획용 정제 데이터로 변환
        변화하는 SSPS 데이터 규격에 유연하게 대응하기 위한 완충 지대 역할을 합니다.
        """
        domain = data.get("domain", "입력되지 않음")
        price_target = data.get("raw_scores", {}).get("price_tier", "GENERAL")
        
        # 상품군 정보 추출 (N-Depth vs V1 하이브리드 대응)
        product_items = data.get("items", []) or data.get("products", [])
        top_items = product_items[:5] if product_items else []
        
        return {
            "category": domain,
            "target_value": "가성비/저가형" if price_target == "LOWPRICE" else "프리미엄/트렌드",
            "top_products": top_items,
            "analysis_metadata": data.get("category_analysis", {})
        }

    def _build_prompt(self, refined: Dict[str, Any], duration: int) -> str:
        """분석 데이터와 가변 시간을 결합한 초청밀 마케팅 프롬프트"""
        products_str = "\n".join([f"- {p.get('name') or p.get('title')} ({p.get('price'):,}원)" for p in refined['top_products']])

        return f"""
역할: 당신은 대한민국 0.1% 수준의 숏폼 마케팅 전문가이자 크리에이티브 디렉터입니다.
SSPS(Smart Selection Planning System)가 분석한 다음의 데이터를 바탕으로, 구매 전환율이 보장되는 숏폼 기획안을 작성하세요.

[SSPS 분석 리포트 요약]
- 분석 분야: {refined['category']}
- 시장 포지셔닝: {refined['target_value']}
- 주요 경쟁 상품군:
{products_str}
- 시즌성/이슈: {refined.get('seasonality', '중립')} (분석 결과 기반)

[기획 핵심 요청 사항]
1. 목표 영상 길이: 반드시 **{duration}초** 구성 (초 단위의 타임라인 명시).
2. 타겟 페르소나: 이 상품 데이터가 가리키는 가장 날카로운 타겟을 1문장으로 정의.
3. 숏폼 성공 방정식 적용 (Hook-Body-CTA):
   - [0-3초] 시청 차단(Stop Scrolling)을 유도하는 강렬한 시각/청각적 후킹.
   - [본론] 제품의 핵심 USP(Unique Selling Point)를 시장 데이터 기반으로 제시.
   - [마무리] 댓글 참여 유도 또는 상단 링크 클릭을 부드럽게 제안하는 CTA.
4. 연출 디테일: 배경음악(BGM) 톤앤매너, 자막 배치 전략, 컷 전환(Transition) 타이밍 포함.

[출력 형식]
- 반드시 한국어로 작성.
- 대표님께 보고하는 격조 있는 '마케팅 기획서' 형식을 갖출 것.
- 가독성을 위해 적절한 이모지와 마크다운 문법을 활용하여 시각적으로 WOW 포인트를 줄 것.
"""

    def _generate_mock_plan(self, data: Dict[str, Any], duration: int) -> Dict[str, Any]:
        return {
            "status": "mock",
            "planning_document": f"## 🚀 {data.get('domain')} 분야 예시 기획안\n\n현재 API 키가 설정되지 않아 시스템의 핵심 알고리즘(v2.45)에 따른 모의 데이터를 노출합니다."
        }

raptor_engine = RaptorEngine()

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
        """[v2.75] 숏폼 시청 지속률(Retention) 극대화를 위한 초정밀 마케팅 프롬프트"""
        products_str = "\n".join([f"- {p.get('name') or p.get('title')} ({p.get('price'):,}원)" for p in refined['top_products']])

        return f"""
역할: 당신은 대한민국 0.1% 수준의 숏폼 마케팅 전문가이자 크리에이티브 디렉터입니다.
SSPS 분석 데이터를 바탕으로 **'시청자가 1초도 지루할 틈이 없는'** 고몰입도 숏폼 기획안을 작성하세요.

[SSPS 분석 데이터]
- 분야: {refined['category']}
- 타겟 가치: {refined['target_value']}
- 분석 상품 리스트:
{products_str}

[필수 기획 조건 - 절대 준수]
1. **장면(Scene) 1:1 매칭**: 전체 영상(약 {duration}초)을 여러 장면으로 나누고, 각 장면마다 [대사] + [이미지 생성 프롬프트] + [효과음/액션]이 반드시 세트로 구성되어야 합니다. (장면이 7개면 이미지도 7개여야 함)
2. **오디오 공백 제로 (No Silence)**: 숏폼에서 정적은 이탈입니다. 나레이션이 끊기지 않고 물 흐르듯 이어지도록 대본을 작성하세요. 
3. **나레이션 템포**: 보통 속도보다 1.2배 빠른, 힘 있는 톤의 나레이션을 가정하여 대본 길이를 조절하세요.
4. **ASMR & 액션 예외**: 고기 굽는 소리, 강렬한 언박싱 등 시청각적 임팩트가 큰 장면은 대사 대신 상세한 [효과음(SFX)] 묘사로 채워 지루함을 방지하세요.
5. **이미지 퀄리티**: 텍스트로도 이미지가 눈앞에 그려질 만큼 입체적이고 상세한 '이미지 전용 프롬프트'를 각 장면별로 작성하세요.

[출력 형식]
1. **기획 컨셉**: 타겟 인텐트와 핵심 소구점 (1문장)
2. **장면별 상세 대본 (Table 형식 선호)**:
   - 장면 번호 | 대사(나레이션) | 이미지 생성용 상세 프롬프트 | 연출/효과음(SFX)
3. **최종 마케팅 카피**: 영상의 핵심 메시지

가독성을 위해 마크다운과 이모지를 조화롭게 사용하고, 대표님께서 보시기에 즉시 제작에 들어갈 수 있을 만큼 구체적이어야 합니다.
"""

    def _generate_mock_plan(self, data: Dict[str, Any], duration: int) -> Dict[str, Any]:
        return {
            "status": "mock",
            "planning_document": f"## 🚀 {data.get('domain')} 분야 예시 기획안\n\n현재 API 키가 설정되지 않아 시스템의 핵심 알고리즘(v2.45)에 따른 모의 데이터를 노출합니다."
        }

raptor_engine = RaptorEngine()

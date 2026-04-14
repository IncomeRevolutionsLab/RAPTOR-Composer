import os
import json
import logging
import datetime
import google.generativeai as genai
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class RaptorEngine:
    """
    RAPTOR GEM: AI Short-form Planning Engine
    - SSPS 데이터를 기반으로 Gemini 1.5 Pro를 활용하여 마케팅 기획안을 자동 생성합니다.
    - 15초~60초 가변 시간에 대응하는 다이내믹 프롬프트가 탑재되어 있습니다.
    """

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model_name = "gemini-3.1-pro-high-latest"
        self.is_ready = False

        if self.api_key and self.api_key != "YOUR_GEMINI_API_KEY":
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.is_ready = True
                logger.info(f"[RaptorEngine] Gemini 1.5 Pro Initialized.")
            except Exception as e:
                logger.error(f"[RaptorEngine] Initialization Failed: {e}")
        else:
            logger.warning("[RaptorEngine] Gemini API Key is missing. Running in Mock Mode.")

    async def generate_plan(self, ssps_data: Dict[str, Any], duration: int = 30) -> Dict[str, Any]:
        """
        SSPS V1 JSON 데이터를 분석하여 숏폼 기획안을 생성합니다.
        @param ssps_data: JsonPackager가 생성한 규격 데이터
        @param duration: 목표 영상 길이 (15 ~ 60초)
        """
        if not self.is_ready:
            return self._generate_mock_plan(ssps_data, duration)

        # 1. 프롬프트 구성
        prompt = self._build_prompt(ssps_data, duration)

        try:
            # 2. Gemini API 호출 (1.5 Pro의 강력한 추론 활용)
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=2048,
                )
            )

            # 3. 마크다운 결과 정제 및 반환
            full_text = response.text
            return {
                "status": "success",
                "engine": self.model_name,
                "duration_target": f"{duration}s",
                "generated_at": datetime.datetime.now().isoformat(),
                "planning_document": full_text
            }

        except Exception as e:
            logger.error(f"[RaptorEngine] Generation Error: {e}")
            return {"status": "error", "message": str(e)}

    def _build_prompt(self, data: Dict[str, Any], duration: int) -> str:
        """분석 데이터와 가변 시간을 결합한 정밀 프롬프트 생성"""
        domain = data.get("domain", "Unknown")
        group = data.get("top_product_groups", [{}])[0]
        skus = group.get("skus", [])[:3]
        hooks = group.get("hook_lines", [])

        sku_list_str = "\n".join([f"- {s.get('title')} ({s.get('price')}원)" for s in skus])
        hook_str = ", ".join(hooks)

        return f"""
역할: 당신은 대한민국 최고의 틱톡/릴스/쇼츠 숏폼 전문 마케터이자 영상 피디입니다.
SSPS(지능형 쇼핑 선정 시스템)의 분석 데이터를 바탕으로 매출을 극대화할 수 있는 '숏폼 기획안'을 작성하세요.

[분석 데이터 기초 정보]
- 분석 분야: {domain}
- 추천 상품 명칭: {group.get('group_name')}
- 핵심 주력 상품(Top 3):
{sku_list_str}
- 시스템 제안 초기 후킹 멘트: {hook_str}

[요청 사항]
1. 목표 영상 길이: 반드시 **{duration}초** 분량에 딱 맞춘 구성을 짜주세요.
2. 타겟 오디언스 분석: 이 상품을 가장 즉각적으로 구매할 것 같은 좁고 날카로운 타겟을 설정하세요.
3. 영상 컨셉 및 톤앤매너: 짧고 강렬한 숏폼 트렌드에 맞는 컨셉을 제안하세요.
4. 3단 구성 스크립트:
   - 0~{int(duration*0.15)}초 (HOOK): 시선을 1초 만에 사로잡는 강력한 오프닝 문구와 장면.
   - {int(duration*0.15)}~{int(duration*0.8)}초 (BODY): 제품의 핵심 소구점(USP)을 데이터 근거로 풀어내는 본문.
   - {int(duration*0.8)}~{duration}초 (CTA): 댓글 확인이나 프로필 링크 클릭을 유도하는 강력한 클로징.
5. 연출 가이드: 추천 배경음악(BGM) 장르, 자막 스타일, 전환 효과(Transition) 팁을 포함하세요.

[출력 형식]
사용자가 보기 편하도록 깔끔한 마크다운(Markdown) 형식으로 한국어로 작성하세요.
각 섹션을 이모지와 함께 웅장하게 표현하세요.
"""

    def _generate_mock_plan(self, data: Dict[str, Any], duration: int) -> Dict[str, Any]:
        """API 키가 없을 때 작동하는 모의 데이터 모드"""
        domain = data.get("domain", "Unknown")
        return {
            "status": "mock",
            "message": "GEMINI_API_KEY가 설정되지 않아 생성된 예시 기획안입니다.",
            "duration_target": f"{duration}s",
            "planning_document": f"## 🚀 [{domain}] 숏폼 기획안 (Mock)\n\n"
                                f"**목표 길이**: {duration}초\n"
                                f"**타겟**: 2030 트렌드 세터\n\n"
                                f"1. **HOOK**: '아직도 이걸 모르세요?' (강렬한 텍스트 자막)\n"
                                f"2. **BODY**: SSPS 데이터가 증명하는 {domain} 1위 아이템의 위력 공개\n"
                                f"3. **CTA**: 지금 바로 프로필 링크를 확인하세요!"
        }

raptor_engine = RaptorEngine()

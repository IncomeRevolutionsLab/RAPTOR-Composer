import requests
import base64

class KieAiClient:
    def __init__(self):
        self.base_url = "https://api.kie.ai/v1"

    def _build_grok_payload(self, product_name: str, image_url: str, duration: int, quality: str):
        """
        Test 2: 하이브리드 해상도 분기 로직
        - preview: 480p (비용 최적화)
        - export: 720p (품질 확보)
        """
        res_map = {
            "preview": "480p",
            "export": "720p"
        }
        return {
            "model": "grok-imagine/image-to-video",
            "quality": res_map.get(quality, "480p"),
            "input": {
                "image_url": image_url,
                "duration": str(duration)
            }
        }

    def parse_response(self, response: dict):
        """
        Test 3: Grok API 응답 파싱
        """
        result = response.get("result", {})
        return {
            "scenes": result.get("scenes", []),
            "image_prompts": result.get("prompts", [])
        }

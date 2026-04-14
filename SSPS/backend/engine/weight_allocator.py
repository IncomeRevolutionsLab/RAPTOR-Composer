import logging
from typing import Dict

logger = logging.getLogger(__name__)

class WeightAllocator:
    """카테고리 타입에 따라 데이터 소스의 동적 가중치를 할당"""
    
    def __init__(self):
        # [네이버, 올리브영, 다이소] 가중치 매핑
        self.base_weights = {
            "BEAUTY": {"oliveyoung": 0.45, "naver": 0.35, "daiso": 0.20},
            "LOWPRICE": {"daiso": 0.40, "naver": 0.30, "oliveyoung": 0.30},
            "SEASONAL": {"naver": 0.65, "oliveyoung": 0.20, "daiso": 0.15},
            "GENERAL": {"naver": 0.40, "oliveyoung": 0.30, "daiso": 0.30}
        }
        
    def get_weights(self, category_type: str, healthy_sources: list = None) -> Dict[str, float]:
        """
        가중치 반환. 
        만약 특정 소스가 Circuit Breaker에 의해 차단된 경우, 남은 소스들만으로 비율을 재조정(정규화)합니다.
        """
        weights = dict(self.base_weights.get(category_type, self.base_weights["GENERAL"]))
        
        # 특정 소스가 고장났다면? -> 재정규화
        if healthy_sources is not None:
            available_weights = {k: v for k, v in weights.items() if k in healthy_sources}
            total = sum(available_weights.values())
            
            if total > 0:
                weights = {k: round(v / total, 3) for k, v in available_weights.items()}
                # 제외된 소스의 가중치는 0으로 설정
                for k in self.base_weights["GENERAL"].keys():
                    if k not in available_weights:
                        weights[k] = 0.0
            else:
                # 모든 소스가 고장난 최악의 경우 균등 분배로 설정하되 런타임 에러 방지
                weights = {k: 0.0 for k in self.base_weights["GENERAL"].keys()}
                
        logger.info(f"[WeightAllocator] {category_type} 가중치 할당: {weights}")
        return weights

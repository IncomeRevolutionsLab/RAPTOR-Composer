import random
from datetime import datetime

try:
    from dateutil.relativedelta import relativedelta
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

# ─────────────────────────────────────────────────────────────
# 동적 N-Depth 쇼핑 카테고리 트리 (네이버 실구조 기반)
# - subcategories: 하위 분류 딕셔너리 (없으면 리프 노드)
# - q_keyword: 데이터랩 API에 질의할 때 사용할 치환 검색어 (슬래시 등 문제 방지)
# - base: 기본 클릭 지수 (평균치)
# - season: 12개월(최근 1년) 월별 편차값
# ─────────────────────────────────────────────────────────────
NAVER_CATEGORY_TREE = {
    "패션의류": {
        "base": 80, "season": [0,0,0,0,0,0,0,0,0,0,0,0],
        "subcategories": {
            "여성의류": {
                "base": 80, "season": [ 0,  5, 12, 18,-5, 20,-10,-25,-5, 15, 28,  8],
                "subcategories": {
                    "원피스": {"base": 85, "season": [0, 5, 15, 25, 10,-5,-15,-20,-10, 5, 10, -5], "subcategories": {
                        "미니원피스": {"base": 70, "season": [0,0,10,20,10,5,0,0,0,0,0,0]},
                        "롱원피스": {"base": 80, "season": [5,10,5,0,5,5,10,5,10,15,5,5]},
                        "투피스세트": {"base": 65, "season": [0,5,15,10,5,0,0,5,10,5,0,0]}
                    }},
                    "티셔츠": {"base": 75, "season": [0, 2, 8, 15, 25, 30, 20, -5,-10, 0,  5, -5], "subcategories": {
                        "반팔티셔츠": {"base": 80, "season": [-10,-5,10,30,50,40,20,0,-10,-10,-10,-10]},
                        "긴팔티셔츠": {"base": 70, "season": [20,10,0,-10,-20,-20,-10,10,20,20,20,20]},
                        "맨투맨/후드": {"base": 85, "season": [15,10,-5,-15,-15,-15,-5,15,25,30,25,20]}
                    }},
                    "블라우스/셔츠": {"q_keyword": "블라우스", "base": 65, "season": [5,10,25,15,5,-10,-15,-5, 10,20,5,0], "subcategories": {
                        "블라우스": {"base": 75, "season": [5,15,20,10,0,0,-5,10,15,5,5,0]},
                        "셔츠/남방": {"base": 70, "season": [0,5,15,15,10,0,0,10,15,10,5,0]}
                    }},
                    "니트/스웨터": {"q_keyword": "니트", "base": 70, "season": [20,0,-20,-30,-30,-30,-20, 10, 30,40,35,25]},
                    "바지": {"base": 78, "season": [5,10,15,5,10,20,10,-5,-5,10,15,5]},
                    "스커트": {"base": 60, "season": [0,5,10,15,5,10,5,-10,-5,5,10,0]},
                    "코트": {"base": 65, "season": [30,10,-20,-40,-40,-40,-20,10,30,50,45,35]},
                    "점퍼/패딩": {"q_keyword": "패딩", "base": 75, "season": [35,10,-30,-50,-50,-50,-30,10,40,60,50,40]}
                }
            },
            "남성의류": {
                "base": 50, "season": [ 0,  3,  8, 12, -2, 10, -5, -15, -2, 10, 18,  5],
                "subcategories": {
                    "티셔츠": {"base": 70, "season": [0,5,10,20,30,40,30,5,0,0,0,-5], "subcategories": {
                        "반팔티": {"base": 80, "season": [-10,-5,10,30,50,40,20,0,-10,-10,-10,-10]},
                        "긴팔티": {"base": 60, "season": [20,10,0,-10,-20,-20,-10,10,20,20,20,20]},
                        "맨투맨": {"base": 85, "season": [15,10,-5,-15,-15,-15,-5,15,25,30,25,20]}
                    }},
                    "셔츠/남방": {"q_keyword": "남성셔츠", "base": 60, "season": [5,10,20,15,10,-5,-10,5,15,20,10,5]},
                    "니트/스웨터": {"q_keyword": "남성니트", "base": 55, "season": [20,5,-15,-25,-25,-25,-15,5,25,35,30,20]},
                    "바지": {"base": 65, "season": [5,10,15,10,15,25,15,0,-5,5,10,5]},
                    "정장": {"base": 40, "season": [5,15,25,10,0,-10,-15,5,20,25,10,0]},
                    "코트": {"base": 50, "season": [25,5,-25,-35,-35,-35,-15,5,25,40,35,25]}
                }
            },
            "여성언더웨어/잠옷": {
                "q_keyword": "여성잠옷", "base": 30, "season": [5, 5, 2, 0, 5, 10, 15, 5, 2, -2, -5, 0],
                "subcategories": {
                    "브라": {"base": 75, "season": [0,0,5,10,15,20,20,10,0,0,0,0]},
                    "팬티": {"base": 70, "season": [0,0,0,5,5,10,10,5,0,0,0,0]},
                    "브라팬티세트": {"base": 65, "season": [5,5,5,5,10,10,10,5,5,5,5,5]},
                    "잠옷/홈웨어": {"q_keyword": "여성잠옷", "base": 80, "season": [10,0,-5,-10,-5,0,10,15,20,30,25,15], "subcategories": {
                        "파자마/수면잠옷": {"base": 70, "season": [30,20,-10,-20,-20,-20,-10,10,20,30,30,40]},
                        "원피스잠옷": {"base": 60, "season": [0,10,20,20,10,0,0,10,10,5,0,0]}
                    }},
                    "보정속옷": {"base": 40, "season": [5,5,10,15,20,20,15,5,0,0,0,5]},
                    "슬립": {"base": 30, "season": [-5,-5,0,5,10,15,10,0,-5,-10,-10,-5]},
                    "러닝/캐미솔": {"q_keyword": "여성러닝", "base": 35, "season": [-10,-5,5,15,25,30,20,0,-5,-10,-10,-10]}
                }
            },
            "남성언더웨어/잠옷": {
                "q_keyword": "남성잠옷", "base": 25, "season": [2, 2, 0, -2, 2, 5, 8, 2, 0, -5, -8, -2],
                "subcategories": {
                    "팬티": {"base": 75, "season": [0,0,0,5,15,20,15,5,0,0,0,0], "subcategories": {
                        "드로즈": {"base": 80, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
                        "트렁크": {"base": 60, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
                    }},
                    "런닝": {"base": 50, "season": [-10,-5,5,15,25,35,25,5,-5,-10,-10,-10]},
                    "잠옷/홈웨어": {"q_keyword": "남성잠옷", "base": 65, "season": [10,5,0,-5,0,5,15,20,25,30,20,10]},
                    "내복": {"base": 45, "season": [40,20,-20,-40,-40,-40,-20,10,30,50,45,35]}
                }
            }
        }
    },
    "패션잡화": {
        "base": 70, "season": [0,0,0,0,0,0,0,0,0,0,0,0],
        "subcategories": {
            "여성신발": {
                "base": 75, "season": [ 0,  5, 10, 15, 10, 15, 10,  0, -5,  5, 10,  5],
                "subcategories": {
                    "구두": {"base": 65, "season": [5,15,25,10,0,-10,-15,5,20,15,5,0], "subcategories": {
                        "펌프스": {"base": 60, "season": [5,10,20,10,0,0,-5,5,15,10,5,5]},
                        "로퍼": {"base": 75, "season": [10,20,30,10,-5,-10,-5,10,25,20,10,10]},
                        "플랫슈즈": {"base": 65, "season": [0,10,25,20,5,0,-5,10,20,15,5,0]}
                    }},
                    "슬립온": {"base": 50, "season": [5,10,20,25,15,5,0,-5,5,10,5,5]},
                    "운동화": {"base": 85, "season": [0,5,15,20,15,10,5,0,5,15,10,5]},
                    "부츠": {"base": 45, "season": [30,10,-20,-40,-40,-40,-30,0,20,40,35,30]},
                    "샌들": {"base": 55, "season": [-20,-10,10,30,50,60,40,10,-10,-20,-20,-20]}
                }
            },
            "남성신발": {
                "base": 65, "season": [ 0,  3,  8, 12,  8, 10,  5, -3, -5,  5,  5,  2],
                "subcategories": {
                    "구두": {"base": 55, "season": [5,10,20,10,0,-5,-10,5,15,10,5,0], "subcategories": {
                        "로퍼": {"base": 70, "season": [10,15,20,10,0,-5,0,10,20,15,10,10]},
                        "옥스퍼드화": {"base": 60, "season": [5,5,10,5,5,0,0,5,10,5,5,5]}
                    }},
                    "운동화": {"base": 80, "season": [0,5,10,15,10,5,0,0,5,10,5,0]},
                    "샌들/슬리퍼": {"q_keyword": "남성샌들", "base": 40, "season": [-20,-10,5,20,40,50,30,5,-10,-20,-20,-20]},
                    "부츠": {"base": 30, "season": [25,5,-25,-35,-35,-35,-25,0,15,30,25,20]}
                }
            },
            "여성가방": {
                "base": 70, "season": [ 3,  5,  8,  5,  3,  2,  5,  8, 10,  5,  5,  8],
                "subcategories": {
                    "크로스백": {"base": 80, "season": [0,5,10,15,10,5,0,5,10,10,5,0]},
                    "숄더백": {"base": 75, "season": [5,10,15,10,5,0,-5,5,15,10,5,5]},
                    "토트백": {"base": 65, "season": [5,10,10,5,0,-5,-5,5,10,5,5,5]},
                    "백팩": {"base": 60, "season": [10,25,35,10,0,-10,-15,5,20,10,0,5]},
                    "클러치백": {"base": 40, "season": [5,5,10,15,15,10,5,0,5,10,5,5]}
                }
            },
            "남성가방": {
                "base": 50, "season": [ 2,  4,  6,  4,  2,  2,  4,  6,  8,  4,  3,  6],
                "subcategories": {
                    "크로스백": {"base": 70, "season": [0,5,10,15,10,5,0,5,10,5,0,0]},
                    "백팩": {"base": 80, "season": [15,30,40,15,5,-5,-10,10,20,15,5,10]},
                    "브리프케이스": {"base": 55, "season": [5,10,15,5,0,-5,-5,5,15,10,5,5]},
                    "클러치백": {"base": 45, "season": [5,5,10,15,20,15,5,0,5,10,5,5]}
                }
            },
            "지갑": {
                "base": 55, "season": [ 0,  2,  5,  5,  2,  0,  2,  4,  6,  0,  0,  4],
                "subcategories": {
                    "여성지갑": {"base": 70, "season": [5,10,15,5,0,-5,0,5,10,5,0,5]},
                    "남성지갑": {"base": 65, "season": [5,10,10,5,0,-5,0,5,10,5,0,5]}
                }
            },
            "모자": {
                "base": 45, "season": [ -5, -2,  5, 15, 20, 15, 10,  0, -5,-10, -8, -6],
                "subcategories": {
                    "캡모자": {"base": 75, "season": [0,5,15,20,15,10,5,0,5,10,5,0], "subcategories": {
                        "볼캡": {"base": 80, "season": [0,5,10,15,10,5,0,0,5,10,5,0]},
                        "스냅백": {"base": 40, "season": [0,0,5,10,5,0,0,0,5,5,0,0]}
                    }},
                    "비니": {"base": 40, "season": [30,15,-15,-30,-30,-30,-20,5,20,35,30,25]},
                    "페도라": {"base": 20, "season": [5,10,15,20,15,10,5,0,5,5,0,0]},
                    "썬캡": {"base": 35, "season": [-20,-10,10,30,50,60,40,10,-10,-20,-20,-20]},
                    "베레모": {"base": 25, "season": [10,5,-10,-20,-20,-20,-10,0,15,20,15,10]}
                }
            }
        }
    },
    "화장품/미용": {
        "base": 75, "season": [0,0,0,0,0,0,0,0,0,0,0,0],
        "subcategories": {
            "스킨케어": {"base": 82, "season": [ 3,  5,  8,  6,  8,  5,  6, 10,  8, -2,  0, 10], "subcategories": {
                "스킨/토너": {"base": 70, "season": [5,5,5,5,5,5,5,5,5,5,5,5]},
                "로션/에멀젼": {"base": 75, "season": [5,10,15,5,0,-5,0,5,15,10,5,5]},
                "에센스/세럼": {"base": 80, "season": [0,0,5,10,10,5,5,10,15,10,0,0]},
                "크림": {"base": 85, "season": [20,10,0,-10,-20,-20,-10,10,30,40,30,20]}
            }},
            "클렌징": {"base": 75, "season": [5,5,5,5,5,5,5,5,5,5,5,5], "subcategories": {
                "클렌징폼": {"base": 80, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
                "클렌징오일": {"base": 72, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
                "클렌징워터": {"base": 68, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
            }},
            "마스크/팩": {"base": 80, "season": [10,10,5,5,5,10,15,15,10,10,10,10], "subcategories": {
                "마스크시트": {"base": 85, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
                "모델링팩": {"base": 70, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
                "워시오프팩": {"base": 65, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
            }},
            "선케어": {"base": 62, "season": [-5,  0,  5, 10, 15, 18, 12,  5, -3, -8,-10, -8], "subcategories": {
                "선크림": {"base": 80, "season": [-10,0,10,20,30,40,30,10,-10,-20,-20,-10]},
                "선스틱": {"base": 60, "season": [-15,-5,5,25,35,45,35,5,-15,-25,-25,-15]},
                "선쿠션": {"base": 50, "season": [-10,-5,5,15,20,25,20,10,0,-10,-10,-10]}
            }},
            "베이스메이크업": {"base": 58, "season": [ 2,  4,  6,  5,  7,  4,  5,  8,  6, -1,  2, 12], "subcategories": {
                "파운데이션": {"base": 70, "season": [10,15,10,5,0,-5,-5,5,10,15,10,10]},
                "비비크림": {"base": 50, "season": [5,5,5,5,5,5,5,5,5,5,5,5]},
                "쿠션파운데이션": {"base": 85, "season": [5,10,15,10,5,5,10,15,20,15,5,5]}
            }},
            "색조메이크업": {"base": 55, "season": [ 5, 10, 15, 10,  5,  0,  5, 10, 15,  5, 10,  5], "subcategories": {
                "아이섀도우": {"base": 65, "season": [15,20,10,0,-10,-10,0,15,25,20,15,15]},
                "립스틱/립틴트": {"base": 80, "season": [10,15,20,15,5,5,10,20,25,20,10,10]},
                "블러셔": {"base": 60, "season": [5,15,25,20,5,0,0,10,15,10,5,5]}
            }},
            "메이크업소품": {
                "base": 50, "season": [0,0,0,0,0,0,0,0,0,0,0,0],
                "q_keyword": "메이컵 툴,메이크업툴,화장소품,브러쉬,퍼프,뷰티툴",
                "subcategories": {
                    "메이크업브러쉬": {"base": 60, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
                    "화장솜/퍼프": {"base": 55, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
                    "아이툴/눈화장": {"base": 50, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
                }
            }
        }
    },
    "디지털/가전": {
        "base": 72, "season": [0,0,0,0,0,0,0,0,0,0,0,0],
        "subcategories": {
            "스마트폰/액세서리": {"q_keyword": "스마트폰", "base": 80, "season": [-2,  0,  3,  5,  6,  8, 10,  6, 25,  0, -2, -3], "subcategories": {
                "스마트폰": {"base": 85, "season": [0,0,5,5,5,5,10,20,30,10,0,0], "subcategories": {
                    "자급제폰": {"base": 80, "season": [0,0,0,5,5,5,5,10,15,5,0,0]},
                    "공기계": {"base": 50, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
                }},
                "휴대폰케이스": {"base": 75, "season": [5,10,15,10,5,5,10,15,20,10,5,5]},
                "보호필름": {"base": 70, "season": [5,5,5,5,5,5,5,5,5,5,5,5]},
                "보조배터리": {"base": 60, "season": [5,5,10,15,15,10,5,0,5,10,5,5]}
            }},
            "노트북/PC": {"base": 70, "season": [ 5, 20, 30, 10,  5, -5, -5,  5, 15, 10,  5, 10], "subcategories": {
                "노트북": {"base": 80, "season": [10,30,40,15,0,-5,-5,5,15,10,5,10]},
                "태블릿PC": {"base": 75, "season": [5,15,20,10,5,0,5,10,15,10,5,5]},
                "데스크탑": {"base": 60, "season": [5,10,5,0,0,0,0,5,5,5,5,5]},
                "모니터": {"base": 65, "season": [5,10,5,0,0,0,0,5,5,5,5,5]}
            }},
            "음향가전": {"base": 60, "season": [ 0,  5,  5,  5,  0,  0,  5,  5, 10,  5,  0,  5], "subcategories": {
                "블루투스이어폰": {"base": 80, "season": [5,10,15,10,5,5,10,15,20,10,5,5]},
                "헤드폰": {"base": 65, "season": [15,10,0,-10,-20,-20,-10,5,20,25,20,15]},
                "블루투스스피커": {"base": 55, "season": [5,10,15,20,15,10,5,0,5,10,10,5]}
            }},
            "계절가전": {"base": 45, "season": [ -5, 10, 30, 50, 40, -10, -20, 10, 30, 40, 20, 0], "subcategories": {
                "에어컨": {"base": 50, "season": [-30,-20,-10,20,50,80,60,10,-10,-20,-30,-30]},
                "선풍기": {"base": 60, "season": [-40,-30,-10,20,60,90,70,10,-20,-30,-40,-40]},
                "가습기": {"base": 40, "season": [30,10,-10,-30,-40,-40,-30,0,20,50,40,30]},
                "전기히터": {"base": 30, "season": [40,20,-20,-30,-30,-30,-20,10,30,60,50,40]}
            }}
        }
    },
    "가구/인테리어": {"base": 65, "season": [0]*12, "subcategories": {
        "침실가구": {"base": 65, "season": [ 0,  3,  8, 10,  8,  5,  5,  6,  8, -5, -5,  0], "subcategories": {
            "침대/매트리스": {"base": 80, "season": [5,10,15,20,10,5,0,5,10,5,0,5]},
            "화장대": {"base": 60, "season": [5,5,10,5,0,0,0,5,10,5,0,0]},
            "서랍장": {"base": 70, "season": [5,10,10,5,0,0,0,5,10,5,0,5]}
        }},
        "거실가구": {"base": 58, "season": [ 0,  3,  7,  9,  7,  4,  5,  6,  7, -4, -4,  0], "subcategories": {
            "소파": {"base": 85, "season": [5,10,15,10,5,0,0,5,10,5,0,5]},
            "TV거실장": {"base": 65, "season": [0,5,5,5,0,0,0,5,5,0,0,0]},
            "거실테이블": {"base": 60, "season": [0,5,10,5,0,0,0,5,10,5,0,0]}
        }},
        "주방가구": {"base": 50, "season": [ 0,  2,  5,  6,  5,  3,  4,  5,  6, -3, -3,  0], "subcategories": {
            "식탁/의자": {"base": 75, "season": [5,10,15,10,5,0,0,5,10,5,0,5]},
            "주방수납장": {"base": 60, "season": [0,5,5,5,0,0,0,0,5,0,0,0]},
            "렌지대": {"base": 55, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
        }},
        "인테리어소품": {"base": 55, "season": [ 0,  2,  6,  8,  6,  4,  4,  5,  5, -4, -4,  2], "subcategories": {
            "조명/스탠드": {"base": 65, "season": [10,5,0,-5,0,5,10,15,20,15,10,10]},
            "러그/카페트": {"base": 60, "season": [25,10,-10,-20,-20,-20,-10,10,25,35,30,25]},
            "커튼/블라인드": {"base": 70, "season": [5,10,15,20,10,5,0,5,10,10,5,5]},
            "쿠션/방석": {"base": 50, "season": [10,5,0,0,0,0,0,5,10,15,10,10]}
        }}
    }},
    "출산/육아": {"base": 60, "season": [0]*12, "subcategories": {
        "유아동의류": {"base": 70, "season": [ 2,  4,  6,  8,  6,  4,  6, 10, 12, -2, -3,  2], "subcategories": {
            "여아의류": {"base": 75, "season": [5,10,15,20,10,5,0,5,15,10,5,5]},
            "남아의류": {"base": 75, "season": [5,10,15,20,10,5,0,5,15,10,5,5]},
            "공용의류": {"base": 60, "season": [5,5,10,10,5,5,5,5,10,5,5,5]}
        }},
        "유아동신발/잡화": {"q_keyword": "아동신발", "base": 60, "season": [-2,  0,  4,  8, 10,  8,  4,  0, -2, -5, -4,  0], "subcategories": {
            "운동화": {"base": 70, "season": [0,5,15,20,10,5,0,0,5,10,5,0]},
            "구두": {"base": 50, "season": [5,10,15,10,0,0,0,5,10,10,5,5]},
            "부츠": {"base": 40, "season": [25,5,-15,-25,-25,-25,-15,5,20,30,25,25]}
        }},
        "장난감/완구": {"base": 65, "season": [ 0,  5, 15,  5,  0, -5,  0,  5, 10, 20, 30, 15], "subcategories": {
            "로봇/작동완구": {"base": 70, "season": [5,10,25,5,0,0,0,10,20,30,40,20]},
            "인형": {"base": 65, "season": [5,10,20,5,0,0,0,5,10,20,35,15]},
            "블록놀이": {"base": 55, "season": [5,10,15,5,5,5,5,10,10,15,25,10]}
        }},
        "분유/기저귀": {"base": 75, "season": [ 0,  1,  2,  2,  2,  2,  2,  3,  3,  1,  1,  1], "subcategories": {
            "국내조제분유": {"base": 70, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
            "수입조제분유": {"base": 60, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
            "밴드형기저귀": {"base": 80, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
            "팬티형기저귀": {"base": 85, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
        }}
    }},
    "식품": {"base": 75, "season": [0]*12, "subcategories": {
        "건강식품": {"base": 85, "season": [ 10, 15, 20, 10,  5, -5,  5, 20, 25, 10,  5, 15], "subcategories": {
            "영양제": {"base": 80, "season": [ 5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5], "subcategories": {
                "종합비타민": {"base": 75, "season": [5,5,5,5,5,5,5,5,5,5,5,5]},
                "오메가3": {"base": 70, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
            }},
            "홍삼": {"base": 65, "season": [ 15, 20, 10, 10, -5, -5, 15, 30, 10, -5, -5, 15]},
            "다이어트식품": {"base": 75, "season": [-5, -5,  5, 15, 25, 30, 20, -5,-10,-10, -5, -5]},
            "비타민/미네랄": {"base": 70, "season": [ 2,  2,  5,  5,  2,  2,  5,  5,  5,  2,  2,  2]}
        }},
        "신선식품": {"base": 72, "season": [ -3,  0,  5, 10, 12,  8,  5,  3,  0, -2, -3, -2], "subcategories": {
            "과일": {"base": 60, "season": [ 0,  5, 15, 20, 25, 20, 10, 15, 20, 10,  5,  0]},
            "채소": {"base": 65, "season": [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0]},
            "정육/계란": {"base": 80, "season": [ 5, 10,  0, -5, -5, -5,  5, 10,  5, -5, -5,  5]},
            "수산물": {"base": 60, "season": [ 10,  5, -5,-10,-15,-15,-10, -5,  5, 15, 20, 15]}
        }},
        "가공식품": {"base": 80, "season": [ 0,  2,  3,  3,  2,  2,  3,  4,  5,  5,  5,  8], "subcategories": {
            "과자/베이커리": {"base": 70, "season": [ 2,  4,  5,  5,  5,  5,  5,  5,  5,  5,  5,  2]},
            "면류": {"base": 65, "season": [ 10,  5,  0, -5, -5, -5,  5, 10,  5, -5,  5, 10]},
            "간편식/밀키트": {"base": 85, "season": [ 5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5]}
        }},
        "음료": {"base": 65, "season": [ -5,  0, 10, 25, 35, 25, 10,  0, -5, -5, -5, -5], "subcategories": {
            "생수/탄산수": {"base": 70, "season": [ -5, -5,  5, 15, 25, 20, 10,  0, -5, -5, -5, -5]},
            "커피": {"base": 85, "season": [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0]},
            "차/전통음료": {"base": 55, "season": [ 15, 10,  0,-10,-10,-10,  0, 10,  5, 10, 15, 15]}
        }}
    }},
    "스포츠/레저": {"base": 60, "season": [0]*12, "subcategories": {
        "스포츠의류": {"base": 72, "season": [ 0,  5, 15, 20, 15,  5, -5, -5,  0,  5,  5,  0], "subcategories": {
            "트레이닝복": {"base": 80, "season": [5,10,15,20,10,5,0,5,10,15,10,5]},
            "골프의류": {"base": 65, "season": [-10,10,30,40,20,0,-10,20,40,30,0,-10]},
            "수영복": {"base": 55, "season": [-20,-10,10,30,50,60,40,10,-10,-20,-20,-20]}
        }},
        "스포츠화": {"base": 65, "season": [ 0,  5, 10, 15, 10,  5,  0,  0,  5,  5,  0,  0], "subcategories": {
            "런닝화": {"base": 75, "season": [0,10,20,25,15,5,0,5,15,10,0,0]},
            "축구화": {"base": 50, "season": [0,5,15,10,5,0,0,5,15,10,0,0]},
            "등산화": {"base": 55, "season": [0,10,25,20,0,-10,-10,15,30,20,5,0]}
        }},
        "헬스/요가용품": {"q_keyword": "요가복", "base": 58, "season": [ 5,  5, 10, 15, 15, 10,  5,  5,  5,  5,  5,  5], "subcategories": {
            "요가매트": {"base": 65, "season": [5,5,10,15,10,5,5,5,5,5,5,5]},
            "폼롤러": {"base": 55, "season": [0,5,5,5,5,5,5,5,5,5,5,0]}
        }},
        "캠핑/아웃도어": {"q_keyword": "캠핑용품", "base": 65, "season": [ -5,  5, 20, 35, 40, 25, 10, -5,-10,-10,-10, -5], "subcategories": {
            "텐트/타프": {"base": 70, "season": [-10,5,25,40,45,30,10,-5,-15,-20,-15,-10]},
            "캠핑가구": {"base": 65, "season": [-5,5,20,30,35,25,15,0,-5,-10,-10,-5]},
            "캠핑매트": {"base": 55, "season": [0,5,15,20,25,20,10,5,0,0,0,0]}
        }}
    }},
    "생활/건강": {"base": 65, "season": [0]*12, "subcategories": {
        "청소용품": {"base": 68, "season": [ 2,  3,  5,  6,  5,  4,  4,  4,  4,  3,  3,  3], "subcategories": {
            "진공청소기": {"base": 75, "season": [0,5,5,5,0,0,0,0,5,5,0,0]},
            "물걸레청소기": {"base": 65, "season": [0,5,10,5,0,0,0,0,5,5,0,0]},
            "청소포": {"base": 60, "season": [5,5,5,5,5,5,5,5,5,5,5,5]}
        }},
        "세탁용품": {"base": 65, "season": [ 2,  3,  5,  5,  4,  4,  4,  4,  4,  3,  3,  3], "subcategories": {
            "세탁세제": {"base": 75, "season": [0,0,5,5,5,5,5,0,0,0,0,0]},
            "섬유유연제": {"base": 70, "season": [0,0,5,5,5,5,5,0,0,0,0,0]},
            "건조대": {"base": 60, "season": [5,5,10,15,10,5,5,5,5,5,5,5]}
        }},
        "욕실용품": {"base": 55, "season": [ 0,  2,  4,  4,  3,  3,  3,  3,  3,  2,  2,  2], "subcategories": {
            "수건/타월": {"base": 70, "season": [0,0,0,0,5,5,5,0,0,0,0,0]},
            "샤워기": {"base": 60, "season": [0,0,0,5,10,10,10,5,0,0,0,0]},
            "욕실수납장": {"base": 50, "season": [0,0,5,5,0,0,0,0,0,0,0,0]}
        }},
        "생활잡화": {"base": 60, "season": [ 0,  2,  3,  4,  3,  3,  3,  4,  4,  3,  3,  2], "subcategories": {
            "마스크": {"base": 85, "season": [10,15,30,-10,-20,-30,-20,10,15,30,20,15]},
            "우산/양산": {"base": 50, "season": [-10,-10,0,10,20,30,50,10,0,-10,-10,-10]}
        }}
    }},
    "여가/생활편의": {"base": 50, "season": [0]*12, "subcategories": {
        "여행용품": {"base": 60, "season": [ -5, -5,  5, 20, 30, 25, 10, -5,-10, -5,  0, -5], "subcategories": {
            "캐리어": {"base": 70, "season": [-10,-5,10,30,40,30,10,-5,-15,-10,0,-5]},
            "여행용파우치": {"base": 55, "season": [-5,0,5,20,25,20,5,-5,-10,-5,0,0]},
            "여권케이스": {"base": 45, "season": [-5,0,10,15,20,15,5,0,-5,0,5,0]}
        }},
        "반려동물": {"base": 75, "season": [ 2,  3,  4,  5,  5,  5,  5,  5,  5,  4,  4,  3], "subcategories": {
            "강아지사료": {"base": 80, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
            "고양이사료": {"base": 80, "season": [0,0,0,0,0,0,0,0,0,0,0,0]},
            "강아지간식": {"base": 70, "season": [0,5,5,5,5,5,5,5,5,5,0,0]},
            "배변용품": {"base": 65, "season": [0,0,0,0,0,0,0,0,0,0,0,0]}
        }},
        "자동차기기/용품": {"q_keyword": "자동차용품", "base": 55, "season": [ 0,  1,  3,  5,  4,  3,  3,  2,  2,  1,  1,  0], "subcategories": {
            "블랙박스": {"base": 65, "season": [0,0,5,5,0,0,0,0,5,5,0,0]},
            "세차용품": {"base": 60, "season": [-10,0,15,20,15,10,0,10,15,5,-5,-10]},
            "방향제": {"base": 55, "season": [5,5,10,10,5,5,5,5,10,10,5,5]}
        }},
        "문구/오피스": {"q_keyword": "문구류", "base": 45, "season": [ 5, 20, 30, 10,  0, -5, -5,  5, 15, 10,  5,  5], "subcategories": {
            "필기구": {"base": 60, "season": [5,25,35,5,-5,-10,-10,10,20,5,0,0]},
            "다이어리/플래너": {"base": 50, "season": [20,10,-10,-20,-20,-20,-20,0,10,30,60,80]}
        }}
    }}
}

TOP_LEVEL_CATEGORIES = list(NAVER_CATEGORY_TREE.keys())

def get_month_labels(n=12):
    """최근 n개월 라벨 생성 (yy-mm 형식)"""
    now = datetime.now()
    if HAS_DATEUTIL:
        return [(now - relativedelta(months=i)).strftime("%y-%m") for i in range(n-1, -1, -1)]
    labels = []
    year, month = now.year, now.month
    for _ in range(n-1, -1, -1):
        labels.append(f"{str(year)[2:]}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return labels[::-1]

class CategoryManager:
    """N-Depth 네이버 쇼핑 카테고리 트리 관리 및 클릭 트렌드 제공"""

    def __init__(self):
        self.default_fallback = {"기본분류": ["베스트셀러", "트렌드상품", "신상품"]}

    def get_node_by_path(self, path: list) -> dict:
        """
        N-Depth 경로에 해당하는 카테고리 노드 반환
        """
        current = NAVER_CATEGORY_TREE
        for p in path:
            if not isinstance(current, dict):
                return {}
            # current is a dict of subcategories or dict containing 'subcategories'
            if "subcategories" in current:
                current = current["subcategories"]
            
            if p in current:
                current = current[p]
            else:
                return {}
        return current

    def get_depth_trend_analysis(self, path: list) -> dict:
        """
        주어진 카테고리 경로의 하위 분류들에 대한 최고 클릭량=100 기준 상대 지수 트렌드 분석.
        하위 분류가 없으면 빈 딕셔너리를 반환하여 리프 노드임을 알림.
        """
        node = self.get_node_by_path(path)
        if not node or "subcategories" not in node:
            return {} # 리프 노드
        
        subcats = node["subcategories"]
        months = get_month_labels(12)
        
        all_series = []
        global_max = 0

        # 1차 스캔: 각 카테고리의 12개월 점수 생성 및 절대 최대값 추적
        raw_series_data = []
        for name, info in subcats.items():
            base = info.get("base", 50)
            season = info.get("season", [0]*12)
            pts = []
            for j in range(12):
                sj = season[j] if j < len(season) else 0
                val = base + sj + random.randint(-1, 1)
                if val < 0: val = 0
                pts.append(val)
                if val > global_max:
                    global_max = val
            raw_series_data.append({"name": name, "pts": pts})

        # 2차 스캔: 최고 클릭량을 100으로 기준하여 상대 지수로 변환 (데이터랩 작동 방식 동일 적용)
        if global_max == 0: global_max = 1
        
        for item in raw_series_data:
            normalized_pts = [round((v / global_max) * 100, 1) for v in item["pts"]]
            avg = round(sum(normalized_pts) / 12, 1)
            q_keyword = subcats[item["name"]].get("q_keyword", item["name"])
            all_series.append({
                "name": item["name"],
                "q_keyword": q_keyword,
                "data": normalized_pts,
                "avg_score": avg
            })

        # 연평균 상대지수 기준 내림차순 정렬 → TOP 3
        all_series.sort(key=lambda x: -x["avg_score"])
        top3 = all_series[:3]

        return {
            "is_leaf": False,
            "categories": months,
            "series": [{"name": s["name"], "data": s["data"]} for s in top3],
            "ranking": [
                {"rank": i + 1, "name": s["name"], "avg_score": s["avg_score"], "q_keyword": s["q_keyword"]}
                for i, s in enumerate(top3)
            ]
        }

    def get_path_from_keyword(self, keyword: str, items: list = None) -> list:
        """
        [근본 해결책 - Single Pipeline Routing]
        3. 최후의 보루 (기본값)
        """
        def normalize(s):
            if not s: return ""
            # 공백, 하이픈, 슬래시 제거 및 소문자화
            return "".join(s.lower().split()).replace("-","").replace("/","").replace("_","")

        kw_norm = normalize(keyword)
        best_path = []
        is_exact_match = False

        def search_tree(tree, current_path):
            nonlocal best_path, is_exact_match
            if not isinstance(tree, dict): return
            
            for k, info in tree.items():
                if isinstance(info, dict):
                    node_key = k
                    node_norm = normalize(k)
                    aliases = [normalize(a) for a in info.get("q_keyword", "").split(",")] if "q_keyword" in info else []
                    
                    # 1. 정규화된 이름이나 별칭이 정확히 일치하는 경우 (Exact Match)
                    if kw_norm == node_norm or kw_norm in aliases:
                        best_path = current_path + [k]
                        is_exact_match = True
                        # 일치하는 경우에는 하위 탐색을 계속하여 가장 깊은 노드를 찾거나 중단 가능
                        # 여기서는 일단 일치 수준이 높은 것을 선호
                        
                    # 2. 부분 일치 (이미 정확한 일치가 발견되지 않은 경우에만 예비용)
                    elif not is_exact_match and len(kw_norm) >= 2:
                        if kw_norm in node_norm or node_norm in kw_norm:
                            if not best_path:
                                best_path = current_path + [k]
                            
                    if "subcategories" in info:
                        search_tree(info["subcategories"], current_path + [k])
                        
        search_tree(NAVER_CATEGORY_TREE, [])
        
        # 1관문: 트리에서 경로 기반 매치를 찾은 경우
        if best_path:
            # [v2.35] 정확한 카테고리 일치 여부를 객체 속성에 임시 저장하거나 
            # 외부에서 알 수 있도록 추가 정보를 리턴함 (get_node_info 등으로 확장 가능)
            setattr(self, "_last_match_is_exact", is_exact_match)
            return best_path
            
        # 2관문: 트리에 완전히 없는 단어 (예: 두바이 초콜릿) -> 쇼핑 검색 다수결 추론
        if items:
            cat_counter = {}
            for item in items:
                c1, c2, c3, c4 = item.get("category1"), item.get("category2"), item.get("category3"), item.get("category4")
                if c1 and c2:
                    pathStr = f"{c1}>{c2}"
                    if c3: pathStr += f">{c3}"
                    if c4: pathStr += f">{c4}"
                    cat_counter[pathStr] = cat_counter.get(pathStr, 0) + 1
            if cat_counter:
                best_str = max(cat_counter.items(), key=lambda x: x[1])[0]
                best_path = best_str.split(">")
                # 반환된 경로가 우리 10대 트리에 있는 1-depth인지 검증
                if best_path[0] in NAVER_CATEGORY_TREE:
                    setattr(self, "_last_match_is_exact", False) # 다수결 추론은 카테고리 직접 검색이 아님
                    return best_path

        # 3관문: 예외 및 하위 호환성 폴백
        fallback_rules = {
            "원피스": ["패션의류", "여성의류", "원피스"],
            "화장품": ["화장품/미용", "스킨케어"],
            "가방": ["패션잡화", "여성가방"],
            "구두": ["패션잡화", "여성신발"],
        }
        for k, p in fallback_rules.items():
            if k in kw_norm: 
                setattr(self, "_last_match_is_exact", True)
                return p
            
        setattr(self, "_last_match_is_exact", False)
        return ["생활/건강", "생활잡화"]
        
    # 하위 호환을 위해 남겨두되 사실상 N-Depth 전용으로 전환되므로 거의 미사용
    def match_from_keyword(self, keyword: str) -> dict:
        path = self.get_path_from_keyword(keyword, [])
        is_leaf = self.get_node_by_path(path) == {}
        return {
            "depth1": path[0] if len(path) > 0 else None,
            "depth2": path[1] if len(path) > 1 else None,
            "depth3": path[2] if len(path) > 2 else None,
            "depth4_list": [],
            "has_subcat": not is_leaf,
            "is_leaf_category": is_leaf
        }

    def build_hierarchy_from_items(self, items: list, query: str) -> dict:
        path = self.get_path_from_keyword(query, items)
        return self.match_from_keyword(path[-1]) # 하위 호환


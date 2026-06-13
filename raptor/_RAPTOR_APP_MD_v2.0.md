# 📐 RAPTOR V2.1 시스템 설계서 (MD v2.0)
**[9단계 팩트 기반 워크플로우 & 플랫폼 컴플라이언스 대응 버전]**

## 1. 아키텍처 개요
본 시스템은 사용자의 입력 데이터(Fact)를 기반으로 기획안을 생성하고, 사용자의 명시적 결정을 거쳐 최종 숏폼 영상을 합성하는 'Human-in-the-loop'형 컴포저이다.

## 2. 핵심 9단계 워크플로우 (User Journey)
1. **[Step 1] Input & Options:** 상품 링크/팩트 입력 + **[영상 내 쇼핑 태그 삽입 여부]** 선택 (Yes/No).
2. **[Step 2] Auto Scrape:** Apify/Zyte API를 활용한 링크 기반 데이터(이미지, 상품명, 리뷰) 자동 수집.
3. **[Step 3] AI Fact Analysis:** 수집된 데이터를 분석하여 핵심 소구점(Pain Point & Strengths) 도출.
4. **[Step 4] Pattern Selection:** AI가 추천하는 3가지 패턴 중 사용자가 하나를 직접 선택하여 기획 방향 확정.
5. **[Step 5] Asset Planning:** 선택된 패턴에 따른 스크립트, 제목, 해시태그, Grok 전용 프롬프트 생성.
6. **[Step 6] Grok Video Generation:** Image-to-Video API를 호출하여 씬별 고화질 영상 조각 생성 (일관성 유지).
7. **[Step 7] Browser-Side Composition:** 무거운 서버 FFmpeg 대신 브라우저 캔버스 기반으로 자막 및 (옵션 시) 태그 합성.
8. **[Step 8] Final Export:** `{상품명}.mp4` 파일명으로 고화질 최종 영상 다운로드.
9. **[Step 9] Social Package Output:** 플랫폼 전략(Native/Overlay)에 맞춘 업로드 메타데이터 제공.

## 3. 플랫폼 컴플라이언스 및 렌더링 분기
- **Native 모드 (Tag: No):** 
  - 플랫폼 고유 쇼핑 기능을 사용하는 경우. 영상에는 자막만 합성하고 태그 그래픽은 제외.
  - Upload Package에서 댓글/설명란용 링크 CTA 텍스트를 강력하게 생성.
- **Overlay 모드 (Tag: Yes):** 
  - 일반 커뮤니티/바이럴용. 타임라인 지정 시점에 시각적인 상품 카드 그래픽을 물리적으로 합성.

## 4. 데이터 규격 (API Contract)
- **POST `/api/scrape`:** `url` -> `product_info`
- **POST `/api/analyze`:** `product_info` -> `analysis_report`
- **POST `/api/generate-assets`:** `selected_pattern`, `tag_option` -> `full_plan`
- **GET `/api/video-stream`:** Grok 생성 영상 조각 스트리밍

## 5. 보안 및 성능 원칙
- **BYOK:** `X-BYOK-Grok` 헤더를 통한 사용자 키 전달.
- **Lightweight:** 서버 부하를 줄이기 위해 브라우저 단의 렌더링 엔진 활용.

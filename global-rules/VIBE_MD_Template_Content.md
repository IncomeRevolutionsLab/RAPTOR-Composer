🧠 VIBE MD 템플릿 (콘텐츠/서비스 중심)
Model Design — 프롬프트·흐름·모듈 설계 / 모듈 풀 연계
0. Step-by-Step 사용자 워크플로우 (User Workflow)
- **필수:** 기술 설계 전, 사용자가 첫 입력을 시작하여 최종 결과를 얻기까지의 모든 과정을 상세히 명시한다 (Journey Map).
- **기술 매핑:** 각 단계별로 사용되는 기술 모듈(API, Store, UI)을 일대일로 매핑하여 설계의 구체성을 확보한다.
1. 생성 파이프라인 설계
단계: 아이디어 → 리서치 → 초안 → 편집 → SEO/메타 → 썸네일 → 게시 → 배포 → 리포트
각 단계 입력/출력 규격(간단한 키:값 스키마)
예)
입력(아이디어): {topic, audience, goal}
출력(초안): {title, outline[], body_md}
출력(메타): {seo_title, meta_desc, tags[]}
출력(썸네일): {prompt_text, alt_text}
2. 프롬프트 세트(역할 프롬프트 포함)
시스템/역할: "너는 브랜드 일관성을 지키는 콘텐츠 에디터다"
단계별 프롬프트 (간결형/확장형 2종):
초안 생성 / 제목·썸네일 / SEO / 요약 / 스크립트 변환(쇼츠)
3. 품질 기준(QoS) & 자동 리뷰 규칙
금지 표현, 중복 문장 탐지, 팩트 체크 요청 지점
톤·포맷 체크리스트(표/리스트 단독 금지 → 서술 추가)
4. 모듈 풀 설계(재사용 모듈 정의)
모듈 ID: NAME, 목적, 입력, 출력, 의존 모듈, 버전
예시:
TITLE-GEN v1.1: 입력 {topic, tone} → 출력 {title10[]}
SEO-KEYMAP v1.2: 입력 {topic} → 출력 {keywords[], clusters[]}
THUMB-PROMPT v1.0: 입력 {topic, mood} → 출력 {prompt_text}
UTUBE-META v1.0: 입력 {title, keywords[]} → 출력 {description, hashtags[]}
REPORT-AUTO v1.0: 입력 {post_url, metrics_api_key} → 출력 {kpi_table_md}
5. 자동화 연결(오케스트레이션)
Make/Zapier 플로우: 트리거→액션 시퀀스 표기
Replit/Apps Script: 어떤 스크립트가 어떤 API를 호출하는지(고수준 설명)
6. 데이터 보관·동기화
문서 저장소(Drive/Notion) 구조
파일 네이밍: [YYYYMMDD]_[CHANNEL]_[TOPIC]_vX.Y.md
버전 태깅: Main V1.2와 PLM 버전 연동(예: PLM-01 v1.2.3)
7. 보안·정책 준수
저작권·인용 규칙, 개인정보 비포함 원칙
플랫폼 커뮤니티 가이드 준수
--------------------------------------------------------------------------------
🧪 샘플 출력 스키마 (마크다운)
# {title}
{intro_paragraph}

## 핵심 요약
- 포인트 1
- 포인트 2

## 본문
...

## FAQ
- Q: 
  A: 

## 결론 & CTA
...
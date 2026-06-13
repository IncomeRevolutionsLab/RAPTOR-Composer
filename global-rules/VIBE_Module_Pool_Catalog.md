🧰 VIBE Module Pool 카탈로그 (공통 재사용 모듈)
목적: 콘텐츠/서비스 중심 프로젝트에서 반복 재사용되는 기능을 모듈화하여 효율 극대화
카탈로그 스키마
ID / 이름 / 버전
목적
입력 → 출력 계약(Contract)
의존 모듈
사용 예
상태: 실험/베타/정식
변경 로그
--------------------------------------------------------------------------------
1) TITLE-GEN — 제목 생성기
ID/버전: TITLE-GEN v1.1
목적: 주제·톤 기반 다변량 제목 10개 생성
입력→출력: {topic, tone} → {title10[]}
의존: SEO-KEYMAP(선택)
사용 예: 블로그/유튜브 공통
상태: 정식
변경 로그: v1.1 — 의도 반영률 개선
2) SEO-KEYMAP — 키워드 맵퍼
ID/버전: SEO-KEYMAP v1.2
목적: 핵심 키워드/클러스터 생성 및 내부링크 제안
입력→출력: {topic} → {keywords[], clusters[], internal_linking[]}
상태: 정식
3) THUMB-PROMPT — 썸네일 프롬프트 빌더
ID/버전: THUMB-PROMPT v1.0
목적: 썸네일 문구/구도/포즈 지시어 생성
입력→출력: {topic, mood, brand} → {prompt_text, alt_text}
상태: 베타
4) UTUBE-META — 유튜브 메타 생성기
ID/버전: UTUBE-META v1.0
목적: 설명/해시태그/챕터 생성
입력→출력: {title, keywords[]} → {description, hashtags[], chapters[]}
상태: 정식
5) REPORT-AUTO — KPI 리포트 빌더
ID/버전: REPORT-AUTO v1.0
목적: 게시물 URL 기반 KPI 요약 리포트 생성
입력→출력: {post_url, metrics_api} → {kpi_table_md, insight}
상태: 베타
--------------------------------------------------------------------------------
모듈 등록 양식(추가 시 사용)
- ID/버전: 
- 이름:
- 목적:
- 입력→출력:
- 의존 모듈:
- 사용 예:
- 상태(실험/베타/정식):
- 변경 로그:
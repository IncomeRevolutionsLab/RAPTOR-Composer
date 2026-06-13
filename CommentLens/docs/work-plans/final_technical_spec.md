# 최종 기술 명세서 (Final Technical Specification)

## 1. 프로젝트 개요
특정 유튜브 URL의 댓글 및 대댓글을 최대 20만 건까지 수집하는 로컬 Python 도구.

## 2. 아키텍처 원칙 (사용자 지침 반영)
- **단일 API 키 정책**: 복잡한 키 로테이션 없이 단일 API 키만 사용하며, 할당량(10,000 units) 관리에 집중함.
- **강력한 결함 허용(Fault Tolerance)**: API 호출 실패(특히 403 Quota Exceeded) 발생 시 즉시 `checkpoint.json`에 `page_token`을 저장하고 프로세스를 안전하게 종료.
- **데이터 이원화 저장**:
    - **Raw Data**: 20,000건 단위로 `comments_part_N.csv` 파일로 로컬 저장. (JSON/SQLite 배제)
    - **Summary**: 총 수집 수, 실행 시간, 에러 로그를 Google Sheets로 전송.

## 3. 상세 모듈 설계
### [M1] YT-URL-EXTRACTOR v1.0
- 입력받은 유튜브 URL에서 `video_id`를 정규식으로 추출.

### [M2] API-FETCHER v1.0
- `commentThreads.list` (상위 댓글) 및 `comments.list` (대댓글) 호출.
- 매 응답 직후 `checkpoint.json` 갱신.
- `HttpError 403` 감지 시 즉시 상태 저장 및 종료 로직 실행.

### [M3] CSV-CHUNKER v1.0
- 메모리 내 데이터를 20,000건마다 로컬 CSV 파일로 플러시(Flush).
- 파일명 형식: `comments_part_[index].csv`

### [M4] SHEET-REPORTER v1.0
- 수집 종료(정상 또는 에러) 시 최종 상태를 Google Sheets API를 통해 기록.

## 4. 보안 및 품질
- `.env` 파일을 통한 자격 증명 관리.
- '싫어요' 데이터 수집 절대 금지.
- 개인정보 보호를 위해 작성자 핸들(ID) 외 정보 수집 금지.

## 5. 실행 환경
- Python 3.10+ 독립 로컬 환경.
- `1_collection/` 디렉토리를 작업 및 데이터 저장 공간으로 사용.

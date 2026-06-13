# YouTube Comment Collector (v1.0.0)

연구팀을 위한 고성능 유튜브 댓글 수집기입니다.

## 주요 기능
- 수천 개의 댓글 및 답글 자동 수집
- 체크포인트 기능을 통한 중단 시 재개 가능
- 5,000개 단위 CSV 자동 분할 저장
- 실시간 수집 현황 모니터링

## 사용 방법
1. `.env.template` 파일을 `.env`로 복사합니다.
2. `.env` 파일에 본인의 **YOUTUBE_API_KEY**를 입력합니다.
   ```env
   YOUTUBE_API_KEY=your_actual_api_key_here
   ```
3. `requirements.txt`에 있는 라이브러리를 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
4. `start_collector.bat` 파일을 실행하거나 다음 명령어를 입력합니다.
   ```bash
   python web_server.py
   ```
5. 브라우저에서 `http://localhost:8000`에 접속하여 수집할 영상의 URL을 입력합니다.

## 주의 사항
- 유튜브 API 할당량(Quota)을 준수하십시오.
- 대량 수집 시 API 키가 여러 개 필요할 수 있습니다.

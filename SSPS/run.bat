@echo off
chcp 65001 >nul
echo ==============================================
echo  SSPS (지능형 쇼핑 숏폼 상품 선정 시스템) 실행기
echo ==============================================

:: 가상환경 설정 (없으면 생성)
if not exist "..\.venv" (
    echo [INFO] 가상환경을 생성합니다...
    python -m venv ..\.venv
)

:: 가상환경 활성화
call ..\.venv\Scripts\activate.bat

:: 패키지 의존성 확인
echo [INFO] 패키지 의존성을 확인 및 설치합니다...
pip install -r backend\requirements.txt >nul 2>&1

:: .env 파일 확인
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
    )
)

echo [INFO] SSPS API 서버와 대시보드를 시작합니다.
echo [INFO] 서버가 구동되면 자동으로 브라우저가 열립니다! (수동 접속: http://localhost:5000)
echo ==============================================

:: 브라우저를 2초 뒤에 백그라운드에서 열기 (꼼수)
start "" "http://localhost:5000"

:: FastAPI/Flask 서버 실행
python backend\main.py

pause

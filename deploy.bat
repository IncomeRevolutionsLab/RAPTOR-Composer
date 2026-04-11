@echo off
chcp 65001 >nul
echo ==============================================
echo  SSPS Vercel 자동 배포 도구 (Git Sync)
echo ==============================================

:: 1. 상태 확인
echo [1/3] 변경된 파일을 확인합니다...
git status -s

:: 2. 커밋 준비
echo [2/3] 모든 변경 사항을 스테이징에 추가하고 커밋합니다...
git add .
git commit -m "SSPS v2.35: N-Depth 엔진 고도화 및 캐시 버스팅 적용"

:: 3. 푸시
echo [3/3] GitHub로 전송하여 Vercel 배포를 시작합니다...
git push origin master

if %ERRORLEVEL% equ 0 (
    echo.
    echo ==============================================
    echo [성공] GitHub 전송이 완료되었습니다! 
    echo 약 1-2분 뒤 Vercel에서 업데이트된 버전을 확인하세요.
    echo ==============================================
) else (
    echo.
    echo [오류] 전송 중 문제가 발생했습니다. (Git 로그인 상태를 확인해주세요.)
)

pause

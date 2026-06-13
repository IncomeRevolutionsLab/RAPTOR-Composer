# RAPTOR 독립 백엔드 및 FFmpeg 렌더링 워커 배포용 Dockerfile

# 1. 경량화된 Python 3.11 Slim 베이스 이미지 사용
FROM python:3.11-slim

# 2. 환경 변수 구성 (파이썬 버퍼 최소화 및 비대화형 빌드)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 3. FFmpeg 및 한국어 자막 깨짐 방지를 위한 CJK 나눔 고딕 폰트 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-nanum \
    fonts-noto-cjk \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. 의존성 패키지 설치
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 5. 전체 소스 코드 복사
COPY . /app/

# 6. 포트 바인딩: Render.com은 $PORT를 동적으로 주입하므로 shell form CMD를 사용하여 환경변수 확장 보장
# (exec form 배열은 $PORT 등 환경변수 확장이 불가하므로 반드시 shell form 사용)
EXPOSE 8000

# 7. 단일 워커 제한 정책에 따라 uvicorn 단일 프로세스로 서버 실행 (TOCTOU Lock 유효성 보장)
# $PORT: Render.com 동적 포트 바인딩 / Koyeb 호환성을 위해 기본값 8000 설정
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1

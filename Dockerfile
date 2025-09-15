FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    wget \
    && rm -rf /var/lib/apt/lists/*

# RDS CA Bundle 다운로드
RUN wget https://s3.amazonaws.com/rds-downloads/rds-ca-2019-root.pem -O /app/rds-ca-bundle.pem

# Python 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# SSL 인증서 디렉토리 생성 (수동으로 ACM 인증서 추가 예정)
RUN mkdir -p /app/certs

# 포트 노출
EXPOSE 8083

# Flask 애플리케이션 실행
CMD ["python", "app.py"]

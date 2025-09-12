# Comment Service

댓글 서비스를 담당하는 Flask 기반 마이크로서비스입니다.

## 🚀 배포 방법

### 1. CI/CD 파이프라인 (권장)

이 프로젝트는 AWS CodeBuild와 CodePipeline을 사용한 자동화된 CI/CD 파이프라인을 지원합니다.

#### buildspec.yml 구성
- **Pre-build**: ECR 로그인, 이미지 태그 생성, 환경 변수 설정
- **Build**: Docker 이미지 빌드 및 태깅 (커밋 해시 + latest)
- **Post-build**: ECR 푸시, imagedefinitions.json 생성, EKS 배포

#### 필요한 환경 변수
```bash
# CodeBuild 환경 변수
AWS_DEFAULT_REGION=ap-northeast-2
ACCOUNT_ID=your-aws-account-id
K8S_CLUSTER_NAME=my-eks-cluster
K8S_NAMESPACE=comment-service
```

#### 배포 과정
1. GitHub에 코드 푸시
2. CodePipeline이 자동으로 트리거
3. CodeBuild가 buildspec.yml 실행
4. Docker 이미지 빌드 → ECR 푸시 → EKS 배포

### 2. 수동 배포

#### 환경변수 설정

다음 환경변수들을 설정해야 합니다:

```bash
# 데이터베이스 설정
DATABASE_URL=mysql+pymysql://user:password@host:port/database

# 애플리케이션 설정
SECRET_KEY=your-secret-key

# AWS Cognito 설정
COGNITO_USER_POOL_ID=your-user-pool-id
COGNITO_CLIENT_ID=your-client-id
COGNITO_REGION=ap-northeast-2

```

#### Docker 빌드 및 실행

```bash
# Docker 이미지 빌드
docker build -t comment-service .

# Docker 컨테이너 실행
docker run -p 8083:8083 \
  -e DATABASE_URL=mysql+pymysql://user:password@host:port/database \
  -e SECRET_KEY=your-secret-key \
  comment-service
```

### 3. Kubernetes 배포

#### 3.1 Secrets 생성

```bash
# 데이터베이스 시크릿
kubectl create secret generic comment-db-secret \
  --from-literal=host=your-rds-endpoint \
  --from-literal=user=your-db-username \
  --from-literal=password=your-db-password \
  --from-literal=name=your-db-name

# 애플리케이션 시크릿
kubectl create secret generic comment-secrets \
  --from-literal=secret-key=your-secret-key \
  --from-literal=jwt-secret-key=your-jwt-secret-key \
  --from-literal=cognito-user-pool-id=your-user-pool-id \
  --from-literal=cognito-client-id=your-client-id
```

#### 3.2 배포 실행

```bash
kubectl apply -f k8s/deployment.yaml
```

### 4. GitHub Actions 자동 배포

GitHub Secrets에 다음 값들을 설정하세요:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `DATABASE_URL`
- `SECRET_KEY`
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`

## 🧪 테스트 방법

### 헬스체크

```bash
curl http://localhost:8083/health
```

### API 테스트

```bash
# 댓글 목록 조회
curl http://localhost:8083/api/v1/comments

# 댓글 생성
curl -X POST http://localhost:8083/api/v1/comments \
  -H "Content-Type: application/json" \
  -d '{"post_id": 1, "content": "테스트 댓글"}'
```

## 📁 프로젝트 구조

```
Comment-master/
├── comment/                 # 서비스 코드
│   ├── __init__.py
│   ├── models.py           # 데이터 모델
│   ├── routes.py           # API 라우트
│   └── services.py         # 비즈니스 로직
├── k8s/                    # Kubernetes 배포 파일
│   └── deployment.yaml
├── .github/workflows/      # GitHub Actions
│   └── deploy.yml
├── app.py                  # Flask 애플리케이션
├── config.py               # 설정
├── Dockerfile              # Docker 이미지
├── requirements.txt        # Python 의존성
└── README.md              # 이 파일
```

## 🔧 개발 환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 애플리케이션 실행
python app.py
```

## 📝 API 문서

### 엔드포인트

- `GET /health` - 헬스체크
- `GET /api/v1/comments` - 댓글 목록 조회
- `POST /api/v1/comments` - 댓글 생성
- `GET /api/v1/comments/{id}` - 댓글 상세 조회
- `PUT /api/v1/comments/{id}` - 댓글 수정
- `DELETE /api/v1/comments/{id}` - 댓글 삭제

## 🛠️ 문제 해결

### 데이터베이스 연결 실패

1. RDS 엔드포인트 확인
2. 보안 그룹 설정 확인
3. 환경변수 설정 확인

### Docker 빌드 실패

1. `requirements.txt` 의존성 확인
2. Dockerfile 문법 확인
3. 네트워크 연결 확인


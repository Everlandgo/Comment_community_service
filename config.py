"""
Comment Service 설정
"""

import os
from datetime import timedelta

class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # 세션 설정 - 탭 종료 시 자동 로그아웃을 위해 False로 설정
    SESSION_PERMANENT = False
    SESSION_COOKIE_SECURE = False  # 개발 환경에서는 False, 운영 환경에서는 True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # 데이터베이스 설정 - Docker 환경에서는 mysql 서비스명 사용
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"mysql+pymysql://{os.environ.get('DB_USER', 'root')}:{os.environ.get('DB_PASSWORD', 'password')}@{os.environ.get('DB_HOST', 'mysql')}:{os.environ.get('DB_PORT', '3306')}/{os.environ.get('DB_NAME', 'commentdb')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AWS Cognito 설정
    COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
    COGNITO_REGION = os.environ.get('COGNITO_REGION', 'ap-northeast-2')
    COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')
    
    # JWT 설정
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    
    # 서비스 설정
    USER_SERVICE_URL = os.environ.get('USER_SERVICE_URL', 'http://localhost:8081')
    POST_SERVICE_URL = os.environ.get('POST_SERVICE_URL', 'http://localhost:8082')
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SQLALCHEMY_ECHO = False

class TestingConfig(Config):
    """테스트 환경 설정"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

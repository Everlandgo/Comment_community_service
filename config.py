"""
Comment Service 설정
"""

import os
from datetime import timedelta

def get_database_uri():
    """DATABASE_URL 환경변수가 있으면 사용, 없으면 개별 DB 환경변수로 조합"""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return database_url
    
    # 개별 환경변수로부터 DATABASE_URL 생성
    db_host = os.environ.get('DB_HOST')
    db_user = os.environ.get('DB_USER')
    db_password = os.environ.get('DB_PASSWORD')
    db_name = os.environ.get('DB_NAME')
    db_port = os.environ.get('DB_PORT', '3306')
    
    if all([db_host, db_user, db_password, db_name]):
        return f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # 기본값 (개발용)
    return 'sqlite:///comment.db'

class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # 세션 설정 - 탭 종료 시 자동 로그아웃을 위해 False로 설정
    SESSION_PERMANENT = False
    SESSION_COOKIE_SECURE = True  # HTTPS 환경에서는 True로 설정
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # 데이터베이스 설정 - RDS 연결을 위한 DATABASE_URL 생성
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AWS Cognito 설정
    COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
    COGNITO_REGION = os.environ.get('COGNITO_REGION', 'ap-northeast-2')
    COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')
    
    # JWT 설정
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=5)
    

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

"""
Comment Service - Flask Application
MSA 아키텍처에서 Comment 서비스를 담당하는 Flask 애플리케이션입니다.
"""

import os
import logging
import ssl
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, NotFound
from flask_migrate import Migrate
from sqlalchemy import text
from comment.models import db  # Comment 모델 import
from comment.routes import bp  # Comment 라우트 import

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_class=None):
    """Flask 애플리케이션 팩토리"""
    app = Flask(__name__)

    # 설정 로드
    if config_class:
        app.config.from_object(config_class)
    else:
        # config.py의 Config 클래스 사용
        from config import Config
        app.config.from_object(Config)

    # CORS 설정
    CORS(app,
     origins=["https://www.hhottdogg.shop", "https://hhottdogg.shop"],
     methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True,
     max_age=86400)

    # 데이터베이스 초기화
    db.init_app(app)
    Migrate(app, db)

    # 테이블 생성 - 연결 실패 시에도 애플리케이션은 계속 실행
    with app.app_context():
        try:
            # 데이터베이스 연결 테스트
            db.session.execute(text('SELECT 1'))
            logger.info("Database connection test successful")
            
            # 테이블 생성
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            logger.warning("Application will continue without database initialization")
            # 연결 실패 시에도 애플리케이션은 계속 실행


    # 블루프린트 등록
    app.register_blueprint(bp, url_prefix='/api/v1')


    # 전역 에러 핸들러
    @app.errorhandler(HTTPException)
    def handle_exception(e):
        response = {
            "error": {
                "code": e.code,
                "name": e.name,
                "description": e.description
            }
        }
        return jsonify(response), e.code

    @app.errorhandler(NotFound)
    def handle_not_found(e):
        response = {
            "error": {
                "code": 404,
                "name": "Not Found",
                "description": "The requested resource was not found"
            }
        }
        return jsonify(response), 404

    @app.errorhandler(Exception)
    def handle_generic_exception(e):
        logger.error(f"Unhandled exception: {str(e)}")
        response = {
            "error": {
                "code": 500,
                "name": "Internal Server Error",
                "description": "An unexpected error occurred"
            }
        }
        return jsonify(response), 500

    # 헬스체크 엔드포인트
    @app.route('/health', methods=['GET'])
    def health():
        try:
            db.session.execute(text('SELECT 1'))
            db_status = 'connected'
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            db_status = 'disconnected'
        
        return jsonify({
            'status': 'healthy' if db_status == 'connected' else 'unhealthy',
            'service': 'Comment Service API',
            'version': '1.0.0',
            'database': db_status
        })

    return app

app = create_app()

def create_ssl_context():
    """SSL 컨텍스트 생성 (수동 ACM 인증서 사용)"""
    try:
        # 환경변수에서 인증서 경로 가져오기
        cert_file = os.environ.get('SSL_CERT_FILE', '/app/certs/cert.pem')
        key_file = os.environ.get('SSL_KEY_FILE', '/app/certs/key.pem')
        
        print(f"[SSL DEBUG] 인증서 경로 확인 중...")
        print(f"[SSL DEBUG] 인증서 파일: {cert_file}")
        print(f"[SSL DEBUG] 개인키 파일: {key_file}")
        
        if os.path.exists(cert_file) and os.path.exists(key_file):
            print(f"[SSL DEBUG] ✅ 인증서 파일 존재 확인됨")
            logger.info(f"Using SSL certificates: {cert_file}, {key_file}")
            
            # SSL 컨텍스트 생성 및 설정
            print(f"[SSL DEBUG] SSL 컨텍스트 생성 중...")
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            
            print(f"[SSL DEBUG] 인증서 체인 로드 중...")
            context.load_cert_chain(cert_file, key_file)
            print(f"[SSL DEBUG] ✅ 인증서 체인 로드 성공")
            
            # 보안 설정
            print(f"[SSL DEBUG] 보안 설정 적용 중...")
            context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            context.options |= ssl.OP_NO_SSLv2
            context.options |= ssl.OP_NO_SSLv3
            context.options |= ssl.OP_NO_TLSv1
            context.options |= ssl.OP_NO_TLSv1_1
            print(f"[SSL DEBUG] ✅ SSL 컨텍스트 생성 완료")
            
            return context
        else:
            print(f"[SSL ERROR] ❌ SSL 인증서 파일을 찾을 수 없습니다!")
            print(f"[SSL ERROR] 인증서 파일 존재: {os.path.exists(cert_file) if 'cert_file' in locals() else 'N/A'}")
            print(f"[SSL ERROR] 개인키 파일 존재: {os.path.exists(key_file) if 'key_file' in locals() else 'N/A'}")
            logger.warning("SSL certificates not found, running HTTP server")
            return None
        
    except Exception as e:
        print(f"[SSL ERROR] ❌ SSL 인증 문제 발생: {e}")
        print(f"[SSL ERROR] SSL 컨텍스트 생성 실패")
        logger.error(f"SSL context creation failed: {e}")
        return None

if __name__ == '__main__':
    print(f"[SSL DEBUG] SSL 컨텍스트 생성 시작...")
    ssl_context = create_ssl_context()
    
    if ssl_context:
        print(f"[SSL DEBUG] ✅ HTTPS 서버 시작 중...")
        logger.info("Starting HTTPS server on port 8083")
        app.run(
            debug=False, 
            host='0.0.0.0', 
            port=8083,
            ssl_context=ssl_context
        )
    else:
        print(f"[SSL ERROR] ❌ SSL 인증 문제로 HTTP 서버로 전환")
        print(f"[SSL ERROR] SSL 컨텍스트가 생성되지 않았습니다")
        logger.warning("Starting HTTP server on port 8083 (SSL disabled)")
        app.run(debug=False, host='0.0.0.0', port=8083)

"""
Comment Service - Flask Application
MSA 아키텍처에서 Comment 서비스를 담당하는 Flask 애플리케이션입니다.
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
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
         origins=["http://localhost:3000", "http://localhost:8080"],
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

    # Swagger UI 설정
    SWAGGER_URL = '/api/docs'
    API_URL = '/static/swagger.json'
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={'app_name': "Comment Service API"}
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    # 블루프린트 등록
    app.register_blueprint(bp, url_prefix='/api/v1')

    # OPTIONS preflight 요청 처리
    @app.route('/api/v1/posts/<path:post_id>/comments', methods=['OPTIONS'])
    def handle_comments_options(post_id):
        response = jsonify({'message': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        return response

    @app.route('/api/v1/comments/<path:comment_id>', methods=['OPTIONS'])
    def handle_comment_options(comment_id):
        response = jsonify({'message': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        return response

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8083)

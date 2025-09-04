"""
Comment Service API Routes
MSA 환경에서 독립적으로 동작하는 Comment 서비스 API입니다.
"""

import os
import logging
import jwt
import requests
import time
from flask import Blueprint, request, jsonify, current_app
from .models import db, Comment, CommentLike
from .services import CommentService
from datetime import datetime
from functools import wraps

bp = Blueprint('api', __name__)

# 로깅 설정
logger = logging.getLogger(__name__)

# AWS Cognito 설정 (환경변수에서 읽기)
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_REGION = os.environ.get("COGNITO_REGION")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")

# 공개키 캐싱을 위한 전역 변수
_public_keys_cache = None
_public_keys_cache_time = 0
_CACHE_DURATION = 3600  # 1시간

# ============================================================================
# 유틸리티 함수들
# ============================================================================

def api_response(data=None, message="Success", status_code=200):
    """API 응답 표준화"""
    response = {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    return jsonify(response), status_code

def api_error(message="Error", status_code=400):
    """API 에러 응답 표준화"""
    response = {
        "success": False,
        "message": message,
        "error": {
            "code": status_code,
            "message": message
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    return jsonify(response), status_code

def get_cognito_public_keys():
    """Cognito User Pool의 공개키를 가져오고 캐싱합니다."""
    global _public_keys_cache, _public_keys_cache_time
    
    current_time = time.time()
    
    # 캐시가 유효한 경우 캐시된 공개키 반환
    if _public_keys_cache and (current_time - _public_keys_cache_time) < _CACHE_DURATION:
        logger.info("캐시된 공개키 사용")
        return _public_keys_cache
    
    try:
        url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        # 상세 디버깅 로그 제거
        
        response = requests.get(url, timeout=10)
        
        
        response.raise_for_status()
        
        # 캐시 업데이트
        _public_keys_cache = response.json()
        _public_keys_cache_time = current_time
        
        
        return _public_keys_cache
    except requests.RequestException as e:
        logger.error(f"공개키 가져오기 실패: {e}")
        # 캐시된 공개키가 있으면 사용
        if _public_keys_cache:
            logger.info("캐시된 공개키 사용")
            return _public_keys_cache
        raise Exception("Failed to get public keys")
    except Exception as e:
        logger.error(f"공개키 가져오기 실패: {e}")
        raise Exception("Failed to get public keys")

def get_public_keys_from_issuer(issuer: str) -> dict:
    """주어진 issuer의 JWKS를 가져옵니다."""
    try:
        jwks_url = issuer.rstrip('/') + '/.well-known/jwks.json'
        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"issuer 기반 공개키 가져오기 실패: {e}")
        return None

def verify_cognito_token(token: str) -> dict:
    """Cognito JWT 토큰을 검증합니다.

    - idToken: aud 검증(클라이언트 ID), token_use == "id"
    - accessToken: aud 미검증, issuer 검증, token_use == "access" 및 client_id == 클라이언트 ID
    """
    logger.info(f"JWT 토큰 검증 시작")
    
    # 토큰 형식 검증
    if not token or len(token.split('.')) != 3:
        logger.error("잘못된 JWT 토큰 형식")
        raise Exception("Invalid JWT token format")
    
    try:
        # 토큰 헤더에서 kid 추출
        unverified_header = jwt.get_unverified_header(token)
        
        
        kid = unverified_header.get('kid')
        
        
        if not kid:
            logger.error("kid가 토큰 헤더에 없음")
            raise Exception("Invalid token header")
        
        # Cognito 공개키 가져오기
        
        public_keys = get_cognito_public_keys()
        
        
        if not public_keys:
            logger.error("공개키를 가져올 수 없음")
            raise Exception("Failed to get public keys")
        
        # 해당 kid의 공개키 찾기
        
        public_key = None
        selected_issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
        for i, key in enumerate(public_keys['keys']):
            
            if key['kid'] == kid:
                
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
        
        if not public_key:
            logger.warning(f"kid '{kid}' 공개키 미발견. 토큰 issuer 기반으로 재시도")
            try:
                # 토큰의 iss를 확인하여 해당 JWKS로 재조회
                temp_unverified_payload = jwt.decode(
                    token,
                    options={"verify_signature": False}
                )
                issuer_from_token = temp_unverified_payload.get('iss')
                
                if issuer_from_token:
                    public_keys_from_iss = get_public_keys_from_issuer(issuer_from_token)
                    if public_keys_from_iss and 'keys' in public_keys_from_iss:
                        for i, key in enumerate(public_keys_from_iss['keys']):
                            if key.get('kid') == kid:
                                
                                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                                selected_issuer = issuer_from_token
                                break
            except Exception as retry_e:
                logger.error(f"issuer 기반 공개키 재시도 중 오류: {retry_e}")

        if not public_key:
            logger.error(f"kid '{kid}'에 해당하는 공개키를 찾을 수 없음 (env/iss 모두)")
            logger.error(f"사용 가능한 kid들(env): {[key.get('kid') for key in public_keys.get('keys', [])]}")
            raise Exception("Public key not found")
        
        # 토큰 타입 파악을 위해 서명 미검증으로 페이로드 먼저 확인
        unverified_payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )

        token_use = unverified_payload.get('token_use')
        aud = unverified_payload.get('aud')
        client_id_in_token = unverified_payload.get('client_id')
        issuer = selected_issuer

        

        # 토큰 검증
        

        if token_use == 'id':
            
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=COGNITO_CLIENT_ID,
                issuer=issuer
            )
            if payload.get('token_use') != 'id':
                raise Exception("Invalid token_use for id token")
        elif token_use == 'access':
            
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                issuer=issuer,
                options={"verify_aud": False}
            )
            if payload.get('token_use') != 'access':
                raise Exception("Invalid token_use for access token")
            if payload.get('client_id') != COGNITO_CLIENT_ID:
                logger.error(f"client_id 불일치: expected={COGNITO_CLIENT_ID}, actual={payload.get('client_id')}")
                raise Exception("Invalid client_id")
        else:
            logger.error(f"알 수 없는 token_use: {token_use}")
            raise Exception("Unknown token_use")

        logger.info("JWT 토큰 검증 완료")
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.error("토큰 만료됨")
        raise Exception("Token expired")
    except jwt.InvalidAudienceError:
        logger.error("잘못된 audience")
        raise Exception("Invalid audience")
    except jwt.InvalidIssuerError:
        logger.error("잘못된 issuer")
        raise Exception("Invalid issuer")
    except jwt.InvalidSignatureError:
        logger.error("서명 검증 실패")
        raise Exception("Invalid signature")
    except jwt.InvalidTokenError as e:
        logger.error(f"잘못된 토큰: {str(e)}")
        raise Exception(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"토큰 검증 실패: {e}")
        logger.error(f"에러 타입: {type(e).__name__}")
        logger.error(f"에러 상세: {str(e)}")
        raise Exception("Token verification failed")

def jwt_required(f):
    """JWT 토큰 검증 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token or not token.startswith('Bearer '):
            logger.warning("Authorization header missing or invalid format")
            return api_error("Authorization token required", 401)
        
        token = token.split(' ')[1]
        
        try:
            # Cognito JWT 토큰 검증
            payload = verify_cognito_token(token)
            request.current_user = payload
            logger.info(f"JWT validation successful for user: {payload.get('sub', 'unknown')}")
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"JWT validation failed: {str(e)}")
            # 더 구체적인 에러 메시지 제공
            if "Token expired" in str(e):
                return api_error("Token expired", 401)
            elif "Invalid audience" in str(e):
                return api_error("Invalid token audience", 401)
            elif "Invalid issuer" in str(e):
                return api_error("Invalid token issuer", 401)
            elif "Invalid token" in str(e):
                return api_error("Invalid token format", 401)
            else:
                return api_error("Token verification failed", 401)
    
    return decorated_function

# ============================================================================
# 댓글 API 엔드포인트
# ============================================================================

@bp.route('/posts/<post_id>/comments', methods=['GET'])
def get_comments(post_id):
    """특정 게시글의 댓글 목록 조회"""
    logger.info(f"댓글 목록 조회 요청 - post_id: {post_id}, type: {type(post_id)}")
    
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        skip = (page - 1) * size
        
        comments, total = CommentService.get_comments(
            post_id, skip=skip, limit=size,
            sort_by=sort_by, sort_order=sort_order
        )
        
        # 댓글을 딕셔너리로 변환
        comments_data = [comment.to_dict() for comment in comments]
        
        logger.info(f"댓글 목록 조회 성공 - count: {len(comments_data)}, total: {total}")
        return api_response(data={
            "comments": comments_data,
            "total": total,
            "page": page,
            "size": size
        })
        
    except Exception as e:
        logger.error(f"댓글 목록 조회 실패: {e}")
        return api_error("댓글 목록 조회에 실패했습니다", 500)

@bp.route('/posts/<post_id>/comments', methods=['POST'])
@jwt_required
def create_comment(post_id):
    """댓글 작성"""
    logger.info(f"댓글 작성 요청 - post_id: {post_id}, type: {type(post_id)}")
    logger.info(f"요청 데이터: {request.get_json()}")
    
    try:
        data = request.get_json()
        
        if not data or 'content' not in data:
            return api_error("댓글 내용은 필수입니다", 400)
        
        # Cognito 사용자 정보 추출 및 검증
        current_user = request.current_user
        user_sub = current_user.get("sub")
        user_name = current_user.get("cognito:username") or current_user.get("username") or "Unknown"
        
        # user_sub가 없으면 에러
        if not user_sub:
            logger.error(f"사용자 sub 정보가 없음: {current_user}")
            return api_error("사용자 정보를 확인할 수 없습니다", 400)
        

        
        # 댓글 생성
        comment = CommentService.create_comment(
            post_id=post_id,
            user_id=user_sub,
            user_name=user_name,
            content=data["content"]
        )
        
        logger.info(f"댓글 작성 성공 - comment_id: {comment.id}")
        
        
        return api_response(data=comment.to_dict(), message="댓글이 작성되었습니다", status_code=201)
        
    except Exception as e:
        logger.error(f"댓글 작성 실패: {e}")
        return api_error("댓글 작성에 실패했습니다", 500)

@bp.route('/comments/<int:comment_id>', methods=['PATCH'])
@jwt_required
def update_comment(comment_id):
    """댓글 수정"""
    try:
        data = request.get_json()
        
        if not data or 'content' not in data:
            return api_error("댓글 내용은 필수입니다", 400)
        
        # Cognito 사용자 정보 추출 및 검증
        current_user = request.current_user
        user_sub = current_user.get("sub")
        
        if not user_sub:
            logger.error(f"사용자 sub 정보가 없음: {current_user}")
            return api_error("사용자 정보를 확인할 수 없습니다", 400)
        
        # 댓글 존재 및 작성자 확인
        comment = CommentService.get_comment_by_id(comment_id)
        if not comment:
            return api_error("댓글을 찾을 수 없습니다", 404)
        

        
        if comment.user_id != user_sub:
            return api_error("이 댓글을 수정할 권한이 없습니다", 403)
        
        # 댓글 수정
        updated_comment = CommentService.update_comment(comment_id, {"content": data["content"]})
        
        return api_response(data=updated_comment.to_dict(), message="댓글이 수정되었습니다")
        
    except Exception as e:
        logger.error(f"댓글 수정 실패: {e}")
        return api_error("댓글 수정에 실패했습니다", 500)

@bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required
def delete_comment(comment_id):
    """댓글 삭제"""
    try:
        # Cognito 사용자 정보 추출 및 검증
        current_user = request.current_user
        user_sub = current_user.get("sub")
        
        if not user_sub:
            logger.error(f"사용자 sub 정보가 없음: {current_user}")
            return api_error("사용자 정보를 확인할 수 없습니다", 400)
        
        # 댓글 존재 및 작성자 확인
        comment = CommentService.get_comment_by_id(comment_id)
        if not comment:
            return api_error("댓글을 찾을 수 없습니다", 404)
        

        
        if comment.user_id != user_sub:
            return api_error("이 댓글을 삭제할 권한이 없습니다", 403)
        
        # 댓글 삭제
        CommentService.delete_comment(comment_id)
        
        
        return api_response(message="댓글이 삭제되었습니다")
        
    except Exception as e:
        logger.error(f"댓글 삭제 실패: {e}")
        return api_error("댓글 삭제에 실패했습니다", 500)

@bp.route('/comments/my', methods=['GET'])
@jwt_required
def get_my_comments():
    """내 댓글 목록 조회"""
    try:
        # Cognito 사용자 정보 추출 및 검증
        current_user = request.current_user
        user_sub = current_user.get("sub")
        
        if not user_sub:
            logger.error(f"사용자 sub 정보가 없음: {current_user}")
            return api_error("사용자 정보를 확인할 수 없습니다", 400)
        
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        
        skip = (page - 1) * size
        
        comments = CommentService.get_comments_by_user(user_sub, skip=skip, limit=size)
        
        # 댓글을 딕셔너리로 변환
        comments_data = [comment.to_dict() for comment in comments]
        
        return api_response(data=comments_data)
        
    except Exception as e:
        logger.error(f"내 댓글 목록 조회 실패: {e}")
        return api_error("내 댓글 목록 조회에 실패했습니다", 500)

@bp.route('/comments/<int:comment_id>/like', methods=['POST'])
@jwt_required
def toggle_comment_like(comment_id):
    """댓글 좋아요 토글"""
    try:
        # Cognito 사용자 정보 추출 및 검증
        current_user = request.current_user
        user_sub = current_user.get("sub")
        
        if not user_sub:
            logger.error(f"사용자 sub 정보가 없음: {current_user}")
            return api_error("사용자 정보를 확인할 수 없습니다", 400)
        
        # 댓글 존재 확인
        comment = CommentService.get_comment_by_id(comment_id)
        if not comment:
            return api_error("댓글을 찾을 수 없습니다", 404)
        
        # 좋아요 토글
        is_liked = CommentService.toggle_comment_like(comment_id, user_sub)
        
        if is_liked:
            message = "댓글에 좋아요를 눌렀습니다"
        else:
            message = "댓글 좋아요를 취소했습니다"
        
        return api_response(data={
            "comment_id": comment_id,
            "liked": is_liked
        }, message=message)
        
    except Exception as e:
        logger.error(f"댓글 좋아요 토글 실패: {e}")
        return api_error("댓글 좋아요 토글에 실패했습니다", 500)

@bp.route('/comments/<int:comment_id>/like/status', methods=['GET'])
@jwt_required
def get_comment_like_status(comment_id):
    """댓글 좋아요 상태 확인"""
    try:
        # Cognito 사용자 정보 추출 및 검증
        current_user = request.current_user
        user_sub = current_user.get("sub")
        
        if not user_sub:
            logger.error(f"사용자 sub 정보가 없음: {current_user}")
            return api_error("사용자 정보를 확인할 수 없습니다", 400)
        
        is_liked = CommentService.get_comment_like_status(comment_id, user_sub)
        
        return api_response(data={
            "comment_id": comment_id,
            "is_liked": is_liked
        })
        
    except Exception as e:
        logger.error(f"댓글 좋아요 상태 확인 실패: {e}")
        return api_error("댓글 좋아요 상태 확인에 실패했습니다", 500)

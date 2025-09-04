"""
Comment Service 비즈니스 로직
"""

from .models import db, Comment, CommentLike
from typing import List, Tuple, Optional

class CommentService:
    """댓글 서비스 클래스"""
    
    @staticmethod
    def create_comment(post_id: int, user_id: str, user_name: str, content: str) -> Comment:
        """새 댓글 생성"""
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            user_name=user_name,
            content=content
        )
        db.session.add(comment)
        db.session.commit()
        db.session.refresh(comment)
        return comment
    
    @staticmethod
    def get_comment_by_id(comment_id: int) -> Optional[Comment]:
        """ID로 댓글 조회"""
        return Comment.query.get(comment_id)
    
    @staticmethod
    def get_comments(post_id: int, skip: int = 0, limit: int = 10,
                     sort_by: str = "created_at", sort_order: str = "desc") -> Tuple[List[Comment], int]:
        """특정 게시글의 댓글 목록 조회"""
        query = Comment.query.filter_by(
            post_id=post_id,
            status="visible"
        )
        
        # 정렬
        if sort_by == "created_at":
            if sort_order == "desc":
                query = query.order_by(Comment.created_at.desc())
            else:
                query = query.order_by(Comment.created_at.asc())
        elif sort_by == "like_count":
            if sort_order == "desc":
                query = query.order_by(Comment.like_count.desc())
            else:
                query = query.order_by(Comment.like_count.asc())
        
        # 총 개수 계산
        total = query.count()
        
        # 페이지네이션
        comments = query.offset(skip).limit(limit).all()
        
        return comments, total
    
    @staticmethod
    def get_comments_by_user(user_id: str, skip: int = 0, limit: int = 10) -> List[Comment]:
        """특정 사용자가 작성한 댓글 조회"""
        return Comment.query.filter_by(
            user_id=user_id,
            status="visible"
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_comment(comment_id: int, update_data: dict) -> Optional[Comment]:
        """댓글 수정"""
        comment = Comment.query.get(comment_id)
        if not comment:
            return None
        
        for key, value in update_data.items():
            if hasattr(comment, key):
                setattr(comment, key, value)
        
        db.session.commit()
        db.session.refresh(comment)
        return comment
    
    @staticmethod
    def delete_comment(comment_id: int) -> bool:
        """댓글 삭제 (상태 변경)"""
        comment = Comment.query.get(comment_id)
        if not comment:
            return False
        
        comment.status = "deleted"
        db.session.commit()
        return True
    
    @staticmethod
    def toggle_comment_like(comment_id: int, user_id: str) -> bool:
        """댓글 좋아요 토글"""
        # 기존 좋아요 확인
        existing_like = CommentLike.query.filter_by(
            comment_id=comment_id,
            user_id=user_id
        ).first()
        
        if existing_like:
            # 좋아요 취소
            db.session.delete(existing_like)
            comment = Comment.query.get(comment_id)
            if comment and comment.like_count > 0:
                comment.like_count -= 1
            db.session.commit()
            return False
        else:
            # 좋아요 추가
            new_like = CommentLike(comment_id=comment_id, user_id=user_id)
            db.session.add(new_like)
            comment = Comment.query.get(comment_id)
            if comment:
                comment.like_count += 1
            db.session.commit()
            return True
    
    @staticmethod
    def get_comment_like_status(comment_id: int, user_id: str) -> bool:
        """사용자의 댓글 좋아요 상태 확인"""
        like = CommentLike.query.filter_by(
            comment_id=comment_id,
            user_id=user_id
        ).first()
        return like is not None

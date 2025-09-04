"""
Comment Service 데이터베이스 모델
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, func, ForeignKey
import enum
from datetime import datetime

db = SQLAlchemy()

class CommentStatus(str, enum.Enum):
    visible = "visible"
    hidden = "hidden"
    deleted = "deleted"

class Comment(db.Model):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(32), index=True, nullable=False)  # Post 서비스의 post ID 참조 (별도 DB)
    user_id = Column(String(100), nullable=False, index=True)  # Cognito User ID
    user_name = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(Enum(CommentStatus), default=CommentStatus.visible)
    like_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """모델을 딕셔너리로 변환"""
        return {
            "id": self.id,
            "post_id": self.post_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "content": self.content,
            "status": self.status.value,
            "like_count": self.like_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class CommentLike(db.Model):
    __tablename__ = "comment_likes"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, index=True, nullable=False)  # Comment ID 참조
    user_id = Column(String(100), nullable=False, index=True)  # Cognito User ID
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        """모델을 딕셔너리로 변환"""
        return {
            "id": self.id,
            "comment_id": self.comment_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# Blueprint for USER class that maps to DB table using SQLAlchemy ORM

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from .db import Base
from .config import settings


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(settings.USER_NAME_MAX_LENGTH), nullable=False)
    email = Column(String(settings.USER_EMAIL_MAX_LENGTH), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

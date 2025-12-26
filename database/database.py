from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import ForeignKey, Integer, String, JSON, DateTime, Column, ARRAY
from typing import Optional
from datetime import datetime


class MainBase(DeclarativeBase):
    pass


class Users(MainBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str]
    token: Mapped[Optional[str]]
    role: Mapped[str]
    points: Mapped[int]


class Tasks(MainBase):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[int]
    points: Mapped[int]
    category: Mapped[str]
    subcategory: Mapped[str]
    condition: Mapped[str]
    solution: Mapped[str]
    answer: Mapped[str]


class BattleHistory(MainBase):
    __tablename__ = 'battle_history'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id1: Mapped[int] = mapped_column(Integer, ForeignKey(Users.id))
    id2: Mapped[int] = mapped_column(Integer, ForeignKey(Users.id))
    result1: Mapped[int]
    result2: Mapped[int]
    solvingtime1: Mapped[list[int]] = Column(ARRAY(Integer))
    solvingtime2: Mapped[list[int]] = Column(ARRAY(Integer))
    date: Mapped[datetime]


class Analytics(MainBase):
    __tablename__ = 'analytics'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime]
    data: Mapped[dict] = mapped_column(JSON)


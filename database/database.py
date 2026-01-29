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
    name: Mapped[str]
    surname: Mapped[str]
    status: Mapped[Optional[str]] = mapped_column(String, default=None)  # training / battle / None


class Categories(MainBase):
    __tablename__ = 'categories'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str]


class SubCategories(MainBase):
    __tablename__ = 'subcategories'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str]
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey(Categories.id))


class Tasks(MainBase):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[int]
    category: Mapped[int] = mapped_column(Integer, ForeignKey(Categories.id))
    subcategory: Mapped[list[int]] = Column(ARRAY(Integer))
    condition: Mapped[str]
    solution: Mapped[str]
    answer: Mapped[str]
    source: Mapped[str]
    answer_type: Mapped[str]


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
    userid: Mapped[int] = mapped_column(Integer, ForeignKey(Users.id))

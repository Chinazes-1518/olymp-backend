from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from dotenv import load_dotenv
import os

from .database import *

load_dotenv()

engine = create_async_engine(f'postgresql+asyncpg://jaan:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}/postgres')
sessions = async_sessionmaker(engine)
from fastapi import FastAPI
from pydantic import BaseModel
import logging
from datetime import date
from contextlib import asynccontextmanager
from sqlalchemy import Column, Integer, Float, String, Date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

########################################################################################
# Параметры БД
########################################################################################

DATABASE_URL = "sqlite+aiosqlite:///weight_bot.db"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


# Создаем класс для записи значения веса
class WeightData(BaseModel):
    user_id: int
    weight: float
    date: date
    username: str | None = None

# Создаем класс для создания новой записи в БД
class WeightRecord(Base):
    __tablename__ = "weight_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String, nullable=True)
    weight = Column(Float, nullable=False)
    date = Column(Date, nullable=False)

########################################################################################
# Создаем БД
########################################################################################
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logging.info("Database initialized and tables created successfully")
    yield
    
    # Cleanup on shutdown
    await engine.dispose()

########################################################################################
# Вставка значений в БД
########################################################################################

app = FastAPI(lifespan=lifespan)

# Функция для сохранения веса в БД
@app.post("/save-weight")
async def save_weight(data: WeightData):
    async with AsyncSessionLocal() as session:
        new_record = WeightRecord(
            user_id=data.user_id,
            username=data.username,
            weight=data.weight,
            date=data.date
        )
        session.add(new_record)
        message = "Weight saved successfully"

        # Сохраняем изменения в БД
        await session.commit()

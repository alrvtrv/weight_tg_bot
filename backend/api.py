from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Создаем класс для записи значения веса
class WeightData(BaseModel):
    user_id: int
    weight: float
    username: str | None = None

# Функция для сохранения веса (пока без реального сохранения)
@app.post("/save-weight")
async def save_weight(data: WeightData):
    print(f"Received weight: {data.weight} kg from user {data.user_id} ({data.username})")
    return {"status": "success", "message": "Weight saved"}
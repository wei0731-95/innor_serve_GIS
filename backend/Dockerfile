# syntax=docker/dockerfile:1
# CityGap FastAPI backend
# 執行：uvicorn app.main:app --host 0.0.0.0 --port 8000（不用 --reload，production-like）
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先安裝套件，讓程式碼變動時可以重用這一層
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 程式碼；tests 一併放入，方便 docker compose exec backend python -m pytest
COPY app ./app
COPY tests ./tests
COPY .env.example ./

# SQLite 與下載快取都在 /app/data，由 docker-compose 以 bind mount（./backend/data）持久化
RUN mkdir -p /app/data/cache

EXPOSE 8000

# 一定要 bind 0.0.0.0，container 外才連得到
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

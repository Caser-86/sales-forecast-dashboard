FROM python:3.11-slim

WORKDIR /app

# 系统依赖（gcc 用于编译 lightgbm，libgomp1 用于 OpenMP）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    mkdir -p data/raw data/processed ml/saved_models logs && \
    chown -R appuser:appuser /app

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# 健康检查（使用 /health 端点）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

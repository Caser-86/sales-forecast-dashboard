# 部署脚本（在服务器执行）
#!/bin/bash
set -e

PROJECT_DIR="/root/sales-forecast-dashboard"

echo "=== 销售数据预测大屏 - 部署 ==="

# 1. 进入项目目录
cd "$PROJECT_DIR" || { echo "项目目录不存在: $PROJECT_DIR"; exit 1; }

# 2. 构建镜像
echo "[1/3] 构建 Docker 镜像..."
docker-compose build

# 3. 启动服务
echo "[2/3] 启动服务..."
docker-compose up -d

# 4. 等待后端就绪
echo "[3/3] 等待后端就绪..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/ > /dev/null; then
        echo "后端服务已就绪"
        break
    fi
    sleep 2
done

echo ""
echo "=== 部署完成 ==="
echo "前端: http://localhost:3000"
echo "API 文档: http://localhost:8000/docs"
echo "查看日志: docker-compose logs -f"

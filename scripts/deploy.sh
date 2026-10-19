#!/bin/bash
# 部署脚本（在服务器执行）
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3000}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"

show_failure_context() {
    echo "部署失败，最近的 Compose 状态和日志："
    docker compose ps || true
    docker compose logs --tail=100 backend frontend || true
}

trap show_failure_context ERR

echo "=== 销售数据预测大屏 - 部署 ==="
cd "$PROJECT_DIR"

echo "[1/4] 构建 Docker 镜像..."
docker compose build

echo "[2/4] 启动服务..."
docker compose up -d

echo "[3/4] 等待后端就绪（最多 ${WAIT_SECONDS}s）..."
ready=0
for ((i = 1; i <= WAIT_SECONDS; i++)); do
    if curl -fsS "${BACKEND_URL}/health" > /dev/null; then
        ready=1
        break
    fi
    sleep 1
done

if [[ "$ready" -ne 1 ]]; then
    echo "后端未在 ${WAIT_SECONDS}s 内通过 ${BACKEND_URL}/health"
    exit 1
fi

echo "[4/4] 执行部署接口验收..."
"${PROJECT_DIR}/scripts/verify_deployment.sh" "$BACKEND_URL"
curl -fsS "${FRONTEND_URL}/" > /dev/null

trap - ERR
echo ""
echo "=== 部署完成 ==="
echo "前端: ${FRONTEND_URL}"
echo "API 文档: ${BACKEND_URL}/docs"
echo "查看日志: docker compose logs -f"

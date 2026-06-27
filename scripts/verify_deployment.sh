#!/usr/bin/env bash
# 部署后验证脚本：检查服务是否正常运行。
# 使用：bash scripts/verify_deployment.sh [BASE_URL]
set -e

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expect="$3"
    local resp
    resp=$(curl -fsS -o /tmp/_deploy_check -w "%{http_code}" "${url}" 2>/dev/null || echo "000")
    if [[ "${resp}" == "${expect}" ]]; then
        echo "  [OK]   ${name} (${resp})"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] ${name} (期望 ${expect}, 实际 ${resp})"
        FAIL=$((FAIL + 1))
    fi
}

echo "================ 部署验证 ================"
echo "目标: ${BASE_URL}"
echo "-----------------------------------------"

check "根路径"     "${BASE_URL}/"                 "200"
check "健康检查"   "${BASE_URL}/health"           "200"
check "API 文档"   "${BASE_URL}/docs"             "200"
check "商品列表"   "${BASE_URL}/api/products"     "200"
check "大屏聚合"   "${BASE_URL}/api/dashboard"    "200"
check "库存接口"   "${BASE_URL}/api/inventory"    "200"
check "KPI 接口"   "${BASE_URL}/api/kpi"          "200"
check "预测接口"   "${BASE_URL}/api/forecast?product_id=1&store_id=1"  "200"
check "历史销量"   "${BASE_URL}/api/sales?product_id=1&store_id=1&days=30" "200"

# 错误场景：不存在商品应返回 404
check "错误处理(404)" "${BASE_URL}/api/sales?product_id=999&store_id=1&days=30" "404"

echo "-----------------------------------------"
echo "通过: ${PASS}  失败: ${FAIL}"

if [[ ${FAIL} -gt 0 ]]; then
    echo "结论: 部署存在问题，请检查"
    exit 1
fi
echo "结论: 部署成功"

"""统一异常体系与错误响应格式。

错误响应统一格式:
{
  "error": {
    "code": "ERROR_CODE",
    "message": "用户可读的错误描述",
    "detail": "调试信息（仅开发环境）"
  }
}
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    """应用异常基类。"""

    code: str = "APP_ERROR"
    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        detail: Optional[str] = None,
        code: Optional[str] = None,
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        if code:
            self.code = code
        if http_status:
            self.http_status = http_status

    def to_response(self, include_detail: bool = False) -> Dict[str, Any]:
        """转为客户端响应字典。"""
        body: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if include_detail and self.detail:
            body["detail"] = self.detail
        return {"error": body}


# ---------- 常见业务异常 ----------

class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 422


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = 409


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    http_status = 401


class ServiceUnavailableError(AppError):
    code = "SERVICE_UNAVAILABLE"
    http_status = 503


class DataNotInitializedError(ServiceUnavailableError):
    """数据或模型未初始化。"""
    code = "DATA_NOT_INITIALIZED"


class ModelNotTrainedError(ServiceUnavailableError):
    """模型未训练。"""
    code = "MODEL_NOT_TRAINED"

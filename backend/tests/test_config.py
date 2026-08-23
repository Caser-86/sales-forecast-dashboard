"""配置系统测试。"""
from __future__ import annotations


class TestConfig:
    def test_default_settings(self):
        """默认配置加载。"""
        from app.core.config import Settings
        s = Settings()
        assert s.APP_NAME
        assert s.ENV in ("development", "production", "test")
        assert s.PORT == 8000

    def test_cors_origins_parsed_as_list(self):
        """CORS 字符串正确解析为列表。"""
        from app.core.config import Settings
        s = Settings(CORS_ORIGINS="http://a.com, http://b.com ,http://c.com")
        assert s.cors_origin_list == ["http://a.com", "http://b.com", "http://c.com"]

    def test_cors_origins_empty_string(self):
        """空 CORS 字符串解析为空列表。"""
        from app.core.config import Settings
        s = Settings(CORS_ORIGINS="")
        assert s.cors_origin_list == []

    def test_is_prod_flag(self):
        """生产环境标志正确。"""
        from app.core.config import Settings
        assert Settings(ENV="production").is_prod is True
        assert Settings(ENV="development").is_prod is False

    def test_auth_enabled_depends_on_token(self):
        """认证开关取决于 API_TOKEN。"""
        from app.core.config import Settings
        assert Settings(API_TOKEN="").auth_enabled is False
        assert Settings(API_TOKEN="secret").auth_enabled is True

    def test_env_validator_rejects_invalid(self):
        """非法 ENV 值应被拒绝。"""
        from app.core.config import Settings
        from pydantic import ValidationError
        try:
            Settings(ENV="staging")
            assert False, "应抛出 ValidationError"
        except ValidationError:
            pass

    def test_ensure_dirs_creates_log_dir(self, tmp_path):
        """ensure_dirs 创建日志目录。"""
        from app.core.config import Settings
        s = Settings(LOG_DIR=str(tmp_path / "logs"))
        s.ensure_dirs()
        assert (tmp_path / "logs").exists()

    def test_ensure_dirs_idempotent(self, tmp_path):
        """ensure_dirs 幂等：重复调用不会报错。"""
        from app.core.config import Settings
        s = Settings(
            LOG_DIR=str(tmp_path / "logs"),
            DATA_RAW_DIR=str(tmp_path / "raw"),
            DATA_PROCESSED_DIR=str(tmp_path / "processed"),
            MODELS_DIR=str(tmp_path / "models"),
        )
        s.ensure_dirs()
        s.ensure_dirs()
        assert (tmp_path / "logs").is_dir()
        assert (tmp_path / "raw").is_dir()
        assert (tmp_path / "processed").is_dir()
        assert (tmp_path / "models").is_dir()

    def test_settings_singleton(self):
        """get_settings 返回同一实例。"""
        from app.core.config import get_settings
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_paths_resolve(self):
        """路径属性解析为绝对路径。"""
        from app.core.config import settings
        assert settings.SALES_CSV.is_absolute()
        assert settings.LSTM_PATH.is_absolute()
        assert settings.LGBM_PATH.is_absolute()

    def test_legacy_path_constants_match_settings(self):
        """app.config 兼容层常量与 settings 一致。"""
        from app.config import FEATURES_CSV, REPORT_JSON, SALES_CSV
        from app.core.config import settings
        assert SALES_CSV == settings.SALES_CSV
        assert FEATURES_CSV == settings.FEATURES_CSV
        assert REPORT_JSON == settings.REPORT_JSON

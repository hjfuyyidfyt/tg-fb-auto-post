from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    app_env: str = "development"
    bot_token: str = ""
    bot_owner_id: str = ""
    oracle_user: str = ""
    oracle_password: str = ""
    oracle_dsn: str = ""
    oracle_wallet_dir: str = ""
    redis_url: str = "redis://redis:6379/0"
    dashboard_secret: str = ""
    dashboard_public_url: str = ""
    dashboard_port: int = 8000
    facebook_promo_graph_api_enabled: bool = False
    facebook_graph_version: str = "v24.0"
    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-2.5-flash-lite"
    gemini_text_fallback_model: str = "gemini-2.5-flash"
    alibaba_api_key: str = ""
    alibaba_image_api_enabled: bool = False
    alibaba_image_dry_run: bool = True
    alibaba_image_admin_live_only: bool = True
    alibaba_image_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    alibaba_free_monthly_image_cap: int = 10
    alibaba_paid_monthly_image_cap: int = 100
    alibaba_global_monthly_image_cap: int = 100

    @property
    def owner_ids(self) -> set[int]:
        if not self.bot_owner_id:
            return set()

        values = set()
        for raw_value in self.bot_owner_id.split(","):
            raw_value = raw_value.strip()
            if not raw_value:
                continue
            values.add(int(raw_value))
        return values

    @property
    def owner_id(self) -> int | None:
        return next(iter(self.owner_ids), None)


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        bot_token=os.getenv("BOT_TOKEN", ""),
        bot_owner_id=os.getenv("BOT_OWNER_ID", ""),
        oracle_user=os.getenv("ORACLE_USER", ""),
        oracle_password=os.getenv("ORACLE_PASSWORD", ""),
        oracle_dsn=os.getenv("ORACLE_DSN", ""),
        oracle_wallet_dir=os.getenv("ORACLE_WALLET_DIR", ""),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        dashboard_secret=os.getenv("DASHBOARD_SECRET", os.getenv("BOT_TOKEN", "change-me")),
        dashboard_public_url=os.getenv("DASHBOARD_PUBLIC_URL", "http://localhost:8000"),
        dashboard_port=int(os.getenv("DASHBOARD_PORT", "8000")),
        facebook_promo_graph_api_enabled=os.getenv("FACEBOOK_PROMO_GRAPH_API_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        facebook_graph_version=os.getenv("FACEBOOK_GRAPH_VERSION", "v24.0"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_text_model=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash-lite"),
        gemini_text_fallback_model=os.getenv("GEMINI_TEXT_FALLBACK_MODEL", "gemini-2.5-flash"),
        alibaba_api_key=os.getenv("ALIBABA_API_KEY", ""),
        alibaba_image_api_enabled=os.getenv("ALIBABA_IMAGE_API_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        alibaba_image_dry_run=os.getenv("ALIBABA_IMAGE_DRY_RUN", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        alibaba_image_admin_live_only=os.getenv("ALIBABA_IMAGE_ADMIN_LIVE_ONLY", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        alibaba_image_base_url=os.getenv("ALIBABA_IMAGE_BASE_URL", "https://dashscope-intl.aliyuncs.com/api/v1"),
        alibaba_free_monthly_image_cap=int(os.getenv("ALIBABA_FREE_MONTHLY_IMAGE_CAP", "10")),
        alibaba_paid_monthly_image_cap=int(os.getenv("ALIBABA_PAID_MONTHLY_IMAGE_CAP", "100")),
        alibaba_global_monthly_image_cap=int(os.getenv("ALIBABA_GLOBAL_MONTHLY_IMAGE_CAP", "100")),
    )

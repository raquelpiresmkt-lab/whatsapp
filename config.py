import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Evolution API
    evolution_api_url: str
    evolution_api_key: str
    webhook_secret: str

    # Meta
    meta_access_token: str
    meta_pixel_id: str          # Pixel ID (not ad account) — used in CAPI URL
    meta_ad_account_id: str = "act_896262087400762"

    # GA4
    ga4_measurement_id: str
    ga4_api_secret: str

    # Google Ads
    google_ads_yaml_path: str = "../../../credentials/google-ads.yaml"
    google_ads_customer_id: str = "6886389280"
    gads_conversion_lead: str
    gads_conversion_qualify: str
    gads_conversion_purchase: str

    # Dashboard
    dashboard_user: str
    dashboard_password: str
    dashboard_secret_key: str

    # Report Bot
    raquel_phone: str
    report_sender_instance: str

    # Saleswomen
    saleswoman_1: str = ""
    saleswoman_2: str = ""
    saleswoman_3: str = ""
    saleswoman_4: str = ""

    @property
    def saleswomen(self) -> dict[str, str]:
        """Returns {phone: name} mapping."""
        result = {}
        for raw in [self.saleswoman_1, self.saleswoman_2, self.saleswoman_3, self.saleswoman_4]:
            if raw and ":" in raw:
                name, phone = raw.split(":", 1)
                result[phone.strip()] = name.strip()
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()

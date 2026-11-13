import json
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "FailureLab API"
    app_env: str = "development"
    aws_mode: bool = False
    aws_region: str = "ap-south-1"
    database_path: str = "./data/failurelab.db"
    reports_dir: str = "./reports"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    api_key: str = ""
    dynamodb_experiments_table: str = ""
    dynamodb_resources_table: str = ""
    reports_bucket: str = ""
    sns_topic_arn: str = ""
    sqs_queue_url: str = ""
    step_function_arn: str = ""
    fis_template_map_json: str = "{}"
    enable_real_fis: bool = False
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    cloudwatch_namespace: str = "FailureLab/Lab"
    simulation_time_scale: float = 1.0
    testbed_url: str = ""
    testbed_control_token: str = "local-testbed-control-token"
    bedrock_model_id: str = ""
    bedrock_region: str = ""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
    @property
    def fis_template_map(self) -> dict[str, str]:
        try:
            value = json.loads(self.fis_template_map_json or "{}")
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

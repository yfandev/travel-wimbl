from pydantic_settings import BaseSettings, SettingsConfigDict
from wimbl.integrations.models import SUPER

class Settings(BaseSettings):
    # Real keys live only in .env.local (gitignored); later files win.
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), extra="ignore")
    crusoe_api_key: str = ""
    crusoe_base_url: str = "https://api.inference.crusoecloud.com/v1"
    crusoe_model: str = "nvidia/Nemotron-3-Super-120B-A12B"
    you_api_key: str = ""
    you_search_endpoint: str = "https://ydc-index.io/v1/search"
    you_contents_endpoint: str = "https://ydc-index.io/v1/contents"
    you_cache_enabled: bool = True
    you_cache_path: str = "./data/youcom_cache.jsonl"
    wimbl_demo_mode: bool = True
    wimbl_max_search_results: int = 6
    wimbl_max_agent_steps: int = 4
    wimbl_memory_path: str = "./data/shared_memory.jsonl"

settings = Settings()

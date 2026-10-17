from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    crusoe_api_key: str = ""
    crusoe_base_url: str = "https://api.inference.crusoecloud.com/v1"
    crusoe_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    you_api_key: str = ""
    you_search_endpoint: str = "https://api.you.com/v1/search"
    wimbl_demo_mode: bool = True
    wimbl_max_search_results: int = 6
    wimbl_max_agent_steps: int = 4
    wimbl_memory_path: str = "./data/shared_memory.jsonl"

settings = Settings()

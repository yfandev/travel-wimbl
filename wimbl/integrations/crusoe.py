from openai import AsyncOpenAI
from wimbl.config import settings

class CrusoeInference:
    """OpenAI-compatible Crusoe Managed Inference adapter."""
    def __init__(self):
        self.enabled = bool(settings.crusoe_api_key)
        self.client = AsyncOpenAI(api_key=settings.crusoe_api_key, base_url=settings.crusoe_base_url) if self.enabled else None

    async def complete(self, system: str, user: str) -> str:
        if not self.client:
            if settings.wimbl_demo_mode:
                return "Demo mode: no model call made."
            raise RuntimeError("CRUSOE_API_KEY is missing.")
        response = await self.client.chat.completions.create(
            model=settings.crusoe_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2)
        return response.choices[0].message.content or ""

import httpx

from translate_service.config import Settings
from translate_service.errors import (
    OllamaModelError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate(self, prompt: str) -> str:
        url = str(self.settings.ollama_base_url).rstrip("/") + "/api/generate"
        payload = {
            "model": self.settings.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError("Ollama request timed out") from exc
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError("Ollama service is unavailable") from exc
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError("Ollama request failed") from exc

        if response.status_code >= 400:
            raise OllamaModelError(_error_summary(response))

        data = response.json()
        try:
            return str(data["response"])
        except KeyError as exc:
            raise OllamaModelError("Ollama response did not include a response field") from exc

    async def health(self) -> dict[str, object]:
        url = str(self.settings.ollama_base_url).rstrip("/") + "/api/tags"
        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
        except httpx.TimeoutException:
            return {"ok": False, "status": "degraded", "reason": "timeout"}
        except httpx.HTTPError:
            return {"ok": False, "status": "degraded", "reason": "unavailable"}

        if response.status_code >= 400:
            return {"ok": False, "status": "degraded", "reason": f"http_{response.status_code}"}

        models = response.json().get("models", [])
        model_names = {model.get("name") for model in models}
        model_available = self.settings.ollama_model in model_names
        return {
            "ok": model_available,
            "status": "ok" if model_available else "degraded",
            "model": self.settings.ollama_model,
            "model_available": model_available,
        }


def _error_summary(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"Ollama returned HTTP {response.status_code}"
    error = data.get("error")
    if error:
        return str(error)
    return f"Ollama returned HTTP {response.status_code}"

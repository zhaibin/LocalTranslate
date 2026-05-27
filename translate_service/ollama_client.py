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

        if response.status_code >= 500:
            raise OllamaUnavailableError(_error_summary(response))
        if response.status_code >= 400:
            raise OllamaModelError(_error_summary(response))

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaModelError("Ollama returned an invalid response") from exc

        if not isinstance(data, dict):
            raise OllamaModelError("Ollama returned an invalid response")

        try:
            translated_text = data["response"]
        except KeyError as exc:
            raise OllamaModelError("Ollama response did not include a response field") from exc

        if not isinstance(translated_text, str):
            raise OllamaModelError("Ollama response field was not a string")

        return translated_text

    async def health(self) -> dict[str, object]:
        url = str(self.settings.ollama_base_url).rstrip("/") + "/api/tags"
        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
        except httpx.TimeoutException:
            return _degraded_health_response(self.settings, "timeout")
        except httpx.HTTPError:
            return _degraded_health_response(self.settings, "unavailable")

        if response.status_code >= 400:
            return _degraded_health_response(self.settings, f"http_{response.status_code}")

        try:
            data = response.json()
        except ValueError:
            return _invalid_health_response(self.settings)

        if not isinstance(data, dict):
            return _invalid_health_response(self.settings)

        models = data.get("models", [])
        if not isinstance(models, list):
            return _invalid_health_response(self.settings)

        if not all(isinstance(model, dict) for model in models):
            return _invalid_health_response(self.settings)

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
    if not isinstance(data, dict):
        return f"Ollama returned HTTP {response.status_code}"
    error = data.get("error")
    if error:
        return str(error)
    return f"Ollama returned HTTP {response.status_code}"


def _invalid_health_response(settings: Settings) -> dict[str, object]:
    return _degraded_health_response(settings, "invalid_response")


def _degraded_health_response(settings: Settings, reason: str) -> dict[str, object]:
    return {
        "ok": False,
        "status": "degraded",
        "reason": reason,
        "model": settings.ollama_model,
    }

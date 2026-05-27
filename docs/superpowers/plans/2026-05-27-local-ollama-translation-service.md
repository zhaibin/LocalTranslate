# Local Ollama Translation Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Ollama-backed translation service with shared HTTP, CLI, and MCP stdio entry points.

**Architecture:** Create a Python package named `translate_service` with one shared `TranslationService.translate()` core. HTTP routes, Typer CLI commands, and MCP tools will be thin adapters around the same service, so validation, prompt generation, Ollama calls, and error behavior stay consistent.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Typer, HTTPX, Pydantic Settings, FastMCP or MCP Python SDK, Pytest.

---

## File Structure

Create these files:

- `pyproject.toml`: Package metadata, dependencies, test settings, and console script.
- `README.md`: Local setup and usage examples for HTTP, CLI, and MCP.
- `.env.example`: Documented local configuration defaults.
- `translate_service/__init__.py`: Package exports.
- `translate_service/config.py`: Settings object and environment loading.
- `translate_service/errors.py`: Shared exception classes and error codes.
- `translate_service/language_data.tsv`: Supported language code/name table from the user-provided list.
- `translate_service/languages.py`: Language table loading, validation, lookup, and listing.
- `translate_service/prompt.py`: TranslateGemma prompt builder.
- `translate_service/ollama_client.py`: Ollama generate API client and health checks.
- `translate_service/service.py`: Shared translation orchestration.
- `translate_service/api/__init__.py`: API package marker.
- `translate_service/api/app.py`: FastAPI app factory and exception mapping.
- `translate_service/api/routes_translate.py`: `/translate` route.
- `translate_service/api/routes_system.py`: `/languages` and `/health` routes.
- `translate_service/cli.py`: Typer CLI commands.
- `translate_service/mcp_server.py`: MCP stdio tools.
- `tests/test_languages.py`: Language data tests.
- `tests/test_prompt.py`: Prompt format tests.
- `tests/test_service.py`: Core service tests with mocked Ollama.
- `tests/test_api.py`: FastAPI route tests.
- `tests/test_cli.py`: Typer CLI tests.
- `tests/test_mcp_server.py`: MCP tool registration/core-call tests.
- `tests/test_ollama_client.py`: Ollama client request/response/error tests with mocked HTTPX.

Keep language data in `language_data.tsv` instead of embedding a huge dictionary in Python code. Each line is `code<TAB>name`.

---

### Task 1: Project Skeleton and Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.env.example`
- Create: `translate_service/__init__.py`
- Create: `tests/`

- [ ] **Step 1: Create the packaging and dependency file**

Write `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "translate-service"
version = "0.1.0"
description = "Local Ollama-backed translation service for TranslateGemma"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "typer>=0.12",
  "httpx>=0.27",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "python-dotenv>=1.0",
  "mcp>=1.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "respx>=0.21",
  "ruff>=0.6",
]

[project.scripts]
translate = "translate_service.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: Create minimal documentation files**

Write `.env.example`:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=translategemma:latest
DEFAULT_SOURCE_LANG=en
DEFAULT_TARGET_LANG=zh
REQUEST_TIMEOUT_SECONDS=120
```

Write `README.md`:

````markdown
# Local Ollama Translation Service

Local translation service for Ollama and `translategemma:latest`.

## Commands

```bash
translate text --from en --to zh "Hello"
translate languages
translate serve --host 127.0.0.1 --port 8000
```

## HTTP

```bash
curl -X POST http://127.0.0.1:8000/translate \
  -H 'content-type: application/json' \
  -d '{"text":"Hello","source_lang":"en","target_lang":"zh"}'
```

## MCP

Run the MCP stdio server with:

```bash
python -m translate_service.mcp_server
```
````

Write `translate_service/__init__.py`:

```python
"""Local Ollama-backed translation service."""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 3: Run baseline tests**

Run:

```bash
pytest -q
```

Expected: pytest starts successfully and reports no tests collected or passes empty collection without import errors.

- [ ] **Step 4: Commit skeleton**

```bash
git add pyproject.toml README.md .env.example translate_service/__init__.py
git commit -m "chore: add project skeleton"
```

---

### Task 2: Configuration and Shared Errors

**Files:**
- Create: `translate_service/config.py`
- Create: `translate_service/errors.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing configuration tests**

Create `tests/test_config.py`:

```python
from translate_service.config import Settings


def test_settings_defaults():
    settings = Settings()

    assert str(settings.ollama_base_url) == "http://127.0.0.1:11434/"
    assert settings.ollama_model == "translategemma:latest"
    assert settings.default_source_lang == "en"
    assert settings.default_target_lang == "zh"
    assert settings.request_timeout_seconds == 120


def test_settings_can_be_overridden():
    settings = Settings(
        ollama_base_url="http://localhost:9999",
        ollama_model="custom:latest",
        default_source_lang="ja",
        default_target_lang="en",
        request_timeout_seconds=30,
    )

    assert str(settings.ollama_base_url) == "http://localhost:9999/"
    assert settings.ollama_model == "custom:latest"
    assert settings.default_source_lang == "ja"
    assert settings.default_target_lang == "en"
    assert settings.request_timeout_seconds == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_config.py -q
```

Expected: FAIL because `translate_service.config` does not exist.

- [ ] **Step 3: Implement settings and errors**

Create `translate_service/config.py`:

```python
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: AnyHttpUrl = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(
        default="translategemma:latest",
        validation_alias="OLLAMA_MODEL",
    )
    default_source_lang: str = Field(default="en", validation_alias="DEFAULT_SOURCE_LANG")
    default_target_lang: str = Field(default="zh", validation_alias="DEFAULT_TARGET_LANG")
    request_timeout_seconds: int = Field(
        default=120,
        validation_alias="REQUEST_TIMEOUT_SECONDS",
        ge=1,
    )
```

Create `translate_service/errors.py`:

```python
class TranslationError(Exception):
    """Base class for expected translation service errors."""

    error_code = "translation_error"


class EmptyTextError(TranslationError):
    error_code = "empty_text"


class UnsupportedLanguageError(TranslationError):
    error_code = "unsupported_language"

    def __init__(self, language_code: str):
        self.language_code = language_code
        super().__init__(f"Unsupported language code: {language_code}")


class OllamaUnavailableError(TranslationError):
    error_code = "ollama_unavailable"


class OllamaModelError(TranslationError):
    error_code = "ollama_model_error"


class OllamaTimeoutError(TranslationError):
    error_code = "ollama_timeout"
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit configuration**

```bash
git add translate_service/config.py translate_service/errors.py tests/test_config.py
git commit -m "feat: add configuration and shared errors"
```

---

### Task 3: Supported Language Data

**Files:**
- Create: `translate_service/language_data.tsv`
- Create: `translate_service/languages.py`
- Test: `tests/test_languages.py`

- [ ] **Step 1: Write failing language tests**

Create `tests/test_languages.py`:

```python
import pytest

from translate_service.errors import UnsupportedLanguageError
from translate_service.languages import get_language, list_languages, validate_language_code


def test_get_language_supports_base_region_and_script_variants():
    assert get_language("en") == {"code": "en", "name": "English"}
    assert get_language("en-GB") == {"code": "en-GB", "name": "English"}
    assert get_language("zh-Hans") == {"code": "zh-Hans", "name": "Chinese"}
    assert get_language("zh-Hant-HK") == {"code": "zh-Hant-HK", "name": "Chinese"}


def test_language_matching_is_exact_and_case_sensitive():
    with pytest.raises(UnsupportedLanguageError):
        validate_language_code("EN")


def test_invalid_language_raises_clear_error():
    with pytest.raises(UnsupportedLanguageError) as exc_info:
        validate_language_code("xx-Unknown")

    assert exc_info.value.language_code == "xx-Unknown"


def test_list_languages_contains_expected_entries():
    languages = list_languages()

    assert {"code": "en", "name": "English"} in languages
    assert {"code": "zh", "name": "Chinese"} in languages
    assert {"code": "ja", "name": "Japanese"} in languages
    assert len(languages) > 300
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_languages.py -q
```

Expected: FAIL because `translate_service.languages` does not exist.

- [ ] **Step 3: Create the language data file**

Create `translate_service/language_data.tsv` by copying the full supported language table supplied in the approved brainstorming conversation. Preserve exact codes and names. The file must include at least these lines and all other provided lines:

```text
aa	Afar
en	English
en-GB	English
ja	Japanese
zh	Chinese
zh-Hans	Chinese
zh-Hant-HK	Chinese
zu-ZA	Zulu
```

Each line must contain exactly one language code, one tab, and one language display name. Do not normalize case.

- [ ] **Step 4: Implement language helpers**

Create `translate_service/languages.py`:

```python
from functools import lru_cache
from importlib.resources import files

from translate_service.errors import UnsupportedLanguageError


@lru_cache(maxsize=1)
def _language_map() -> dict[str, str]:
    data_path = files("translate_service").joinpath("language_data.tsv")
    languages: dict[str, str] = {}
    for line_number, raw_line in enumerate(data_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            code, name = line.split("\t", 1)
        except ValueError as exc:
            raise ValueError(f"Invalid language data line {line_number}: {raw_line!r}") from exc
        languages[code] = name
    return languages


def validate_language_code(code: str) -> str:
    if code not in _language_map():
        raise UnsupportedLanguageError(code)
    return code


def get_language(code: str) -> dict[str, str]:
    validate_language_code(code)
    return {"code": code, "name": _language_map()[code]}


def list_languages() -> list[dict[str, str]]:
    return [{"code": code, "name": name} for code, name in _language_map().items()]
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_languages.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit language support**

```bash
git add translate_service/language_data.tsv translate_service/languages.py tests/test_languages.py
git commit -m "feat: add supported language table"
```

---

### Task 4: TranslateGemma Prompt Builder

**Files:**
- Create: `translate_service/prompt.py`
- Test: `tests/test_prompt.py`

- [ ] **Step 1: Write failing prompt tests**

Create `tests/test_prompt.py`:

```python
from translate_service.prompt import build_prompt


def test_build_prompt_uses_exact_translategemma_format():
    prompt = build_prompt(
        source_name="English",
        source_code="en",
        target_name="Chinese",
        target_code="zh",
        text="Hello",
    )

    assert prompt == (
        "You are a professional English (en) to Chinese (zh) translator. "
        "Your goal is to accurately convey the meaning and nuances of the original English "
        "text while adhering to Chinese grammar, vocabulary, and cultural sensitivities.\n"
        "Produce only the Chinese translation, without any additional explanations or commentary. "
        "Please translate the following English text into Chinese:\n\n\n"
        "Hello"
    )


def test_build_prompt_preserves_source_text_internal_whitespace():
    prompt = build_prompt(
        source_name="English",
        source_code="en",
        target_name="Japanese",
        target_code="ja",
        text="Line 1\n\nLine 2",
    )

    assert prompt.endswith(":\n\n\nLine 1\n\nLine 2")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_prompt.py -q
```

Expected: FAIL because `translate_service.prompt` does not exist.

- [ ] **Step 3: Implement prompt builder**

Create `translate_service/prompt.py`:

```python
def build_prompt(
    *,
    source_name: str,
    source_code: str,
    target_name: str,
    target_code: str,
    text: str,
) -> str:
    return (
        f"You are a professional {source_name} ({source_code}) to "
        f"{target_name} ({target_code}) translator. Your goal is to accurately convey "
        f"the meaning and nuances of the original {source_name} text while adhering to "
        f"{target_name} grammar, vocabulary, and cultural sensitivities.\n"
        f"Produce only the {target_name} translation, without any additional explanations "
        f"or commentary. Please translate the following {source_name} text into "
        f"{target_name}:\n\n\n"
        f"{text}"
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_prompt.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit prompt builder**

```bash
git add translate_service/prompt.py tests/test_prompt.py
git commit -m "feat: add translategemma prompt builder"
```

---

### Task 5: Ollama Client

**Files:**
- Create: `translate_service/ollama_client.py`
- Test: `tests/test_ollama_client.py`

- [ ] **Step 1: Write failing Ollama client tests**

Create `tests/test_ollama_client.py`:

```python
import httpx
import pytest
import respx

from translate_service.config import Settings
from translate_service.errors import OllamaModelError, OllamaTimeoutError, OllamaUnavailableError
from translate_service.ollama_client import OllamaClient


@pytest.mark.asyncio
@respx.mock
async def test_generate_posts_to_ollama_generate_api():
    route = respx.post("http://127.0.0.1:11434/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "你好", "done": True})
    )
    client = OllamaClient(Settings())

    result = await client.generate("prompt")

    assert result == "你好"
    assert route.calls[0].request.content == (
        b'{"model":"translategemma:latest","prompt":"prompt","stream":false}'
    )


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_non_200_to_model_error():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        return_value=httpx.Response(404, json={"error": "model not found"})
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaModelError):
        await client.generate("prompt")


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_timeout():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaTimeoutError):
        await client.generate("prompt")


@pytest.mark.asyncio
@respx.mock
async def test_generate_maps_connect_error():
    respx.post("http://127.0.0.1:11434/api/generate").mock(
        side_effect=httpx.ConnectError("no service")
    )
    client = OllamaClient(Settings())

    with pytest.raises(OllamaUnavailableError):
        await client.generate("prompt")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ollama_client.py -q
```

Expected: FAIL because `translate_service.ollama_client` does not exist.

- [ ] **Step 3: Implement Ollama client**

Create `translate_service/ollama_client.py`:

```python
import httpx

from translate_service.config import Settings
from translate_service.errors import OllamaModelError, OllamaTimeoutError, OllamaUnavailableError


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
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_ollama_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Ollama client**

```bash
git add translate_service/ollama_client.py tests/test_ollama_client.py
git commit -m "feat: add ollama client"
```

---

### Task 6: Core Translation Service

**Files:**
- Create: `translate_service/service.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_service.py`:

```python
import pytest

from translate_service.config import Settings
from translate_service.errors import EmptyTextError, UnsupportedLanguageError
from translate_service.service import TranslationService


class FakeOllamaClient:
    def __init__(self, result: str = "  你好  "):
        self.result = result
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.result

    async def health(self) -> dict[str, object]:
        return {"ok": True, "status": "ok", "model": "translategemma:latest"}


@pytest.mark.asyncio
async def test_translate_uses_defaults_and_returns_normalized_result():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    result = await service.translate(text="Hello")

    assert result == {
        "translation": "你好",
        "source_lang": {"code": "en", "name": "English"},
        "target_lang": {"code": "zh", "name": "Chinese"},
        "model": "translategemma:latest",
    }
    assert client.prompts[0].endswith(":\n\n\nHello")


@pytest.mark.asyncio
async def test_translate_accepts_explicit_languages():
    service = TranslationService(Settings(), FakeOllamaClient("こんにちは"))

    result = await service.translate(text="Hello", source_lang="en", target_lang="ja")

    assert result["target_lang"] == {"code": "ja", "name": "Japanese"}
    assert result["translation"] == "こんにちは"


@pytest.mark.asyncio
async def test_translate_rejects_empty_text_before_ollama_call():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    with pytest.raises(EmptyTextError):
        await service.translate(text="   ")

    assert client.prompts == []


@pytest.mark.asyncio
async def test_translate_rejects_unsupported_language_before_ollama_call():
    client = FakeOllamaClient()
    service = TranslationService(Settings(), client)

    with pytest.raises(UnsupportedLanguageError):
        await service.translate(text="Hello", source_lang="EN", target_lang="zh")

    assert client.prompts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_service.py -q
```

Expected: FAIL because `translate_service.service` does not exist.

- [ ] **Step 3: Implement core service**

Create `translate_service/service.py`:

```python
from typing import Protocol

from translate_service.config import Settings
from translate_service.errors import EmptyTextError
from translate_service.languages import get_language
from translate_service.prompt import build_prompt


class OllamaLike(Protocol):
    async def generate(self, prompt: str) -> str: ...

    async def health(self) -> dict[str, object]: ...


class TranslationService:
    def __init__(self, settings: Settings, ollama_client: OllamaLike):
        self.settings = settings
        self.ollama_client = ollama_client

    async def translate(
        self,
        *,
        text: str,
        source_lang: str | None = None,
        target_lang: str | None = None,
    ) -> dict[str, object]:
        if not text.strip():
            raise EmptyTextError("Text to translate cannot be empty")

        source = get_language(source_lang or self.settings.default_source_lang)
        target = get_language(target_lang or self.settings.default_target_lang)
        prompt = build_prompt(
            source_name=source["name"],
            source_code=source["code"],
            target_name=target["name"],
            target_code=target["code"],
            text=text,
        )
        translation = (await self.ollama_client.generate(prompt)).strip()
        return {
            "translation": translation,
            "source_lang": source,
            "target_lang": target,
            "model": self.settings.ollama_model,
        }

    async def health(self) -> dict[str, object]:
        ollama_health = await self.ollama_client.health()
        return {
            "status": "ok" if ollama_health.get("ok") else "degraded",
            "model": self.settings.ollama_model,
            "ollama": ollama_health,
        }
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_service.py tests/test_prompt.py tests/test_languages.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit core service**

```bash
git add translate_service/service.py tests/test_service.py
git commit -m "feat: add core translation service"
```

---

### Task 7: HTTP API

**Files:**
- Create: `translate_service/api/__init__.py`
- Create: `translate_service/api/app.py`
- Create: `translate_service/api/routes_translate.py`
- Create: `translate_service/api/routes_system.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from translate_service.api.app import create_app


class FakeService:
    async def translate(self, *, text: str, source_lang: str | None = None, target_lang: str | None = None):
        if text == "boom":
            raise RuntimeError("unexpected")
        return {
            "translation": "你好",
            "source_lang": {"code": source_lang or "en", "name": "English"},
            "target_lang": {"code": target_lang or "zh", "name": "Chinese"},
            "model": "translategemma:latest",
        }

    async def health(self):
        return {"status": "ok", "model": "translategemma:latest", "ollama": {"ok": True}}


def test_translate_route_returns_translation():
    client = TestClient(create_app(FakeService()))

    response = client.post("/translate", json={"text": "Hello", "source_lang": "en", "target_lang": "zh"})

    assert response.status_code == 200
    assert response.json()["translation"] == "你好"


def test_languages_route_returns_supported_languages():
    client = TestClient(create_app(FakeService()))

    response = client.get("/languages")

    assert response.status_code == 200
    assert {"code": "zh-Hans", "name": "Chinese"} in response.json()["languages"]


def test_health_route_returns_status():
    client = TestClient(create_app(FakeService()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_api.py -q
```

Expected: FAIL because API modules do not exist.

- [ ] **Step 3: Implement API app and routes**

Create `translate_service/api/__init__.py`:

```python
"""HTTP API for the translation service."""
```

Create `translate_service/api/app.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from translate_service.config import Settings
from translate_service.errors import (
    EmptyTextError,
    OllamaModelError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    UnsupportedLanguageError,
)
from translate_service.ollama_client import OllamaClient
from translate_service.service import TranslationService


def create_app(service: TranslationService | None = None) -> FastAPI:
    app = FastAPI(title="Local Ollama Translation Service")
    app.state.translation_service = service or TranslationService(Settings(), OllamaClient(Settings()))

    from translate_service.api.routes_system import router as system_router
    from translate_service.api.routes_translate import router as translate_router

    app.include_router(translate_router)
    app.include_router(system_router)
    register_exception_handlers(app)
    return app


def get_service(request: Request) -> TranslationService:
    return request.app.state.translation_service


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EmptyTextError)
    async def empty_text_handler(_request: Request, exc: EmptyTextError):
        return JSONResponse(status_code=400, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(UnsupportedLanguageError)
    async def unsupported_language_handler(_request: Request, exc: UnsupportedLanguageError):
        return JSONResponse(status_code=400, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(OllamaUnavailableError)
    async def unavailable_handler(_request: Request, exc: OllamaUnavailableError):
        return JSONResponse(status_code=503, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(OllamaModelError)
    async def model_handler(_request: Request, exc: OllamaModelError):
        return JSONResponse(status_code=502, content={"error": exc.error_code, "message": str(exc)})

    @app.exception_handler(OllamaTimeoutError)
    async def timeout_handler(_request: Request, exc: OllamaTimeoutError):
        return JSONResponse(status_code=504, content={"error": exc.error_code, "message": str(exc)})
```

Create `translate_service/api/routes_translate.py`:

```python
from fastapi import APIRouter, Request
from pydantic import BaseModel

from translate_service.api.app import get_service

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    source_lang: str | None = None
    target_lang: str | None = None


@router.post("/translate")
async def translate(request: Request, body: TranslateRequest):
    service = get_service(request)
    return await service.translate(
        text=body.text,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
    )
```

Create `translate_service/api/routes_system.py`:

```python
from fastapi import APIRouter, Request

from translate_service.api.app import get_service
from translate_service.languages import list_languages

router = APIRouter()


@router.get("/languages")
async def languages():
    return {"languages": list_languages()}


@router.get("/health")
async def health(request: Request):
    return await get_service(request).health()
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit HTTP API**

```bash
git add translate_service/api tests/test_api.py
git commit -m "feat: add http api"
```

---

### Task 8: CLI

**Files:**
- Create: `translate_service/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from translate_service.cli import app

runner = CliRunner()


def test_languages_command_lists_languages():
    result = runner.invoke(app, ["languages"])

    assert result.exit_code == 0
    assert "zh-Hans" in result.stdout


def test_text_command_requires_text():
    result = runner.invoke(app, ["text", "--from", "en", "--to", "zh", ""])

    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_cli.py -q
```

Expected: FAIL because `translate_service.cli` does not exist.

- [ ] **Step 3: Implement CLI**

Create `translate_service/cli.py`:

```python
import asyncio
import json

import typer
import uvicorn

from translate_service.api.app import create_app
from translate_service.config import Settings
from translate_service.errors import TranslationError
from translate_service.languages import list_languages
from translate_service.ollama_client import OllamaClient
from translate_service.service import TranslationService

app = typer.Typer(no_args_is_help=True)


def _service() -> TranslationService:
    settings = Settings()
    return TranslationService(settings, OllamaClient(settings))


@app.command()
def text(
    value: str = typer.Argument(...),
    source_lang: str | None = typer.Option(None, "--from"),
    target_lang: str | None = typer.Option(None, "--to"),
):
    async def run():
        result = await _service().translate(
            text=value,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        typer.echo(result["translation"])

    try:
        asyncio.run(run())
    except TranslationError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def languages():
    typer.echo(json.dumps({"languages": list_languages()}, ensure_ascii=False, indent=2))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run(create_app(), host=host, port=port)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit CLI**

```bash
git add translate_service/cli.py tests/test_cli.py
git commit -m "feat: add cli"
```

---

### Task 9: MCP Server

**Files:**
- Create: `translate_service/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing MCP tests**

Create `tests/test_mcp_server.py`:

```python
from translate_service.mcp_server import create_mcp_server


def test_mcp_server_can_be_created():
    server = create_mcp_server()

    assert server.name == "local-ollama-translation-service"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mcp_server.py -q
```

Expected: FAIL because `translate_service.mcp_server` does not exist.

- [ ] **Step 3: Implement MCP server**

Create `translate_service/mcp_server.py`:

```python
from mcp.server.fastmcp import FastMCP

from translate_service.config import Settings
from translate_service.languages import list_languages
from translate_service.ollama_client import OllamaClient
from translate_service.service import TranslationService


def _service() -> TranslationService:
    settings = Settings()
    return TranslationService(settings, OllamaClient(settings))


def create_mcp_server() -> FastMCP:
    mcp = FastMCP("local-ollama-translation-service")

    @mcp.tool()
    async def translate_text(
        text: str,
        source_lang: str | None = None,
        target_lang: str | None = None,
    ) -> dict[str, object]:
        """Translate text with local Ollama and TranslateGemma."""
        return await _service().translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
        )

    @mcp.tool()
    def list_supported_languages() -> dict[str, object]:
        """List supported source and target language codes."""
        return {"languages": list_languages()}

    @mcp.tool()
    async def health() -> dict[str, object]:
        """Check local Ollama and model status."""
        return await _service().health()

    return mcp


if __name__ == "__main__":
    create_mcp_server().run()
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_mcp_server.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit MCP server**

```bash
git add translate_service/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add mcp server"
```

---

### Task 10: Full Verification and Documentation Polish

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

- [ ] **Step 1: Run the full automated test suite**

Run:

```bash
pytest -q
```

Expected: PASS for all tests.

- [ ] **Step 2: Run linting**

Run:

```bash
ruff check .
```

Expected: PASS.

- [ ] **Step 3: Manually verify prompt contract from Python**

Run:

```bash
python -c 'from translate_service.prompt import build_prompt; p=build_prompt(source_name="English",source_code="en",target_name="Chinese",target_code="zh",text="Hello"); print(repr(p[-12:]))'
```

Expected output includes:

```text
':\n\n\nHello'
```

- [ ] **Step 4: Optionally verify with real Ollama**

Run only if Ollama is running and `translategemma:latest` is installed:

```bash
translate text --from en --to zh "Hello"
```

Expected: A Chinese translation with no commentary.

- [ ] **Step 5: Commit final polish if docs changed**

```bash
git add README.md .env.example
git commit -m "docs: add usage notes"
```

If no docs changed, skip this commit.

---

## Plan Self-Review

Spec coverage:

- Shared core service: Task 6.
- HTTP API: Task 7.
- CLI: Task 8.
- MCP stdio server: Task 9.
- Config defaults including `translategemma:latest`: Task 2.
- Supported language validation and listing: Task 3.
- Exact TranslateGemma prompt and two blank lines before text: Task 4 and Task 10.
- Ollama generate API and health behavior: Task 5.
- Error mapping: Tasks 2, 5, 6, and 7.
- Tests across languages, prompt, service, API, CLI, MCP, and Ollama client: Tasks 3 through 10.

Placeholder scan:

- No placeholder phrases remain.
- The only large external data step is the supported language TSV, which is explicitly sourced from the user-approved language list and represented as concrete `code<TAB>name` data.

Type consistency:

- Core method is consistently `TranslationService.translate(text=..., source_lang=..., target_lang=...)`.
- Result shape is consistently `translation`, `source_lang`, `target_lang`, and `model`.
- MCP tools and HTTP routes use the same source/target parameter names.

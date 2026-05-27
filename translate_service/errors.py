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

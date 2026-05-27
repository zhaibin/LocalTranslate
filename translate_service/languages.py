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

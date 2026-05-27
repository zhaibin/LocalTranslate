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

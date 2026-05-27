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

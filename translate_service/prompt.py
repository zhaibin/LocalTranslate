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

import os
import time

import anthropic

from src.config import (
    MODEL_DEFAULT,
    CLAUDE_MAX_RETRIES,
    CLAUDE_DEFAULT_MAX_TOKENS,
    CLAUDE_RETRY_BACKOFF_BASE,
)

_client = anthropic.Anthropic(
    base_url=os.environ["AZURE_CLAUDE_ENDPOINT"],
    api_key=os.environ["AZURE_CLAUDE_API_KEY"],
    default_headers={
        "api-key": os.environ["AZURE_CLAUDE_API_KEY"],
        "api-version": "2024-10-01",
    },
)


def analyze(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call Claude via Azure AI Foundry. Returns response text."""
    use_model = model or MODEL_DEFAULT
    use_tokens = max_tokens or CLAUDE_DEFAULT_MAX_TOKENS
    last_err = None

    for attempt in range(CLAUDE_MAX_RETRIES):
        try:
            with _client.messages.stream(
                model=use_model,
                max_tokens=use_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                return stream.get_final_text().strip()
        except Exception as e:
            last_err = e
            wait = CLAUDE_RETRY_BACKOFF_BASE * (2 ** attempt)
            print(f"  [retry {attempt + 1}/{CLAUDE_MAX_RETRIES}] Claude error ({use_model}): {e} — waiting {wait}s")
            time.sleep(wait)

    raise last_err

import os
import time

import anthropic

from src.config2 import (
    MODEL_DEFAULT,
    CLAUDE_MAX_RETRIES,
    CLAUDE_DEFAULT_MAX_TOKENS,
    CLAUDE_RETRY_BACKOFF_BASE,
)
from src.org import API_ENDPOINTS

_client = anthropic.Anthropic(
    base_url=os.environ["AZURE_CLAUDE_ENDPOINT"],
    api_key=os.environ["AZURE_CLAUDE_API_KEY"],
    default_headers={
        API_ENDPOINTS["azure_auth_header"]: os.environ["AZURE_CLAUDE_API_KEY"],
        "api-version": API_ENDPOINTS["azure_api_version"],
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

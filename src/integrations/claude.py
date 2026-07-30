import os
import time

from openai import AzureOpenAI

from src.config2 import (
    MODEL_DEFAULT,
    CLAUDE_MAX_RETRIES,
    CLAUDE_DEFAULT_MAX_TOKENS,
    CLAUDE_RETRY_BACKOFF_BASE,
)
from src.org import API_ENDPOINTS

_client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_CLAUDE_ENDPOINT"],
    api_key=os.environ["AZURE_CLAUDE_API_KEY"],
    api_version=API_ENDPOINTS["azure_api_version"],
)


def analyze(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call LLM via Azure AI Foundry. Returns response text."""
    use_model = model or MODEL_DEFAULT
    use_tokens = max_tokens or CLAUDE_DEFAULT_MAX_TOKENS
    last_err = None

    for attempt in range(CLAUDE_MAX_RETRIES):
        try:
            response = _client.chat.completions.create(
                model=use_model,
                max_tokens=use_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
            wait = CLAUDE_RETRY_BACKOFF_BASE * (2 ** attempt)
            print(f"  [retry {attempt + 1}/{CLAUDE_MAX_RETRIES}] AI error ({use_model}): {e} — waiting {wait}s")
            time.sleep(wait)

    raise last_err

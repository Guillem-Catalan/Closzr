import os
import re
import time

from anthropic import AnthropicFoundry

from src.config2 import (
    MODEL_DEFAULT,
    CLAUDE_MAX_RETRIES,
    CLAUDE_DEFAULT_MAX_TOKENS,
    CLAUDE_RETRY_BACKOFF_BASE,
)


def _resource_name() -> str:
    endpoint = os.environ.get("AZURE_CLAUDE_ENDPOINT", "")
    m = re.match(r"https://([^.]+)\.", endpoint)
    if m:
        return m.group(1)
    return endpoint


_client = AnthropicFoundry(
    api_key=os.environ["AZURE_CLAUDE_API_KEY"],
    resource=_resource_name(),
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
            response = _client.messages.create(
                model=use_model,
                max_tokens=use_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.content[0].text
        except Exception as e:
            last_err = e
            wait = CLAUDE_RETRY_BACKOFF_BASE * (2 ** attempt)
            print(f"  [retry {attempt + 1}/{CLAUDE_MAX_RETRIES}] AI error ({use_model}): {e} — waiting {wait}s")
            time.sleep(wait)

    raise last_err

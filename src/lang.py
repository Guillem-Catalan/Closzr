"""
Language helper — returns the language instruction to append to any system prompt.

Usage:
    from src.lang import get_lang_prompt
    system_prompt += "\n\n" + get_lang_prompt(team)
"""

from src.config import PARTNER_IDENTITY, DS_IDENTITY, XL_IDENTITY, PROMPTS_DIR


def _resolve_lang_file(team: str) -> str:
    if team in PARTNER_IDENTITY:
        return PARTNER_IDENTITY[team].get("lang_file", "lang/es.txt")
    if team == "XL":
        return XL_IDENTITY.get("xl_sales", {}).get("lang_file", "lang/es.txt")
    return DS_IDENTITY.get("direct_sales_es", {}).get("lang_file", "lang/es.txt")


def get_lang_prompt(team: str) -> str:
    """Return the language instruction text for a team, or empty string if not found."""
    lang_file = _resolve_lang_file(team)
    path = PROMPTS_DIR / lang_file
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""

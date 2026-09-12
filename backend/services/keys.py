import os


def candidate_keys():
    """API keys in priority order: user's own OpenAI key first, then the Emergent universal key."""
    keys = []
    if os.environ.get("OPENAI_API_KEY", "").strip():
        keys.append(os.environ["OPENAI_API_KEY"].strip())
    if os.environ.get("EMERGENT_LLM_KEY", "").strip():
        keys.append(os.environ["EMERGENT_LLM_KEY"].strip())
    return keys


def is_emergent(key):
    return key.startswith("sk-emergent-")

"""12 · llm — Groq primary with OpenAI fallback."""

import litellm
from langchain_litellm import ChatLiteLLMRouter
from litellm import Router

from hr_assistant import config

litellm.drop_params = True

_PRIMARY_GROUP = "hr-llm"
_FALLBACK_GROUP = "hr-llm-fallback"
_router: Router | None = None


def _get_router() -> Router:
    global _router
    if _router is None:
        _router = Router(
            model_list=[
                {
                    "model_name": _PRIMARY_GROUP,
                    "litellm_params": {
                        "model": f"groq/{config.LLM_MODEL_NAME}",
                        "api_key": config.GROQ_API_KEY,
                    },
                },
                {
                    "model_name": _FALLBACK_GROUP,
                    "litellm_params": {
                        "model": f"openai/{config.FALLBACK_MODEL_NAME}",
                        "api_key": config.OPENAI_API_KEY,
                    },
                },
            ],
            num_retries=2,
            fallbacks=[{_PRIMARY_GROUP: [_FALLBACK_GROUP]}],
        )
    return _router


def get_llm():
    """Return Groq chat with OpenAI failover for agents and safety checks."""
    return ChatLiteLLMRouter(
        router=_get_router(),
        model_name=_PRIMARY_GROUP,
        temperature=0,
    )

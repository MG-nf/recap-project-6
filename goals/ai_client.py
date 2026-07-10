import openai
from django.conf import settings


class AIConfigurationError(Exception):
    pass


def get_client():
    if not settings.OPENAI_API_KEY:
        raise AIConfigurationError("OPENAI_API_KEY is not configured.")
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)

"""07 · embeddings — create vectors with OpenAI."""

from langchain_openai import OpenAIEmbeddings

from hr_assistant import config


def get_embeddings_model():
    """Return OpenAI's hosted embedding model."""
    return OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL_NAME,
        api_key=config.OPENAI_API_KEY,
    )

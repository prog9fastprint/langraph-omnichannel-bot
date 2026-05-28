from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings
import logging

logger = logging.getLogger(__name__)

class LLMFallbackWrapper:
    def __init__(self):
        self.primary_llm = ChatOpenAI(
            model=settings.OPENROUTER_PRIMARY_MODEL,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=settings.OPENROUTER_API_KEY,
            temperature=0.7
        )
        self.fallback_models = settings.OPENROUTER_FALLBACK_MODELS.split(",")
        self.gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.7,
            google_api_key=settings.GEMINI_API_KEY
        )

    def invoke(self, messages, **kwargs):
        # 1. Attempt Primary
        try:
            return self.primary_llm.invoke(messages, **kwargs)
        except Exception as e:
            logger.warning(f"Primary model {settings.OPENROUTER_PRIMARY_MODEL} failed: {e}")
        
        # 2. Attempt Fallbacks
        for model in self.fallback_models:
            try:
                llm = ChatOpenAI(
                    model=model.strip(),
                    openai_api_base="https://openrouter.ai/api/v1",
                    openai_api_key=settings.OPENROUTER_API_KEY,
                    temperature=0.7
                )
                return llm.invoke(messages, **kwargs)
            except Exception as e:
                logger.warning(f"Fallback model {model} failed: {e}")

        # 3. Final Fallback to Gemini
        logger.error("All OpenRouter models failed, trying Gemini.")
        return self.gemini_llm.invoke(messages, **kwargs)

    async def ainvoke(self, messages, **kwargs):
        # 1. Attempt Primary
        try:
            return await self.primary_llm.ainvoke(messages, **kwargs)
        except Exception as e:
            logger.warning(f"Primary model {settings.OPENROUTER_PRIMARY_MODEL} failed: {e}")
        
        # 2. Attempt Fallbacks
        for model in self.fallback_models:
            try:
                llm = ChatOpenAI(
                    model=model.strip(),
                    openai_api_base="https://openrouter.ai/api/v1",
                    openai_api_key=settings.OPENROUTER_API_KEY,
                    temperature=0.7
                )
                return await llm.ainvoke(messages, **kwargs)
            except Exception as e:
                logger.warning(f"Fallback model {model} failed: {e}")

        # 3. Final Fallback to Gemini
        logger.error("All OpenRouter models failed, trying Gemini.")
        return await self.gemini_llm.ainvoke(messages, **kwargs)

    def bind_tools(self, tools, **kwargs):
        self.primary_llm = self.primary_llm.bind_tools(tools, **kwargs)
        self.gemini_llm = self.gemini_llm.bind_tools(tools, **kwargs)
        return self

    def with_structured_output(self, schema, **kwargs):
        # Delegate structured output to primary LLM
        return self.primary_llm.with_structured_output(schema, **kwargs)

llm = LLMFallbackWrapper()

from langchain_ollama import OllamaLLM


def get_llm(model: str = "llama3.1:8b", temperature: float = 0.2) -> OllamaLLM:
    return OllamaLLM(model=model, temperature=temperature, format="json")

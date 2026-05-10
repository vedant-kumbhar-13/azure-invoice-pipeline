from functools import lru_cache
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from app.config import settings


# BUG-25: Singleton client — reuses connection pool instead of creating a new
# HTTP client on every invoice. Massive latency and resource improvement.
@lru_cache(maxsize=1)
def _get_client() -> DocumentIntelligenceClient:
    return DocumentIntelligenceClient(
        endpoint=settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
        credential=AzureKeyCredential(settings.AZURE_DOCUMENT_INTELLIGENCE_KEY),
    )


def analyze_invoice(file_url: str) -> dict:
    """Sends the invoice URL to Azure AI and returns the raw extracted fields."""
    client = _get_client()

    poller = client.begin_analyze_document(
        "prebuilt-invoice",
        AnalyzeDocumentRequest(url_source=file_url),
        locale="en-IN"
    )

    result = poller.result()

    if result.documents:
        return result.documents[0].fields

    return {}
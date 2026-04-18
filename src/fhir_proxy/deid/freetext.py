from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from fhir_proxy.deid.token_store import TokenStore

PHI_ENTITY_TYPES = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "LOCATION",
    "DATE_TIME",
    "US_SSN",
    "MEDICAL_LICENSE",
    "URL",
]


def build_analyzer() -> AnalyzerEngine:
    """Build and return a new AnalyzerEngine (expensive -- loads spacy model)."""
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    })
    return AnalyzerEngine(nlp_engine=provider.create_engine())


class FreetextDeidentifier:
    def __init__(self, token_store: TokenStore, analyzer: AnalyzerEngine | None = None):
        self.token_store = token_store
        self.analyzer = analyzer if analyzer is not None else build_analyzer()

    def deidentify(self, text: str) -> str:
        if not text:
            return text
        results = self.analyzer.analyze(
            text=text,
            entities=PHI_ENTITY_TYPES,
            language="en",
            score_threshold=0.7,
        )
        results = sorted(results, key=lambda r: r.start, reverse=True)
        deidentified = text
        for result in results:
            original = text[result.start:result.end]
            phi_type = result.entity_type.lower()
            token = self.token_store.tokenize(original, phi_type)
            deidentified = deidentified[:result.start] + token + deidentified[result.end:]
        return deidentified

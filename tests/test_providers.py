from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from vendorproof.models import AuditReport, ClaimCandidate, SourceRecord, Verdict
from vendorproof.providers import (
    GeminiClaimExtractor,
    GeminiEvidenceJudge,
    SerpApiSearchGateway,
    XanoSnapshotStore,
)


def source() -> SourceRecord:
    return SourceRecord(
        title="Current source",
        url="https://example.com/current",
        snippet="Current evidence.",
        source="Example",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )


class FakeSerpClient:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def search(self, params: dict[str, object]) -> object:
        self.calls.append(params)
        response = self.responses[params["engine"]]
        if isinstance(response, Exception):
            raise response
        return response


def test_serpapi_gateway_searches_web_and_news_and_deduplicates() -> None:
    shared = "https://vendor.example/pricing"
    client = FakeSerpClient(
        {
            "google_light": {
                "search_metadata": {"id": "web-123"},
                "organic_results": [
                    {
                        "title": "Vendor pricing",
                        "link": shared,
                        "snippet": "$20 per user",
                        "displayed_link": "vendor.example",
                    },
                    {"title": "Unsafe", "link": "file:///tmp/result"},
                ],
            },
            "google_news": {
                "search_metadata": {"id": "news-456"},
                "news_results": [
                    {"title": "Duplicate", "link": shared},
                    {
                        "title": "Recent outage",
                        "link": "https://news.example/outage",
                        "snippet": "The service recovered.",
                        "source": {"name": "Example News"},
                        "date": "2 days ago",
                    },
                ],
            },
        }
    )
    gateway = SerpApiSearchGateway(client=client, results_per_engine=5)

    results = gateway.search("Vendor price and recent reliability")

    assert [call["engine"] for call in client.calls] == [
        "google_light",
        "google_news",
    ]
    assert client.calls[0]["num"] == 5
    assert "num" not in client.calls[1]
    assert [str(result.url) for result in results] == [
        shared,
        "https://news.example/outage",
    ]
    assert results[0].search_id == "web-123"
    assert results[1].source == "Example News"
    assert results[1].published_at == "2 days ago"


def test_serpapi_gateway_keeps_partial_results_and_fails_when_both_fail() -> None:
    partial = FakeSerpClient(
        {
            "google_light": RuntimeError("web failed"),
            "google_news": {
                "news_results": [
                    {"title": "News", "link": "https://news.example/current"}
                ]
            },
        }
    )
    assert len(SerpApiSearchGateway(client=partial).search("query")) == 1

    failed = FakeSerpClient(
        {
            "google_light": RuntimeError("web failed"),
            "google_news": {"error": "quota exceeded"},
        }
    )
    with pytest.raises(RuntimeError, match="web and news"):
        SerpApiSearchGateway(client=failed).search("query")


def test_serpapi_gateway_validates_configuration() -> None:
    with pytest.raises(ValueError, match="SERPAPI_API_KEY"):
        SerpApiSearchGateway()
    with pytest.raises(ValueError, match="between 1 and 10"):
        SerpApiSearchGateway(client=FakeSerpClient({}), results_per_engine=11)


class FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.checked = False

    def raise_for_status(self) -> None:
        self.checked = True

    def json(self) -> dict[str, object]:
        return self.payload


class FakeHttpClient:
    def __init__(self, response: FakeHttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post(self, url: str, **kwargs: object) -> FakeHttpResponse:
        self.calls.append((url, kwargs))
        return self.response


def test_xano_store_posts_complete_report_and_validates_receipt() -> None:
    response = FakeHttpResponse(
        {
            "snapshot_id": "42",
            "previous_snapshot_id": "37",
            "changed_claims": 2,
        }
    )
    client = FakeHttpClient(response)
    store = XanoSnapshotStore(
        "https://example.xano.io/api:snapshot",
        api_token="server-token",
        client=client,
    )
    report = AuditReport(
        generated_at=datetime.now(UTC), overall_action="review", claims=[]
    )

    receipt = store.save("Compare Acme", report)

    assert receipt.snapshot_id == "42"
    assert response.checked is True
    _, options = client.calls[0]
    assert options["json"]["brief"] == "Compare Acme"
    assert options["headers"]["Authorization"] == "Bearer server-token"
    assert options["timeout"] == 20


def test_xano_store_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        XanoSnapshotStore("http://example.xano.io/api:snapshot")


class FakeModels:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_gemini_extractor_uses_structured_claim_batch() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"text":"Acme supports SSO",'
            '"query":"Acme SSO plan pricing",'
            '"why_check":"Plan limits can change","priority":5}]}'
        ),
        parsed=None,
    )
    models = FakeModels([response])
    extractor = GeminiClaimExtractor(SimpleNamespace(models=models), "gemini-test")

    claims = extractor.extract("Compare Acme for a five-person team.")

    assert claims[0].text == "Acme supports SSO"
    assert models.calls[0]["model"] == "gemini-test"
    assert "untrusted data" in models.calls[0]["contents"]


def test_gemini_judge_handles_no_sources_without_model_call() -> None:
    models = FakeModels([])
    judge = GeminiEvidenceJudge(SimpleNamespace(models=models), "gemini-test")
    candidate = ClaimCandidate(text="Acme has SSO", query="Acme SSO")

    assessment = judge.assess(candidate, [])

    assert assessment.verdict == Verdict.INSUFFICIENT
    assert models.calls == []


def test_gemini_judge_validates_json_and_preserves_input_claim() -> None:
    response = SimpleNamespace(
        text=(
            '{"claim":"changed by model","verdict":"supported",'
            '"confidence":0.8,"explanation":"The pricing page confirms it.",'
            '"recommendation":"Keep on shortlist.",'
            '"citation_urls":["https://example.com/current"]}'
        ),
        parsed=None,
    )
    models = FakeModels([response])
    judge = GeminiEvidenceJudge(SimpleNamespace(models=models), "gemini-test")
    candidate = ClaimCandidate(text="Acme has SSO", query="Acme SSO")

    assessment = judge.assess(candidate, [source()])

    assert assessment.claim == "Acme has SSO"
    assert assessment.verdict == Verdict.SUPPORTED
    assert str(assessment.citation_urls[0]) == "https://example.com/current"
    assert "untrusted data" in models.calls[0]["contents"]

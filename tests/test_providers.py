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


def search_candidate() -> ClaimCandidate:
    return ClaimCandidate(
        entity_anchor="Vendor",
        entity_domain="vendor.com",
        requirement_anchor="price",
        fact_category="pricing",
        text="Vendor price",
        query="Vendor price and recent reliability",
        domain_from_brief=True,
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
    shared = "https://vendor.com/pricing"
    client = FakeSerpClient(
        {
            "google_light": {
                "search_metadata": {"id": "web-123"},
                "organic_results": [
                    {
                        "title": "Vendor pricing",
                        "link": shared,
                        "snippet": "$20 per user",
                        "displayed_link": "vendor.com",
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
                        "snippet": "Vendor vendor.com service recovered.",
                        "source": {"name": "Example News"},
                        "date": "2 days ago",
                    },
                ],
            },
        }
    )
    gateway = SerpApiSearchGateway(client=client, results_per_engine=5)

    outcome = gateway.search(search_candidate())
    results = outcome.sources

    assert [call["engine"] for call in client.calls] == [
        "google_light",
        "google_news",
    ]
    assert client.calls[0]["num"] == 5
    assert "num" not in client.calls[1]
    assert client.calls[0]["q"] == "Vendor price and recent reliability"
    assert [str(result.url) for result in results] == [
        shared,
        "https://news.example/outage",
    ]
    assert results[0].search_id == "web-123"
    assert results[1].source == "Example News"
    assert results[1].published_at == "2 days ago"
    assert outcome.failed_engines == []


def test_serpapi_filters_entity_binding_before_deduplicating_urls() -> None:
    shared = "https://news.example/vendor-outage"
    client = FakeSerpClient(
        {
            "google_light": {
                "organic_results": [
                    {
                        "title": "Vendor home",
                        "link": "https://vendor.com/",
                    },
                    {
                        "title": "Service outage report",
                        "link": shared,
                        "snippet": "Customers were affected.",
                    },
                ]
            },
            "google_news": {
                "news_results": [
                    {
                        "title": "Vendor outage report",
                        "link": shared,
                        "snippet": "Vendor.com customers were affected.",
                    }
                ]
            },
        }
    )

    outcome = SerpApiSearchGateway(client=client).search(search_candidate())

    assert [str(item.url) for item in outcome.sources] == [
        "https://vendor.com/",
        shared,
    ]


def test_serpapi_gateway_keeps_partial_results_and_fails_when_both_fail() -> None:
    partial = FakeSerpClient(
        {
            "google_light": RuntimeError("web failed"),
            "google_news": {
                "news_results": [
                    {"title": "Vendor News", "link": "https://vendor.com/news"}
                ]
            },
        }
    )
    outcome = SerpApiSearchGateway(client=partial).search(search_candidate())
    assert len(outcome.sources) == 1
    assert outcome.failed_engines == ["google_light"]

    failed = FakeSerpClient(
        {
            "google_light": RuntimeError("web failed"),
            "google_news": {"error": "quota exceeded"},
        }
    )
    with pytest.raises(RuntimeError, match="web and news"):
        SerpApiSearchGateway(client=failed).search(search_candidate())


def test_serpapi_gateway_requires_live_entity_domain_confirmation() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "organic_results": [
                    {
                        "title": "Unrelated company",
                        "link": "https://evil.example/about",
                    }
                ]
            },
            "google_news": {
                "news_results": [
                    {
                        "title": "Vendor outage",
                        "link": "https://news.example/vendor-outage",
                    }
                ]
            },
        }
    )
    unverified = search_candidate().model_copy(update={"entity_domain": "evil.example"})

    outcome = SerpApiSearchGateway(client=client).search(unverified)

    assert outcome.sources == []
    assert outcome.entity_domain_verified is False


def test_explicit_domain_confirmation_is_reused_across_vendor_claims() -> None:
    gateway = SerpApiSearchGateway(client=FakeSerpClient({}))
    candidate = search_candidate()
    official = SourceRecord(
        title="Vendor pricing",
        url="https://vendor.com/pricing",
        snippet="Official Vendor pricing.",
        source="Vendor",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert gateway._domain_mapping_confirmed(candidate, [official], []) is True
    assert gateway._domain_mapping_confirmed(candidate, [], []) is True


def test_serpapi_domain_url_cannot_confirm_entity_by_itself() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "organic_results": [
                    {
                        "title": "A different product",
                        "link": "https://mercury.ai/about",
                        "snippet": "Unrelated company profile.",
                    }
                ]
            },
            "google_news": {"news_results": []},
        }
    )
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Mercury", "entity_domain": "mercury.ai"}
    )

    outcome = SerpApiSearchGateway(client=client).search(candidate)

    assert outcome.sources == []
    assert outcome.entity_domain_verified is False


def test_serpapi_displayed_url_cannot_confirm_entity_by_itself() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "organic_results": [
                    {
                        "title": "A different product",
                        "link": "https://mercury.ai/about",
                        "snippet": "Unrelated company profile.",
                        "displayed_link": "https://mercury.ai/about",
                    }
                ]
            },
            "google_news": {"news_results": []},
        }
    )
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Mercury", "entity_domain": "mercury.ai"}
    )

    outcome = SerpApiSearchGateway(client=client).search(candidate)

    assert outcome.sources == []
    assert outcome.entity_domain_verified is False


def test_model_supplied_domain_requires_independent_knowledge_graph() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "organic_results": [
                    {
                        "title": "Vendor pricing guide",
                        "link": "https://evil.example/vendor",
                        "snippet": "Vendor costs $20.",
                    }
                ]
            },
            "google_news": {"news_results": []},
        }
    )
    candidate = search_candidate().model_copy(
        update={"entity_domain": "evil.example", "domain_from_brief": False}
    )

    outcome = SerpApiSearchGateway(client=client).search(candidate)

    assert outcome.sources == []
    assert outcome.entity_domain_verified is False
    assert len(client.calls) == 3


def test_transient_identity_failure_is_not_cached() -> None:
    class FlakyIdentityClient:
        def __init__(self) -> None:
            self.identity_calls = 0

        def search(self, params: dict[str, object]) -> object:
            query = str(params["q"])
            if "official website" in query:
                self.identity_calls += 1
                if self.identity_calls == 1:
                    raise RuntimeError("temporary identity lookup failure")
                return {
                    "knowledge_graph": {
                        "title": "Vendor",
                        "website": "https://vendor.com/",
                    }
                }
            if params["engine"] == "google_news":
                return {"news_results": []}
            return {
                "organic_results": [
                    {
                        "title": "Vendor documentation",
                        "link": "https://vendor.com/docs",
                    }
                ]
            }

    client = FlakyIdentityClient()
    gateway = SerpApiSearchGateway(client=client)
    first = search_candidate().model_copy(update={"domain_from_brief": False})
    second = first.model_copy(
        update={
            "requirement_anchor": "SCIM",
            "text": "Vendor supports SCIM",
            "query": "Vendor SCIM",
        }
    )

    with pytest.raises(RuntimeError, match="web and news"):
        gateway.search(first)
    outcome = gateway.search(second)

    assert client.identity_calls == 2
    assert outcome.entity_domain_verified is True
    assert len(outcome.sources) == 1


def test_knowledge_graph_can_confirm_model_supplied_domain() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "knowledge_graph": {
                    "title": "Vendor",
                    "website": "https://vendor.com/",
                },
                "organic_results": [
                    {
                        "title": "Vendor pricing",
                        "link": "https://vendor.com/pricing",
                    }
                ],
            },
            "google_news": {"news_results": []},
        }
    )
    candidate = search_candidate().model_copy(update={"domain_from_brief": False})

    outcome = SerpApiSearchGateway(client=client).search(candidate)

    assert outcome.entity_domain_verified is True
    assert len(outcome.sources) == 1


def test_knowledge_graph_rejects_descriptive_namesake_entity() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercuryinsurance.com",
            "domain_from_brief": False,
        }
    )
    payload = {
        "knowledge_graph": {
            "title": "Mercury Insurance",
            "website": "https://www.mercuryinsurance.com/",
        }
    }

    assert (
        SerpApiSearchGateway._knowledge_graph_confirms_domain(payload, candidate)
        is False
    )


def test_knowledge_graph_allows_only_legal_suffix_variation() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Acme",
            "entity_domain": "acme.com",
            "domain_from_brief": False,
        }
    )
    payload = {
        "knowledge_graph": {
            "title": "Acme, Inc.",
            "website": "https://www.acme.com/",
        }
    }

    assert SerpApiSearchGateway._knowledge_graph_confirms_domain(payload, candidate)


@pytest.mark.parametrize("title", ["Acme B.V.", "Acme A.G.", "Acme N.V."])
def test_knowledge_graph_normalizes_dotted_legal_suffixes(title: str) -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Acme", "entity_domain": "acme.com"}
    )
    payload = {
        "knowledge_graph": {"title": title, "website": "https://acme.com/"}
    }

    assert SerpApiSearchGateway._knowledge_graph_confirms_domain(payload, candidate)


def test_source_filter_allows_legal_suffix_variation() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Acme, Inc.", "entity_domain": "acme.com"}
    )
    source_record = source().model_copy(
        update={
            "title": "Acme SSO documentation",
            "url": "https://acme.com/docs/sso",
            "source": "Acme",
        }
    )

    assert SerpApiSearchGateway._source_confirms_domain(source_record, candidate)


@pytest.mark.parametrize("suffix", ["SE", "GmbH", "AG", "BV"])
def test_source_filter_allows_international_legal_suffix_variation(
    suffix: str,
) -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": f"Acme {suffix}", "entity_domain": "acme.com"}
    )
    source_record = source().model_copy(
        update={
            "title": "Acme SSO documentation",
            "url": "https://acme.com/docs/sso",
            "source": "Acme",
        }
    )

    assert SerpApiSearchGateway._source_confirms_domain(source_record, candidate)


@pytest.mark.parametrize(
    "legal_name",
    ["Acme Pte Ltd", "Acme Pte. Ltd.", "Acme Pty Ltd", "Acme L.L.C."],
)
def test_source_filter_normalizes_multitoken_legal_suffixes(
    legal_name: str,
) -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": legal_name, "entity_domain": "acme.com"}
    )
    source_record = SourceRecord(
        title="Acme SSO documentation",
        url="https://acme.com/sso",
        snippet="Official Acme documentation.",
        source="Acme",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_confirms_domain(source_record, candidate)


def test_identity_lookup_confirms_domain_for_third_party_risk_results() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "knowledge_graph": {
                    "title": "Vendor",
                    "website": "https://vendor.com/",
                },
                "organic_results": [
                    {
                        "title": "Vendor outage report",
                        "link": "https://news.example/vendor-outage",
                        "snippet": "The vendor.com service recovered.",
                    }
                ],
            },
            "google_news": {"news_results": []},
        }
    )

    outcome = SerpApiSearchGateway(client=client).search(search_candidate())

    assert outcome.entity_domain_verified is True
    assert [str(source.url) for source in outcome.sources] == [
        "https://news.example/vendor-outage"
    ]
    assert len(client.calls) == 3


def test_cross_domain_namesake_evidence_is_excluded() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "organic_results": [
                    {
                        "title": "Mercury banking",
                        "link": "https://mercury.com/pricing",
                        "snippet": "Mercury pricing",
                    }
                ]
            },
            "google_news": {
                "news_results": [
                    {
                        "title": "Mercury AI outage",
                        "link": "https://mercury.ai/status",
                        "snippet": "Mercury service failed.",
                    }
                ]
            },
        }
    )
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )

    outcome = SerpApiSearchGateway(client=client).search(candidate)

    assert [str(source.url) for source in outcome.sources] == [
        "https://mercury.com/pricing"
    ]


def test_compound_namesake_domain_is_excluded() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title="Mercury Insurance pricing",
        url="https://mercuryinsurance.com/pricing",
        snippet="Mercury insurance plans",
        source="Mercury Insurance",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(source, candidate) is False


def test_verified_entity_keeps_ordinary_third_party_news() -> None:
    client = FakeSerpClient(
        {
            "google_light": {
                "organic_results": [
                    {
                        "title": "Intercom status",
                        "link": "https://intercom.com/status",
                    }
                ]
            },
            "google_news": {
                "news_results": [
                    {
                        "title": "Intercom outage report",
                        "link": "https://techcrunch.com/intercom-outage",
                        "snippet": (
                            "The intercom.com incident affected customers on Friday."
                        ),
                    }
                ]
            },
        }
    )
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Intercom",
            "entity_domain": "intercom.com",
            "domain_from_brief": True,
        }
    )

    outcome = SerpApiSearchGateway(client=client).search(candidate)

    assert [str(source.url) for source in outcome.sources] == [
        "https://intercom.com/status",
        "https://techcrunch.com/intercom-outage",
    ]


def test_single_token_entity_rejects_third_party_news_without_domain_text() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Intercom",
            "entity_domain": "intercom.com",
            "requirement_anchor": "outage",
            "text": "Intercom outage risk",
            "query": "Intercom recent outage",
        }
    )
    source = SourceRecord(
        title="Intercom outage affects customer support teams",
        url="https://techcrunch.com/intercom-outage",
        snippet="Intercom reported that service was restored Friday.",
        source="TechCrunch",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_multiword_entity_requires_domain_text_in_third_party_news() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "International Business Machines",
            "entity_domain": "ibm.com",
            "requirement_anchor": "outage",
            "text": "International Business Machines outage risk",
            "query": "International Business Machines recent outage",
        }
    )
    source = SourceRecord(
        title="International Business Machines outage affects customers",
        url="https://example.org/ibm-outage",
        snippet="International Business Machines restored service Friday.",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )

    confirmed = source.model_copy(
        update={
            "snippet": (
                "International Business Machines restored service on ibm.com Friday."
            )
        }
    )
    assert SerpApiSearchGateway._source_is_bound_to_entity(
        confirmed, candidate, domain_confirmed=True
    )


@pytest.mark.parametrize("namesake", ["Mercury Drug", "Mercury Records"])
def test_verified_generic_name_rejects_unrelated_compound_namesake(
    namesake: str,
) -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Mercury", "entity_domain": "mercury.com"}
    )
    source = SourceRecord(
        title=f"{namesake} pricing changes",
        url="https://example.org/story",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_verified_generic_name_rejects_namesake_before_entity_token() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Mercury", "entity_domain": "mercury.com"}
    )
    source = SourceRecord(
        title="Freddie Mercury | Biography",
        url="https://example.org/biography",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_title_cased_namesake_is_rejected_even_with_official_domain_text() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "mercury", "entity_domain": "mercury.com"}
    )
    source = SourceRecord(
        title="Freddie Mercury biography",
        url="https://example.org/biography",
        snippet="Read more at mercury.com",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_unlisted_compound_namesake_is_rejected_with_official_domain_text() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Mercury", "entity_domain": "mercury.com"}
    )
    source = SourceRecord(
        title="Mercury Payments announces layoffs",
        url="https://example.org/layoffs",
        snippet="Unlike mercury.com, Mercury Payments will cut 100 jobs.",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_compound_namesake_in_snippet_is_rejected() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Mercury", "entity_domain": "mercury.com"}
    )
    source = SourceRecord(
        title="Mercury announces layoffs",
        url="https://example.org/layoffs",
        snippet=(
            "Mercury General Insurance announced layoffs; unlike mercury.com, "
            "its banking namesake is unaffected."
        ),
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_namesake_detection_does_not_join_title_and_snippet_tokens() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "requirement_anchor": "layoffs",
            "text": "Mercury layoffs",
            "query": "Mercury layoffs",
        }
    )
    source = SourceRecord(
        title="Mercury announces layoffs",
        url="https://example.org/layoffs",
        snippet="Mercury General Insurance will cut 100 jobs.",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_entity_name_cannot_be_assembled_across_result_fields() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury Bank",
            "entity_domain": "mercury.com",
            "requirement_anchor": "layoffs",
            "text": "Mercury Bank layoffs",
            "query": "Mercury Bank layoffs",
        }
    )
    source = SourceRecord(
        title="Planet Mercury",
        url="https://example.org/layoffs",
        snippet="Bank layoffs rose this year.",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_namesake_descriptor_is_rejected_even_when_it_matches_requirement() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "requirement_anchor": "insurance",
            "text": "Mercury must provide insurance",
            "query": "Mercury insurance coverage",
        }
    )
    source = SourceRecord(
        title="Mercury Insurance raises prices",
        url="https://example.org/insurance",
        snippet="Mercury Insurance changed its customer rates.",
        source="Example News",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_third_party_namesake_without_official_domain_is_excluded() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title="Mercury Insurance announces layoffs",
        url="https://www.reuters.com/example",
        snippet="Mercury General is cutting jobs.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(source, candidate) is False


@pytest.mark.parametrize("namesake", ["Mercury Marine", "Mercury Systems"])
def test_third_party_compound_namesake_is_excluded(namesake: str) -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title=f"{namesake} announces layoffs",
        url="https://www.reuters.com/example",
        snippet=f"{namesake} is cutting jobs.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_third_party_exact_reference_is_accepted_after_domain_confirmation() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title="Mercury announces a new funding round",
        url="https://www.reuters.com/example",
        snippet="Mercury said mercury.com will use the funds for product development.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_bare_third_party_entity_reference_is_insufficient_binding() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title="Mercury Insurance announces layoffs",
        url="https://www.reuters.com/example",
        snippet="Mercury said it will cut jobs.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


@pytest.mark.parametrize(
    "title,snippet",
    [
        ("Mercury Insurance announces layoffs", "Mercury said it will cut jobs."),
        ("Freddie Mercury biography", "Mercury was a singer."),
    ],
)
def test_legal_suffix_does_not_turn_bare_namesake_into_multitoken_binding(
    title: str, snippet: str
) -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury Inc.",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title=title,
        url="https://www.reuters.com/example",
        snippet=snippet,
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_longer_multiword_namesake_is_rejected_without_official_domain_text() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury Bank",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title="Mercury Bank Trust outage affects customers",
        url="https://www.reuters.com/example",
        snippet="Mercury Bank Trust restored service.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_namesake_is_rejected_even_when_snippet_mentions_official_domain() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Mercury",
            "entity_domain": "mercury.com",
            "domain_from_brief": True,
        }
    )
    source = SourceRecord(
        title="Mercury Insurance announces layoffs",
        url="https://www.reuters.com/example",
        snippet="Unlike mercury.com, Mercury Insurance will cut jobs.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


@pytest.mark.parametrize("domain_text", ["mercury.com.au", "mercury.com.evil.test"])
def test_official_domain_prefix_does_not_bind_third_party_evidence(
    domain_text: str,
) -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Mercury", "entity_domain": "mercury.com"}
    )
    source = SourceRecord(
        title="Mercury outage",
        url="https://www.reuters.com/example",
        snippet=f"The {domain_text} service had an outage.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            source, candidate, domain_confirmed=True
        )
        is False
    )


def test_sentence_period_after_official_domain_still_binds_evidence() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Intercom", "entity_domain": "intercom.com"}
    )
    source = SourceRecord(
        title="Intercom outage",
        url="https://www.reuters.com/example",
        snippet="Service details are available at intercom.com.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_title_case_requirement_is_not_mistaken_for_a_namesake() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Intercom", "entity_domain": "intercom.com"}
    )
    source = SourceRecord(
        title="Intercom Outage Report",
        url="https://www.reuters.com/example",
        snippet="The intercom.com incident affected customers.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_title_case_role_is_not_mistaken_for_a_namesake() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Intercom", "entity_domain": "intercom.com"}
    )
    source = SourceRecord(
        title="Intercom CEO resigns",
        url="https://www.reuters.com/example",
        snippet="The intercom.com chief resigned today.",
        source="Reuters",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_ampersand_and_word_spellings_bind_in_both_directions() -> None:
    source = SourceRecord(
        title="Dun & Bradstreet Pricing",
        url="https://www.dnb.com/products/pricing",
        snippet="Official pricing information.",
        source="dnb.com",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Dun and Bradstreet",
            "entity_domain": "dnb.com",
        }
    )

    assert SerpApiSearchGateway._source_confirms_domain(source, candidate)
    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_cjk_entity_accepts_unspaced_continuation_on_verified_host() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "飞书", "entity_domain": "feishu.cn"}
    )
    source = SourceRecord(
        title="飞书发生大规模故障",
        url="https://www.feishu.cn/news",
        snippet="官方信息",
        source="feishu.cn",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_confirms_domain(source, candidate)
    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_confirmed_official_host_accepts_generic_page_metadata() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Acme", "entity_domain": "acme.com"}
    )
    source = SourceRecord(
        title="Pricing plans",
        url="https://acme.com/pricing",
        snippet="$20 per user",
        source="acme.com",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_dotted_brand_accepts_generic_page_on_confirmed_official_host() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "monday.com", "entity_domain": "monday.com"}
    )
    source = SourceRecord(
        title="Pricing plans",
        url="https://monday.com/pricing",
        snippet="$20 per user",
        source="monday.com",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_shared_official_domain_still_requires_the_specific_product_name() -> None:
    candidate = search_candidate().model_copy(
        update={
            "entity_anchor": "Microsoft Teams",
            "entity_domain": "microsoft.com",
        }
    )
    wrong_product = SourceRecord(
        title="Microsoft 365 single sign-on documentation",
        url="https://www.microsoft.com/microsoft-365/sso",
        snippet="Configure SSO for Microsoft 365.",
        source="microsoft.com",
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )
    right_product = wrong_product.model_copy(
        update={
            "title": "Microsoft Teams single sign-on documentation",
            "url": "https://www.microsoft.com/microsoft-teams/sso",
            "snippet": "Configure SSO for Microsoft Teams.",
        }
    )

    assert (
        SerpApiSearchGateway._source_is_bound_to_entity(
            wrong_product, candidate, domain_confirmed=True
        )
        is False
    )
    assert SerpApiSearchGateway._source_is_bound_to_entity(
        right_product, candidate, domain_confirmed=True
    )


@pytest.mark.parametrize("host", ["www.acme.com", "status.acme.com"])
def test_confirmed_official_subdomain_accepts_generic_metadata(host: str) -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "Acme", "entity_domain": "acme.com"}
    )
    source = SourceRecord(
        title="Service status",
        url=f"https://{host}/status",
        snippet="All systems operational",
        source=host,
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )

    assert SerpApiSearchGateway._source_is_bound_to_entity(
        source, candidate, domain_confirmed=True
    )


def test_knowledge_graph_rejects_empty_canonical_short_names() -> None:
    candidate = search_candidate().model_copy(
        update={"entity_anchor": "AB", "entity_domain": "se.com"}
    )
    payload = {"knowledge_graph": {"title": "SE", "website": "https://se.com"}}

    assert not SerpApiSearchGateway._knowledge_graph_confirms_domain(payload, candidate)


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
    assert options["json"]["api_token"] == "server-token"
    assert options["json"]["report"]["comparison_schema"] == "v5"
    assert options["headers"] == {"Accept": "application/json"}
    assert options["timeout"] == 20


def test_xano_store_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        XanoSnapshotStore("http://example.xano.io/api:snapshot")


def test_xano_store_requires_token_when_enabled() -> None:
    with pytest.raises(ValueError, match="XANO_API_TOKEN"):
        XanoSnapshotStore("https://example.xano.io/api:snapshot")


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
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"five-person team",'
            '"fact_category":"other_capability",'
            '"text":"Acme supports a five-person team",'
            '"query":"Acme five-person team plan pricing",'
            '"why_check":"Plan limits can change","priority":5}]}'
        ),
        parsed=None,
    )
    models = FakeModels([response])
    extractor = GeminiClaimExtractor(SimpleNamespace(models=models), "gemini-test")

    claims = extractor.extract("Compare Acme for a five-person team.")

    assert claims[0].text == "Acme supports a five-person team"
    assert claims[0].comparison_key.startswith("v5_entity_")
    assert models.calls[0]["model"] == "gemini-test"
    assert "untrusted data" in models.calls[0]["contents"]
    assert "include the complete" in models.calls[0]["contents"]


def test_gemini_extractor_retries_rejected_anchor_and_canonicalizes_unit() -> None:
    rejected = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SOC 2 certification",'
            '"fact_category":"security_certification",'
            '"text":"Acme security includes SOC 2",'
            '"query":"Acme security SOC 2"}]}'
        ),
        parsed=None,
    )
    corrected = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"security",'
            '"fact_category":"security_certification",'
            '"text":"Acme security includes SOC 2",'
            '"query":"Acme security SOC 2"}]}'
        ),
        parsed=None,
    )
    models = FakeModels([rejected, corrected])
    extractor = GeminiClaimExtractor(SimpleNamespace(models=models), "gemini-test")

    claims = extractor.extract("Compare Acme. Security is required.")

    assert len(models.calls) == 2
    assert claims[0].requirement_anchor == "security"
    assert "previous checklist" in models.calls[1]["contents"]


def test_gemini_extractor_rejects_entity_as_requirement_identity() -> None:
    malformed = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"Acme","fact_category":"pricing",'
            '"text":"Acme pricing is within budget","query":"Acme pricing"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([malformed, malformed])), "gemini-test"
    )

    assert (
        extractor.extract("Compare Acme (acme.com). Budget for Acme: $100/month.") == []
    )
    assert extractor.rejected_count == 1


def test_gemini_extractor_surfaces_count_after_two_rejected_batches() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"International Business Machines",'
            '"entity_domain":"ibm.com","requirement_anchor":"security",'
            '"fact_category":"security_certification",'
            '"text":"IBM has security controls",'
            '"query":"IBM security"}]}'
        ),
        parsed=None,
    )
    models = FakeModels([response, response])
    extractor = GeminiClaimExtractor(SimpleNamespace(models=models), "gemini-test")

    assert extractor.extract("Compare IBM security.") == []
    assert extractor.rejected_count == 1


def test_gemini_extractor_canonicalizes_nested_anchor_wording() -> None:
    short = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"shared inbox",'
            '"fact_category":"shared_inbox","text":"Acme has a shared inbox",'
            '"query":"Acme shared inbox"}]}'
        ),
        parsed=None,
    )
    long = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"Must have a shared inbox",'
            '"fact_category":"shared_inbox","text":"Acme offers a shared inbox",'
            '"query":"Acme shared inbox"}]}'
        ),
        parsed=None,
    )
    brief = "Compare Acme. Must have a shared inbox and chatbot."

    first = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([short])), "gemini-test"
    ).extract(brief)[0]
    second = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([long])), "gemini-test"
    ).extract(brief)[0]

    assert first.requirement_anchor == "shared inbox"
    assert second.requirement_anchor == first.requirement_anchor
    assert second.comparison_key == first.comparison_key


def test_gemini_extractor_keeps_same_category_checks_in_one_sentence() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"},'
            '{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SCIM","fact_category":"integration",'
            '"text":"Acme supports SCIM","query":"Acme SCIM"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response])), "gemini-test"
    )

    claims = extractor.extract("Compare Acme. Must support SSO and SCIM.")

    assert [claim.requirement_anchor for claim in claims] == ["sso", "scim"]
    assert claims[0].comparison_key != claims[1].comparison_key


def test_gemini_extractor_retries_anchor_that_canonicalizes_empty() -> None:
    invalid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"Budget:","fact_category":"pricing",'
            '"text":"Check Acme pricing","query":"Acme pricing"}]}'
        ),
        parsed=None,
    )
    valid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"$100 per month","fact_category":"pricing",'
            '"text":"Acme costs $100 per month",'
            '"query":"Acme $100 per month pricing"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([invalid, valid])), "gemini-test"
    )

    claims = extractor.extract("Compare Acme. Budget: $100 per month.")

    assert claims[0].requirement_anchor == "$100 per month"


def test_gemini_extractor_rejects_partial_entity_and_unrelated_domain() -> None:
    invalid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"me","entity_domain":"evil.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Evil supports SSO","query":"Evil SSO"}]}'
        ),
        parsed=None,
    )
    valid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([invalid, valid])), "gemini-test"
    )

    claims = extractor.extract("Compare Acme. Must support SSO.")

    assert claims[0].entity_anchor == "acme"
    assert claims[0].entity_domain == "acme.com"


def test_gemini_extractor_accepts_parent_company_domain() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Jira",'
            '"entity_domain":"atlassian.com","requirement_anchor":"SSO",'
            '"fact_category":"integration","text":"Jira supports SSO",'
            '"query":"Jira SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response])), "gemini-test"
    )

    claims = extractor.extract("Compare Jira. Must support SSO.")

    assert claims[0].entity_anchor == "jira"
    assert claims[0].entity_domain == "atlassian.com"
    assert claims[0].domain_from_brief is False


def test_gemini_extractor_marks_domain_copied_from_brief_as_trusted() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Mercury",'
            '"entity_domain":"mercury.com","requirement_anchor":"SSO",'
            '"fact_category":"integration","text":"Mercury supports SSO",'
            '"query":"Mercury SSO","domain_from_brief":false}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response])), "gemini-test"
    )

    claims = extractor.extract("Compare Mercury (mercury.com). Must support SSO.")

    assert claims[0].domain_from_brief is True


def test_gemini_extractor_retries_non_apex_model_domain() -> None:
    invalid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Intercom",'
            '"entity_domain":"support.intercom.com","requirement_anchor":"pricing",'
            '"fact_category":"pricing","text":"Intercom pricing is current",'
            '"query":"Intercom pricing current"}]}'
        ),
        parsed=None,
    )
    valid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Intercom",'
            '"entity_domain":"intercom.com","requirement_anchor":"pricing",'
            '"fact_category":"pricing","text":"Intercom pricing is current",'
            '"query":"Intercom pricing current"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([invalid, valid])), "gemini-test"
    )

    claims = extractor.extract(
        "We use Intercom. Review current pricing and shared inbox support."
    )

    assert claims[0].entity_domain == "intercom.com"
    assert claims[0].entity_anchor == "intercom"


def test_gemini_extractor_rejects_domain_that_conflicts_with_brief() -> None:
    wrong = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Mercury",'
            '"entity_domain":"mercury.ai","requirement_anchor":"SSO",'
            '"fact_category":"integration","text":"Mercury supports SSO",'
            '"query":"Mercury SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([wrong, wrong])), "gemini-test"
    )

    claims = extractor.extract("Compare Mercury (mercury.com). Must support SSO.")

    assert claims == []
    assert extractor.rejected_count == 1


def test_gemini_extractor_requires_query_to_name_exact_entity_anchor() -> None:
    invalid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"need SSO pricing"}]}'
        ),
        parsed=None,
    )
    valid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO pricing"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([invalid, valid])), "gemini-test"
    )

    claims = extractor.extract("We need software from Acme. Must support SSO.")

    assert claims[0].entity_anchor == "acme"
    assert claims[0].query == "Acme SSO pricing"


def test_gemini_extractor_requires_claim_text_to_name_exact_entity_anchor() -> None:
    invalid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Beta supports SSO","query":"Acme SSO"}]}'
        ),
        parsed=None,
    )
    valid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([invalid, valid])), "gemini-test"
    )

    claims = extractor.extract("Compare Acme and Beta. Must support SSO.")

    assert [claim.entity_anchor for claim in claims] == ["acme"]
    assert extractor.rejected_count == 1


def test_gemini_extractor_rejects_cross_wired_requirement_fields() -> None:
    invalid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"pricing",'
            '"text":"Acme costs $100 per month",'
            '"query":"Acme pricing $100 per month"}]}'
        ),
        parsed=None,
    )
    valid = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([invalid, valid])), "gemini-test"
    )

    claims = extractor.extract(
        "Compare Acme. Budget: $100 per month. Must support SSO."
    )

    assert [claim.requirement_anchor for claim in claims] == ["sso"]
    assert extractor.rejected_count == 1


def test_gemini_extractor_rejects_ambiguous_namesake_domains() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Mercury","entity_domain":"mercury.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Mercury supports SSO","query":"Mercury SSO"},'
            '{"entity_anchor":"Mercury","entity_domain":"mercury.ai",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Mercury supports SSO","query":"Mercury SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response, response])), "gemini-test"
    )

    assert extractor.extract("Compare Mercury. Must support SSO.") == []
    assert extractor.rejected_count == 2


def test_gemini_extractor_accepts_unicode_entity_query() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"飞书","entity_domain":"feishu.cn",'
            '"requirement_anchor":"知识库","fact_category":"knowledge_base",'
            '"text":"飞书支持知识库","query":"飞书 知识库功能"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response])), "gemini-test"
    )

    claims = extractor.extract("飞书。需要知识库。")

    assert claims[0].entity_anchor == "飞书"


def test_gemini_extractor_rejects_invalid_annotated_brief_domain() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response, response])), "gemini-test"
    )

    claims = extractor.extract("Compare Acme (acme.invalid). Must support SSO.")

    assert claims == []
    assert extractor.rejected_count == 1


def test_gemini_extractor_rejects_invalid_domain_during_alias_resolution() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"IBM","entity_domain":"ibm.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"IBM supports SSO","query":"IBM SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response, response])), "gemini-test"
    )

    claims = extractor.extract(
        "Compare International Business Machines (ibm.invalid). Must support SSO."
    )

    assert claims == []
    assert extractor.rejected_count == 1


def test_gemini_extractor_retries_a_batch_with_one_malformed_candidate() -> None:
    malformed = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Acme","entity_domain":"https://acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"},'
            '{"entity_anchor":"Beta","entity_domain":"beta.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Beta supports SSO","query":"Beta SSO"}]}'
        ),
        parsed=None,
    )
    corrected = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"},'
            '{"entity_anchor":"Beta","entity_domain":"beta.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Beta supports SSO","query":"Beta SSO"}]}'
        ),
        parsed=None,
    )
    models = FakeModels([malformed, corrected])
    extractor = GeminiClaimExtractor(SimpleNamespace(models=models), "gemini-test")

    claims = extractor.extract("Compare Acme and Beta. Must support SSO.")

    assert len(models.calls) == 2
    assert {claim.entity_anchor for claim in claims} == {"acme", "beta"}


def test_gemini_extractor_warns_when_retry_replaces_a_rejected_check() -> None:
    first = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"},'
            '{"entity_anchor":"Beta","entity_domain":"beta.com",'
            '"requirement_anchor":"invented","fact_category":"integration",'
            '"text":"Beta supports SCIM","query":"Beta SCIM"}]}'
        ),
        parsed=None,
    )
    replacement = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"},'
            '{"entity_anchor":"Gamma","entity_domain":"gamma.com",'
            '"requirement_anchor":"SCIM","fact_category":"integration",'
            '"text":"Gamma supports SCIM","query":"Gamma SCIM"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([first, replacement])), "gemini-test"
    )

    claims = extractor.extract(
        "Compare Acme, Beta, and Gamma. Must support SSO and SCIM."
    )

    assert len(claims) == 2
    assert extractor.rejected_count == 1


def test_gemini_extractor_rejects_oversized_canonical_requirement() -> None:
    response = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([response, response])), "gemini-test"
    )
    brief = f"Compare Acme. Must {'very carefully ' * 20}support SSO."

    assert extractor.extract(brief) == []
    assert extractor.rejected_count == 1


def test_gemini_extractor_keeps_valid_first_batch_when_retry_fails() -> None:
    first = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"},'
            '{"entity_anchor":"Beta","entity_domain":"bad",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Beta supports SSO","query":"Beta SSO"}]}'
        ),
        parsed=None,
    )
    models = FakeModels([first, TimeoutError("retry timed out")])
    extractor = GeminiClaimExtractor(SimpleNamespace(models=models), "gemini-test")

    claims = extractor.extract("Compare Acme and Beta. Must support SSO.")

    assert [claim.entity_anchor for claim in claims] == ["acme"]
    assert extractor.rejected_count == 1


def test_gemini_extractor_merges_valid_checks_from_both_attempts() -> None:
    first = SimpleNamespace(
        text=(
            '{"claims":['
            '{"entity_anchor":"Acme","entity_domain":"acme.com",'
            '"requirement_anchor":"SSO","fact_category":"integration",'
            '"text":"Acme supports SSO","query":"Acme SSO"},'
            '{"entity_anchor":"Beta","entity_domain":"bad",'
            '"requirement_anchor":"SCIM","fact_category":"integration",'
            '"text":"Beta supports SCIM","query":"Beta SCIM"}]}'
        ),
        parsed=None,
    )
    retry = SimpleNamespace(
        text=(
            '{"claims":[{"entity_anchor":"Beta","entity_domain":"beta.com",'
            '"requirement_anchor":"SCIM","fact_category":"integration",'
            '"text":"Beta supports SCIM","query":"Beta SCIM"}]}'
        ),
        parsed=None,
    )
    extractor = GeminiClaimExtractor(
        SimpleNamespace(models=FakeModels([first, retry])), "gemini-test"
    )

    claims = extractor.extract("Compare Acme and Beta. Must support SSO and SCIM.")

    assert [claim.entity_anchor for claim in claims] == ["acme", "beta"]
    assert extractor.rejected_count == 1


def test_gemini_judge_handles_no_sources_without_model_call() -> None:
    models = FakeModels([])
    judge = GeminiEvidenceJudge(SimpleNamespace(models=models), "gemini-test")
    candidate = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="SSO",
        fact_category="other_capability",
        text="Acme has SSO",
        query="Acme SSO",
    )

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
    candidate = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="SSO",
        fact_category="other_capability",
        text="Acme has SSO",
        query="Acme SSO",
    )

    assessment = judge.assess(candidate, [source()])

    assert assessment.claim == "Acme has SSO"
    assert assessment.verdict == Verdict.SUPPORTED
    assert str(assessment.citation_urls[0]) == "https://example.com/current"
    assert "untrusted data" in models.calls[0]["contents"]

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vendorproof.models import (
    ClaimAssessment,
    ClaimCandidate,
    SourceRecord,
    Verdict,
    brief_anchor_association_valid,
    brief_domain_for_entity,
    canonicalize_brief_anchor,
    canonicalize_requirement_anchor,
    comparison_entity_hints,
    query_mentions_entity,
    split_brief_sentences,
)


def test_claim_candidate_rejects_empty_or_oversized_text() -> None:
    with pytest.raises(ValidationError):
        ClaimCandidate(
            entity_anchor="Acme",
            entity_domain="acme.com",
            requirement_anchor="current status",
            fact_category="reliability",
            text="",
            query="current status",
        )

    with pytest.raises(ValidationError):
        ClaimCandidate(
            entity_anchor="Acme",
            entity_domain="acme.com",
            requirement_anchor="current status",
            fact_category="reliability",
            text="x" * 501,
            query="current status",
        )


def test_claim_candidate_derives_deterministic_comparison_key() -> None:
    first = ClaimCandidate(
        entity_anchor="Zendesk",
        entity_domain="WWW.ZENDESK.COM.",
        requirement_anchor="Slack integration",
        fact_category="integration",
        text="Zendesk integrates with Slack.",
        query="Zendesk Slack integration",
    )
    paraphrase = ClaimCandidate(
        entity_anchor="zendesk",
        entity_domain="zendesk.com",
        requirement_anchor="Slack   integration",
        fact_category="integration",
        text="Slack can connect to Zendesk.",
        query="Zendesk Slack connection",
    )

    assert first.entity_domain == "zendesk.com"
    assert paraphrase.comparison_key == first.comparison_key
    assert first.model_dump()["comparison_key"] == first.comparison_key


def test_claim_candidate_preserves_distinct_requirement_identities() -> None:
    first = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="共享收件箱",
        fact_category="shared_inbox",
        text="The product has a shared inbox.",
        query="Acme shared inbox",
    )
    second = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="知识库",
        fact_category="knowledge_base",
        text="The product has a knowledge base.",
        query="Acme knowledge base",
    )

    assert first.comparison_key != second.comparison_key
    assert first.comparison_key.startswith("v5_entity_")


def test_claim_candidate_rejects_non_domain_vendor_identity() -> None:
    with pytest.raises(ValidationError):
        ClaimCandidate(
            entity_anchor="IBM",
            entity_domain="International Business Machines",
            requirement_anchor="security",
            fact_category="security_certification",
            text="The vendor has a security claim.",
            query="IBM security",
        )


@pytest.mark.parametrize("domain", ["co.uk", "github.io"])
def test_claim_candidate_rejects_public_suffix_as_vendor_domain(domain: str) -> None:
    with pytest.raises(ValueError, match="registrable domain"):
        ClaimCandidate(
            entity_anchor="Acme",
            entity_domain=domain,
            requirement_anchor="SSO",
            fact_category="integration",
            text="Acme supports SSO",
            query="Acme SSO",
        )


def test_claim_candidate_rejects_non_apex_vendor_domain() -> None:
    with pytest.raises(ValueError, match="apex domain"):
        ClaimCandidate(
            entity_anchor="Intercom",
            entity_domain="support.intercom.com",
            requirement_anchor="SSO",
            fact_category="integration",
            text="Intercom supports SSO",
            query="Intercom SSO",
        )


def test_claim_candidate_rejects_whitespace_only_anchors() -> None:
    with pytest.raises(ValidationError):
        ClaimCandidate(
            entity_anchor="   ",
            entity_domain="acme.com",
            requirement_anchor="security",
            fact_category="security_certification",
            text="The vendor has a security claim.",
            query="Acme security",
        )


def test_requirement_anchor_canonicalization_preserves_specific_checks() -> None:
    assert canonicalize_requirement_anchor("shared inbox") == "shared inbox"
    assert canonicalize_requirement_anchor("Must have a shared inbox") == (
        "shared inbox"
    )
    assert canonicalize_requirement_anchor("Prefer month-to-month billing") == (
        "month-to-month billing"
    )
    assert canonicalize_requirement_anchor("99.9% uptime") == "99.9% uptime"
    assert canonicalize_requirement_anchor("$0.05 per request") == ("$0.05 per request")
    assert canonicalize_requirement_anchor("Acme must support SSO") == "sso"
    assert canonicalize_requirement_anchor("Security is required") == "security"


@pytest.mark.parametrize(
    "label",
    ["Features include", "Features are", "Must-haves are"],
)
def test_requirement_anchor_canonicalization_strips_feature_list_labels(
    label: str,
) -> None:
    assert canonicalize_requirement_anchor(f"{label} SSO") == "sso"


def test_requirement_anchor_canonicalization_preserves_passive_subject() -> None:
    assert canonicalize_requirement_anchor("SSO must be supported") == "sso"
    assert canonicalize_requirement_anchor("SCIM should be included") == "scim"

    sso = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="SSO must be supported",
        fact_category="integration",
        text="Acme supports SSO",
        query="Acme SSO",
    )
    scim = sso.model_copy(
        update={
            "requirement_anchor": "SCIM must be supported",
            "text": "Acme supports SCIM",
            "query": "Acme SCIM",
        }
    )
    assert sso.comparison_key != scim.comparison_key


def test_directive_variants_derive_the_same_comparison_key() -> None:
    short = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="shared inbox",
        fact_category="shared_inbox",
        text="Acme has a shared inbox.",
        query="Acme shared inbox",
    )
    long = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="Must have a shared inbox",
        fact_category="shared_inbox",
        text="Acme offers a shared inbox.",
        query="Acme shared inbox",
    )

    assert long.comparison_key == short.comparison_key


def test_comparison_key_uses_brief_entity_and_ignores_category() -> None:
    acronym = ClaimCandidate(
        entity_anchor="IBM",
        entity_domain="ibm.com",
        requirement_anchor="SOC 2",
        fact_category="security_certification",
        text="IBM has SOC 2.",
        query="IBM SOC 2",
    )
    full_name = ClaimCandidate(
        entity_anchor="IBM",
        entity_domain="ibm.com",
        requirement_anchor="SOC 2",
        fact_category="compliance",
        text="IBM maintains SOC 2 compliance.",
        query="IBM SOC 2 compliance",
    )
    namesake = ClaimCandidate(
        entity_anchor="Other IBM",
        entity_domain="ibm.com",
        requirement_anchor="SOC 2",
        fact_category="compliance",
        text="Another IBM has SOC 2.",
        query="IBM example SOC 2",
    )

    assert full_name.comparison_key == acronym.comparison_key
    assert namesake.comparison_key != acronym.comparison_key


def test_brief_atoms_stabilize_nested_anchors_and_keep_distinct_items() -> None:
    brief = (
        "Compare Microsoft Teams, Microsoft Dynamics 365, and Jira. "
        "Must support SSO and SCIM. Must have Slack integration."
    )

    assert canonicalize_brief_anchor(brief, "Microsoft", entity=True) is None
    assert canonicalize_brief_anchor(brief, "Teams", entity=True) is None
    assert (
        canonicalize_brief_anchor(
            "Compare Crisp for a five-person team.", "Crisp", entity=True
        )
        == "crisp"
    )
    assert canonicalize_brief_anchor(brief, "integration", entity=False) == (
        "slack integration"
    )
    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert canonicalize_brief_anchor(brief, "SCIM", entity=False) == "scim"
    assert canonicalize_brief_anchor(brief, "me", entity=True) is None


def test_brief_atoms_split_common_vendor_comparison_syntax() -> None:
    assert (
        canonicalize_brief_anchor(
            "Compare Acme with Beta. Must support SSO.", "Acme", entity=True
        )
        == "acme"
    )
    assert (
        canonicalize_brief_anchor(
            "Compare Acme with Beta. Must support SSO.", "Beta", entity=True
        )
        == "beta"
    )
    assert (
        canonicalize_brief_anchor(
            "Compare Acme & Beta. Must support SSO.", "Acme", entity=True
        )
        == "acme"
    )
    assert (
        canonicalize_brief_anchor(
            "Compare Acme & Beta. Must support SSO.", "Beta", entity=True
        )
        == "beta"
    )
    assert (
        canonicalize_brief_anchor(
            "Compare Procter & Gamble and Unilever.",
            "Procter & Gamble",
            entity=True,
        )
        == "procter & gamble"
    )


@pytest.mark.parametrize("separator", ["&", "+", "/"])
def test_symbolic_separator_splits_tail_of_multi_vendor_list(separator: str) -> None:
    brief = f"Compare Acme, Beta {separator} Gamma. Must support SSO."

    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    for entity in ("Acme", "Beta", "Gamma"):
        assert (
            canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
        )


@pytest.mark.parametrize(
    "brief",
    [
        "Compare support platforms. Options: Intercom, Zendesk, and Crisp.",
        "Compare support platforms. Options are Intercom, Zendesk, and Crisp.",
        "Compare support platforms.\nOptions:\n- Intercom\n- Zendesk\n- Crisp",
    ],
)
def test_brief_atoms_accept_vendor_lists_outside_comparison_clause(
    brief: str,
) -> None:
    assert canonicalize_brief_anchor(brief, "Intercom", entity=True) == "intercom"
    assert canonicalize_brief_anchor(brief, "Zendesk", entity=True) == "zendesk"
    assert canonicalize_brief_anchor(brief, "Crisp", entity=True) == "crisp"
    assert {"intercom", "zendesk", "crisp"} <= comparison_entity_hints(brief)


def test_review_requirement_does_not_override_vendor_identity() -> None:
    brief = "We use Intercom. Review current pricing and shared inbox support."

    assert comparison_entity_hints(brief) == set()
    assert canonicalize_brief_anchor(brief, "Intercom", entity=True) == "intercom"
    assert canonicalize_brief_anchor(brief, "pricing", entity=False) == "pricing"


@pytest.mark.parametrize(
    "brief",
    [
        "Review Acme. Billing options are monthly or annual. Must support SSO.",
        "Review Acme. Options are Basic, Pro, and Enterprise. Must support SSO.",
    ],
)
def test_non_vendor_options_do_not_override_entity_identity(brief: str) -> None:
    assert comparison_entity_hints(brief) == set()
    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"


def test_explicit_vendor_list_still_rejects_unlisted_entity() -> None:
    brief = "Compare Intercom and Zendesk. Mercury appears only in a note."

    assert canonicalize_brief_anchor(brief, "Mercury", entity=True) is None


@pytest.mark.parametrize(
    "brief",
    [
        "Compare vendors Acme and Beta. Must support SSO.",
        "Compare the vendors Acme and Beta. Must support SSO.",
        "Compare software vendors Acme and Beta. Must support SSO.",
        "Compare options Acme and Beta. Must support SSO.",
        "Evaluate vendors: Acme, Beta, and Gamma. Must support SSO.",
        "Candidates include Acme, Beta, and Gamma. Must support SSO.",
        "Vendors include Acme, Beta, and Gamma. Must support SSO.",
    ],
)
def test_comparison_descriptors_are_not_part_of_first_vendor(brief: str) -> None:
    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(brief, "Beta", entity=True) == "beta"


@pytest.mark.parametrize(
    "label",
    ["Features include", "Features are", "Must-haves are"],
)
def test_brief_atoms_accept_global_feature_lists(label: str) -> None:
    brief = f"Compare Acme and Beta. {label} SSO, SCIM, and audit logs."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert brief_anchor_association_valid(brief, "Acme", "SSO")


def test_repeated_vendor_mentions_keep_the_exact_entity_identity() -> None:
    brief = "Compare Acme and Beta. Acme must support SSO."

    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"
    possessive = "Compare Acme and Beta. Acme's security must include SSO."
    assert canonicalize_brief_anchor(possessive, "Acme", entity=True) == "acme"


def test_repeated_requirement_anchor_converges_across_vendor_clauses() -> None:
    brief = "Acme must support SSO. Beta must support SSO."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"


def test_budget_label_and_value_share_one_requirement_identity() -> None:
    brief = "Compare Acme and Beta. Budget: US$100 per month."

    assert canonicalize_brief_anchor(brief, "Budget", entity=False) == (
        "us$100 per month"
    )
    assert canonicalize_brief_anchor(brief, "US$100 per month", entity=False) == (
        "us$100 per month"
    )


def test_budget_label_stops_before_a_separate_clause() -> None:
    brief = "Compare Acme. Budget: $100 per month, for five users."

    assert canonicalize_brief_anchor(brief, "Budget", entity=False) == (
        "$100 per month"
    )
    assert canonicalize_brief_anchor(brief, "$100 per month", entity=False) == (
        "$100 per month"
    )


def test_decimal_budget_label_preserves_the_complete_value() -> None:
    brief = "Compare Acme. Budget: $0.05 per request."

    assert canonicalize_brief_anchor(brief, "Budget", entity=False) == (
        "$0.05 per request"
    )
    assert canonicalize_brief_anchor(brief, "$0.05 per request", entity=False) == (
        "$0.05 per request"
    )


def test_thousands_separators_remain_part_of_labeled_budget_values() -> None:
    brief = "Compare Acme. Budget: $1,000/month. Price: $1,500/year."

    assert canonicalize_brief_anchor(brief, "Budget", entity=False) == "$1,000/month"
    assert canonicalize_brief_anchor(brief, "Price", entity=False) == "$1,500/year"


def test_alternate_requirement_separators_keep_distinct_checks() -> None:
    slash = "Compare Acme. Must support SSO/SCIM."
    plus = "Compare Acme. Must support SSO + SCIM."
    chinese = "比较飞书。需要知识库和共享收件箱。"

    assert canonicalize_brief_anchor(slash, "SSO", entity=False) == "sso"
    assert canonicalize_brief_anchor(slash, "SCIM", entity=False) == "scim"
    assert canonicalize_brief_anchor(plus, "SSO", entity=False) == "sso"
    assert canonicalize_brief_anchor(plus, "SCIM", entity=False) == "scim"
    assert canonicalize_brief_anchor(chinese, "知识库", entity=False) == ("知识库")
    assert canonicalize_brief_anchor(chinese, "共享收件箱", entity=False) == (
        "共享收件箱"
    )


def test_two_vendor_prepositions_keep_distinct_entity_identities() -> None:
    to_brief = "Compare Acme to Beta. Must support SSO."
    against_brief = "Evaluate Acme against Beta. Must support SSO."

    assert canonicalize_brief_anchor(to_brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(to_brief, "Beta", entity=True) == "beta"
    assert canonicalize_brief_anchor(against_brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(against_brief, "Beta", entity=True) == "beta"


def test_entity_name_ending_in_generic_word_is_preserved() -> None:
    brief = "Compare Acme and Acme Security. Must support SSO."

    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(brief, "Acme Security", entity=True) == (
        "acme security"
    )
    assert (
        canonicalize_brief_anchor("Compare Acme Security.", "Acme", entity=True) is None
    )


def test_entity_alias_and_internal_dot_expand_to_stable_complete_names() -> None:
    aws = "Compare Amazon Web Services (AWS) and Azure. Must support SSO."
    monday = "Compare Monday.com and Jira. Must support SSO."

    assert (
        canonicalize_brief_anchor(aws, "Amazon Web Services", entity=True)
        == "amazon web services"
    )
    assert canonicalize_brief_anchor(monday, "Monday", entity=True) is None


def test_polite_comparison_prefixes_are_not_part_of_entity_identity() -> None:
    for brief in (
        "Please compare Intercom and Zendesk. Must support SSO.",
        "Can you compare Intercom and Zendesk? Must support SSO.",
        "We are evaluating Intercom against Zendesk. Must support SSO.",
        "I'm comparing Intercom and Zendesk. Must support SSO.",
    ):
        assert canonicalize_brief_anchor(brief, "Intercom", entity=True) == ("intercom")


def test_repeated_short_alias_uses_earlier_complete_entity_identity() -> None:
    brief = "Compare Microsoft Teams and Slack. Teams must support SSO."

    assert canonicalize_brief_anchor(brief, "Teams", entity=True) is None

    repeated = (
        "Compare Microsoft Teams and Slack. Teams must support SSO. "
        "Teams must support SCIM."
    )
    assert canonicalize_brief_anchor(repeated, "Teams", entity=True) is None


def test_distinct_short_name_precedes_and_is_not_merged_into_longer_entity() -> None:
    brief = "Compare Acme and Acme Pro. Acme must support SSO."

    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"

    reversed_brief = "Compare Acme Pro and Acme. Acme must support SSO."
    assert canonicalize_brief_anchor(reversed_brief, "Acme", entity=True) == "acme"


def test_comparison_key_ignores_verified_domain_aliases() -> None:
    dot_com = ClaimCandidate(
        entity_anchor="Mercury",
        entity_domain="mercury.com",
        requirement_anchor="SSO",
        fact_category="integration",
        text="Mercury supports SSO",
        query="Mercury SSO",
    )
    dot_ai = dot_com.model_copy(update={"entity_domain": "mercury.ai"})

    assert dot_com.comparison_key == dot_ai.comparison_key


def test_comparison_key_ignores_sentence_final_period_variation() -> None:
    punctuated = ClaimCandidate(
        entity_anchor="Acme Inc.",
        entity_domain="acme.com",
        requirement_anchor="pricing.",
        fact_category="pricing",
        text="Acme Inc. pricing.",
        query="Acme Inc. pricing",
    )
    plain = punctuated.model_copy(
        update={"entity_anchor": "Acme Inc", "requirement_anchor": "pricing"}
    )

    assert punctuated.comparison_key == plain.comparison_key


def test_vendor_scoped_budget_cannot_be_assigned_to_another_vendor() -> None:
    brief = (
        "Compare Acme and Beta. Budget for Acme: $100/month. "
        "Budget for Beta: $200/month."
    )

    assert brief_anchor_association_valid(brief, "Acme", "$100/month") is True
    assert brief_anchor_association_valid(brief, "Beta", "$100/month") is False
    assert brief_anchor_association_valid(brief, "Beta", "$200/month") is True


def test_global_team_scope_remains_valid_for_each_vendor() -> None:
    brief = "Compare Acme and Beta. Must support SSO for five users."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize(
    "directive",
    [
        "Our team needs SSO",
        "We require SSO",
        "The vendor must support SSO",
        "Every option should include SSO",
        "Requirements: SSO",
    ],
)
def test_subject_prefixed_global_requirements_apply_to_each_vendor(
    directive: str,
) -> None:
    brief = f"Compare Acme and Beta. {directive}."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize(
    "subject",
    [
        "The solution",
        "The product",
        "The tool",
        "The platform",
        "The software",
        "Both vendors",
        "All candidates",
        "Every candidate",
        "Each option",
    ],
)
def test_solution_scoped_requirements_apply_to_each_vendor(subject: str) -> None:
    brief = f"Compare Acme and Beta. {subject} must support SSO."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


def test_passive_global_requirements_remain_distinct_and_apply_to_each_vendor() -> None:
    brief = "Compare Acme and Beta. SSO must be supported. SCIM must be supported."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert canonicalize_brief_anchor(brief, "SCIM", entity=False) == "scim"
    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SCIM") is True


def test_subject_prefixed_global_requirement_resets_prior_vendor_scope() -> None:
    brief = "Compare Acme and Beta. Acme supports SSO, but our team needs SCIM."

    assert brief_anchor_association_valid(brief, "Acme", "SCIM") is True
    assert brief_anchor_association_valid(brief, "Beta", "SCIM") is True


@pytest.mark.parametrize("quantifier", ["Both", "Each"])
def test_quantified_global_requirements_apply_to_each_vendor(quantifier: str) -> None:
    brief = f"Compare Acme and Beta. {quantifier} must support SSO."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


def test_requirements_are_list_is_canonical_and_global() -> None:
    brief = "Compare Acme and Beta. Requirements are SSO and SCIM."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert canonicalize_brief_anchor(brief, "SCIM", entity=False) == "scim"
    for entity in ("Acme", "Beta"):
        assert brief_anchor_association_valid(brief, entity, "SSO") is True
        assert brief_anchor_association_valid(brief, entity, "SCIM") is True


def test_nested_vendor_scope_uses_the_complete_name() -> None:
    brief = "Compare Acme and Acme Pro. Acme Pro must support SSO."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is False
    assert brief_anchor_association_valid(brief, "Acme Pro", "SSO") is True


def test_one_directive_can_scope_multiple_named_vendors() -> None:
    brief = "Compare Acme and Beta. Acme and Beta must support SSO."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize(
    "directive",
    [
        "Acme and Beta need to support SSO.",
        "Acme and Beta should be able to support SSO.",
        "Acme and Beta need to offer SSO.",
    ],
)
def test_infinitive_directive_scopes_every_named_vendor(directive: str) -> None:
    brief = f"Compare Acme and Beta. {directive}"

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize("subject", ["The vendors", "Our vendors", "The options"])
def test_plural_global_subject_applies_to_every_vendor(subject: str) -> None:
    brief = f"Compare Acme and Beta. {subject} must support SSO."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize(
    "brief,requirements",
    [
        ("Compare Acme and Beta. SSO and SCIM are required.", ("SSO", "SCIM")),
        (
            "Compare Acme and Beta. A shared inbox and chatbot are required.",
            ("shared inbox", "chatbot"),
        ),
    ],
)
def test_passive_requirement_lists_apply_each_item_to_every_vendor(
    brief: str, requirements: tuple[str, str]
) -> None:
    for entity in ("Acme", "Beta"):
        for requirement in requirements:
            assert brief_anchor_association_valid(brief, entity, requirement) is True


@pytest.mark.parametrize(
    "entity",
    ["Johnson and Johnson", "Marks and Spencer", "Monday.com"],
)
def test_complete_vendor_names_survive_association_checks(entity: str) -> None:
    brief = f"Compare {entity} with Beta. {entity} must support SSO."

    assert brief_anchor_association_valid(brief, entity, "SSO") is True


@pytest.mark.parametrize(
    "requirement",
    ["Slack integration", "major service issues"],
)
def test_global_list_tail_remains_associated_with_all_vendors(
    requirement: str,
) -> None:
    brief = (
        "Compare Intercom, Zendesk, and Crisp. Must have a shared inbox, "
        "chatbot, knowledge base, and Slack integration. Flag recent outages, "
        "pricing changes, or major service issues."
    )

    assert brief_anchor_association_valid(brief, "Intercom", requirement) is True


def test_price_constraint_label_and_value_share_one_requirement_identity() -> None:
    brief = "Compare Acme. Price under $100/month."

    assert canonicalize_brief_anchor(brief, "Price", entity=False) == "$100/month"
    assert canonicalize_brief_anchor(brief, "$100/month", entity=False) == (
        "$100/month"
    )


def test_query_must_mention_a_token_from_the_canonical_entity() -> None:
    assert (
        query_mentions_entity("microsoft teams", "Microsoft Teams SSO pricing") is True
    )
    assert query_mentions_entity("jira", "Jira SSO current") is True
    assert query_mentions_entity("acme", "Evil SSO") is False
    assert query_mentions_entity("飞书", "飞书 知识库") is True
    assert (
        query_mentions_entity("Microsoft Teams", "Microsoft Dynamics 365 SSO") is False
    )
    assert query_mentions_entity("Google Cloud", "Google Workspace pricing") is False
    assert query_mentions_entity("Acme Pro", "Acme Basic pricing") is False
    assert query_mentions_entity("Acme", "Acmeify SSO") is False
    assert query_mentions_entity("AT&T", "pricing at enterprise scale") is False
    assert query_mentions_entity("AT&T", "AT&T enterprise pricing") is True
    assert query_mentions_entity("Google Cloud", "Google Workspace cloud") is False
    assert query_mentions_entity("飞书", "超级飞书 知识库") is False
    assert query_mentions_entity("飞书", "飞书通 知识库") is False
    assert query_mentions_entity("飞书", "飞书官网") is True


def test_exact_requirement_is_preserved_before_a_longer_related_check() -> None:
    brief = "Compare Acme. Must support SSO. Must support SSO provisioning."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert (
        canonicalize_brief_anchor(brief, "SSO provisioning", entity=False)
        == "sso provisioning"
    )


def test_non_for_comparison_scope_preserves_each_requirement_anchor() -> None:
    brief = "Evaluate Salesforce vs. HubSpot on price, support, and reporting."

    for requirement in ("price", "support", "reporting"):
        assert canonicalize_brief_anchor(
            brief, requirement, entity=False
        ) == requirement


def test_single_vendor_use_statement_is_not_a_conjoined_company_name() -> None:
    brief = "We use Jira and need SSO and audit logs."

    assert canonicalize_brief_anchor(brief, "Jira", entity=True) == "jira"


def test_legal_abbreviation_is_preserved_when_splitting_requirement_clauses() -> None:
    brief = "Compare Acme Inc. and Beta. Acme Inc. supports SSO."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"


def test_chinese_comparison_prefix_is_removed_from_entity_identity() -> None:
    brief = "比较飞书和钉钉。需要知识库。"

    assert canonicalize_brief_anchor(brief, "飞书", entity=True) == "飞书"
    assert canonicalize_brief_anchor(brief, "钉钉", entity=True) == "钉钉"


def test_partial_repeated_compound_entity_is_rejected() -> None:
    for brief in (
        "Compare Johnson and Johnson with Pfizer. Must support SSO.",
        "Compare Johnson & Johnson and Pfizer. Must support SSO.",
    ):
        assert canonicalize_brief_anchor(brief, "Johnson", entity=True) is None


def test_legal_name_period_preserves_the_following_shared_scope() -> None:
    brief = "Compare Apple Inc. and Microsoft Corp. Both must support SSO."

    assert canonicalize_brief_anchor(brief, "Apple Inc.", entity=True) == "apple inc."
    assert canonicalize_brief_anchor(brief, "Microsoft Corp.", entity=True) == (
        "microsoft corp."
    )


def test_ampersands_inside_two_compared_company_names_are_preserved() -> None:
    brief = "Compare Johnson & Johnson and Procter & Gamble. Must support SSO."

    assert comparison_entity_hints(brief) == {
        "johnson & johnson",
        "procter & gamble",
    }
    for entity in ("Johnson & Johnson", "Procter & Gamble"):
        assert canonicalize_brief_anchor(
            brief, entity, entity=True
        ) == entity.casefold()


def test_ampersand_company_at_end_of_comma_vendor_list_is_preserved() -> None:
    brief = "Compare Zendesk, Intercom, and Johnson & Johnson. Must support SSO."

    assert comparison_entity_hints(brief) == {
        "zendesk",
        "intercom",
        "johnson & johnson",
    }
    assert canonicalize_brief_anchor(
        brief, "Johnson & Johnson", entity=True
    ) == "johnson & johnson"


def test_slash_delimited_vendor_scopes_do_not_cross_wire_requirements() -> None:
    brief = "Compare Acme and Beta. Acme requires SSO / Beta requires SCIM."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Acme", "SCIM") is False
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is False
    assert brief_anchor_association_valid(brief, "Beta", "SCIM") is True


def test_labeled_rate_prefix_maps_to_the_complete_rate() -> None:
    brief = "Compare Acme. Budget: US$100/month."

    assert canonicalize_brief_anchor(brief, "US$100", entity=False) == ("us$100/month")


def test_unicode_anchor_can_be_extracted_from_directive_wording() -> None:
    assert canonicalize_brief_anchor("需要知识库。", "知识库", entity=False) == (
        "知识库"
    )


def test_unicode_partial_entity_anchor_is_rejected() -> None:
    assert canonicalize_brief_anchor("飞书。需要知识库。", "飞", entity=True) is None
    assert query_mentions_entity("飞书", "飞 知识库") is False


def test_explicit_brief_domain_is_bound_to_its_entity() -> None:
    brief = "Compare Mercury (mercury.com) and Beta. Must support SSO."

    assert brief_domain_for_entity(brief, "Mercury") == "mercury.com"
    assert brief_domain_for_entity(brief, "Beta") is None


def test_annotated_final_vendor_remains_bound_before_shared_scope() -> None:
    brief = (
        "Compare Intercom (intercom.com), Zendesk (zendesk.com), and "
        "Crisp (crisp.chat) for a five-person SaaS team."
    )

    assert canonicalize_brief_anchor(brief, "Crisp", entity=True) == "crisp"
    assert comparison_entity_hints(brief) == {"intercom", "zendesk", "crisp"}
    for entity in ("Intercom", "Zendesk", "Crisp"):
        assert brief_anchor_association_valid(brief, entity, "five-person SaaS team")


def test_trailing_shared_scope_applies_to_every_compared_vendor() -> None:
    brief = "Compare Intercom, Zendesk, and Crisp for a five-person SaaS team."

    for entity in ("Intercom", "Zendesk", "Crisp"):
        assert brief_anchor_association_valid(brief, entity, "five-person SaaS team")


@pytest.mark.parametrize("scope", ["10 users", "five users", "customer support", "SSO"])
def test_trailing_shared_scopes_do_not_attach_to_last_vendor(
    scope: str,
) -> None:
    brief = f"Compare Acme, Beta, and Gamma for {scope}."

    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    for entity in ("Acme", "Beta", "Gamma"):
        assert brief_anchor_association_valid(brief, entity, scope) is True


def test_vendor_scoped_pricing_conjuncts_do_not_cross_wire() -> None:
    brief = (
        "Compare Acme and Beta. Acme costs under $100/month and "
        "Beta costs under $200/month."
    )

    first = canonicalize_brief_anchor(brief, "$100/month", entity=False)
    second = canonicalize_brief_anchor(brief, "$200/month", entity=False)
    assert brief_anchor_association_valid(brief, "Acme", first or "") is True
    assert brief_anchor_association_valid(brief, "Beta", first or "") is False
    assert brief_anchor_association_valid(brief, "Beta", second or "") is True
    assert brief_anchor_association_valid(brief, "Acme", second or "") is False


def test_comma_inside_scoped_requirement_does_not_cross_wire() -> None:
    brief = (
        "Compare Acme and Beta. Acme must support SOC 2, Type II; "
        "Beta must support SCIM."
    )

    requirement = canonicalize_brief_anchor(brief, "SOC 2, Type II", entity=False)
    assert requirement == "soc 2, type ii"
    assert brief_anchor_association_valid(brief, "Acme", requirement) is True
    assert brief_anchor_association_valid(brief, "Beta", requirement) is False


@pytest.mark.parametrize(
    "separator",
    [
        "while",
        "but",
        "whereas",
        "yet",
        "although",
        "though",
        "plus",
        "as well as",
        "however",
        "then",
    ],
)
def test_vendor_scoped_transition_clauses_do_not_cross_wire(separator: str) -> None:
    brief = f"Compare Acme and Beta. Acme needs SSO {separator} Beta needs SCIM."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is False
    assert brief_anchor_association_valid(brief, "Beta", "SCIM") is True
    assert brief_anchor_association_valid(brief, "Acme", "SCIM") is False
    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert canonicalize_brief_anchor(brief, "SCIM", entity=False) == "scim"


@pytest.mark.parametrize(
    "brief,first,second",
    [
        (
            "Compare Acme and Beta. Acme needs SSO and Beta SCIM.",
            "SSO",
            "SCIM",
        ),
        (
            "Compare Acme and Beta. Acme costs under $100/month and "
            "Beta under $200/month.",
            "$100/month",
            "$200/month",
        ),
    ],
)
def test_vendor_scoped_elliptical_clauses_do_not_cross_wire(
    brief: str, first: str, second: str
) -> None:
    first_anchor = canonicalize_brief_anchor(brief, first, entity=False)
    second_anchor = canonicalize_brief_anchor(brief, second, entity=False)

    assert first_anchor is not None
    assert second_anchor is not None
    assert brief_anchor_association_valid(brief, "Acme", first_anchor) is True
    assert brief_anchor_association_valid(brief, "Beta", first_anchor) is False
    assert brief_anchor_association_valid(brief, "Beta", second_anchor) is True
    assert brief_anchor_association_valid(brief, "Acme", second_anchor) is False


@pytest.mark.parametrize(
    "brief,requirement",
    [
        ("Compare Acme and Beta. Acme needs SSO, SCIM. Beta needs chatbot.", "SCIM"),
        (
            "Compare Acme and Beta. Acme supports SSO, SCIM, audit logs; "
            "Beta supports chatbot.",
            "audit logs",
        ),
        (
            "Compare Acme and Beta. Acme costs $100/month, includes support. "
            "Beta costs $200/month.",
            "includes support",
        ),
    ],
)
def test_vendor_scoped_list_continuations_inherit_vendor(
    brief: str, requirement: str
) -> None:
    assert brief_anchor_association_valid(brief, "Acme", requirement) is True
    assert brief_anchor_association_valid(brief, "Beta", requirement) is False


def test_newline_vendor_clauses_do_not_cross_wire() -> None:
    brief = "Compare Acme and Beta.\nAcme needs SSO\nBeta needs SCIM"

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is False
    assert brief_anchor_association_valid(brief, "Beta", "SCIM") is True
    assert brief_anchor_association_valid(brief, "Acme", "SCIM") is False


def test_bulleted_global_requirements_apply_to_compared_vendors() -> None:
    brief = "Compare:\n- Acme\n- Beta\nRequirements:\n- SSO\n- SCIM"

    assert comparison_entity_hints(brief) == {"acme", "beta"}
    for entity in ("Acme", "Beta"):
        assert brief_anchor_association_valid(brief, entity, "SSO") is True
        assert brief_anchor_association_valid(brief, entity, "SCIM") is True


def test_numbered_vendor_list_preserves_each_entity() -> None:
    brief = "Compare:\n1. Acme\n2. Beta\n3. Gamma\nRequirements: SSO."

    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    for entity in ("Acme", "Beta", "Gamma"):
        assert (
            canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
        )


@pytest.mark.parametrize("separator", [";", "；"])
def test_semicolon_delimited_vendor_lists(separator: str) -> None:
    brief = f"Compare Acme{separator} Beta{separator} Gamma. Must support SSO."

    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    for entity in ("Acme", "Beta", "Gamma"):
        assert (
            canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
        )


def test_ideographic_commas_split_chinese_entities_and_requirements() -> None:
    brief = "比较飞书、钉钉和企业微信。需要知识库、共享收件箱。"

    for entity in ("飞书", "钉钉", "企业微信"):
        assert canonicalize_brief_anchor(brief, entity, entity=True) == entity
    assert canonicalize_brief_anchor(brief, "知识库", entity=False) == "知识库"
    assert canonicalize_brief_anchor(brief, "共享收件箱", entity=False) == (
        "共享收件箱"
    )


def test_chinese_vendor_scoped_requirements_do_not_cross_wire() -> None:
    brief = "比较甲公司和乙公司。甲公司必须支持共享收件箱，乙公司必须支持聊天机器人。"

    assert brief_anchor_association_valid(brief, "甲公司", "共享收件箱") is True
    assert brief_anchor_association_valid(brief, "乙公司", "共享收件箱") is False
    assert brief_anchor_association_valid(brief, "乙公司", "聊天机器人") is True
    assert brief_anchor_association_valid(brief, "甲公司", "聊天机器人") is False


@pytest.mark.parametrize(
    "brief",
    [
        "比较甲公司（acme.cn）和乙公司。",
        "比较甲公司(acme.cn)和乙公司。",
        "比较 甲公司（acme.cn）和乙公司。",
        "比较甲公司 (acme.cn) 和乙公司。",
    ],
)
def test_chinese_entity_is_bound_to_adjacent_explicit_domain(brief: str) -> None:
    assert canonicalize_brief_anchor(brief, "甲公司", entity=True) == "甲公司"
    assert brief_domain_for_entity(brief, "甲公司") == "acme.cn"


def test_full_url_annotation_does_not_split_entity_identity() -> None:
    brief = "Compare Acme (https://acme.com) and Beta (https://beta.example)."

    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(brief, "Beta", entity=True) == "beta"
    assert brief_domain_for_entity(brief, "Acme") == "acme.com"


@pytest.mark.parametrize(
    "brief",
    [
        "Compare Acme [acme.com] and Beta [beta.example]. Must support SSO.",
        "Compare Acme {acme.com} and Beta {beta.example}. Must support SSO.",
    ],
)
def test_bracketed_domain_annotations_do_not_change_entity_identity(
    brief: str,
) -> None:
    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(brief, "Beta", entity=True) == "beta"
    assert comparison_entity_hints(brief) == {"acme", "beta"}
    assert brief_domain_for_entity(brief, "Acme") == "acme.com"


def test_domain_annotation_in_model_entity_anchor_maps_to_bare_identity() -> None:
    brief = "Compare Acme (https://acme.com) and Beta. Must support SSO."

    assert canonicalize_brief_anchor(
        brief, "Acme (https://acme.com)", entity=True
    ) == canonicalize_brief_anchor(brief, "Acme", entity=True)


def test_legal_abbreviation_does_not_hide_later_vendor() -> None:
    brief = "Compare Acme, Inc. and Beta. Must support SSO."

    assert canonicalize_brief_anchor(brief, "Acme, Inc.", entity=True) == "acme, inc."
    assert canonicalize_brief_anchor(brief, "Beta", entity=True) == "beta"
    assert comparison_entity_hints(brief) == {"acme, inc.", "beta"}


@pytest.mark.parametrize("suffix", ["Company", "Corporation", "Limited"])
def test_full_legal_suffix_does_not_keep_sentence_period(suffix: str) -> None:
    brief = f"Compare Bain and McKinsey & {suffix}. Must support SSO."
    entity = f"McKinsey & {suffix}"

    assert canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
    assert entity.casefold() in comparison_entity_hints(brief)


def test_comparison_and_legal_abbreviation_periods_are_contextual() -> None:
    versus = "Compare Acme vs. Beta. Must support SSO."
    legal_suffix = "Compare Acme and Beta Inc. Must support SSO."

    assert canonicalize_brief_anchor(versus, "Beta", entity=True) == "beta"
    assert comparison_entity_hints(versus) == {"acme", "beta"}
    assert canonicalize_brief_anchor(legal_suffix, "Beta Inc.", entity=True) == (
        "beta inc."
    )
    assert comparison_entity_hints(legal_suffix) == {"acme", "beta inc."}
    assert brief_anchor_association_valid(legal_suffix, "Beta Inc.", "SSO") is True


def test_annotated_legal_names_remain_in_comma_separated_vendor_list() -> None:
    brief = (
        "Compare Acme Inc. (acme.com), Beta LLC (beta.example), and Crisp. "
        "Must support SSO."
    )

    assert canonicalize_brief_anchor(brief, "Acme Inc.", entity=True) == "acme inc."
    assert canonicalize_brief_anchor(brief, "Beta LLC", entity=True) == "beta llc"
    assert canonicalize_brief_anchor(brief, "Crisp", entity=True) == "crisp"
    assert comparison_entity_hints(brief) == {"acme inc.", "beta llc", "crisp"}


def test_stacked_legal_suffixes_keep_one_vendor_name() -> None:
    brief = "Compare Acme Co. Ltd. and Beta. Must support SSO."

    assert canonicalize_brief_anchor(brief, "Acme Co. Ltd.", entity=True) == (
        "acme co. ltd."
    )
    assert comparison_entity_hints(brief) == {"acme co. ltd.", "beta"}


@pytest.mark.parametrize("suffix", ["Pte. Ltd.", "Pty. Ltd."])
def test_dotted_multitoken_legal_suffix_keeps_complete_vendor_list(
    suffix: str,
) -> None:
    entity = f"Acme {suffix}"
    brief = f"Compare {entity} (acme.com), Beta, and Gamma. Must support SSO."

    assert comparison_entity_hints(brief) == {
        entity.casefold(),
        "beta",
        "gamma",
    }
    assert canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
    assert canonicalize_brief_anchor(brief, "Acme Pte", entity=True) is None


def test_sentence_period_after_digit_keeps_requirements_distinct() -> None:
    brief = "Compare Acme. Minimum version 5. SSO support."

    assert canonicalize_brief_anchor(brief, "Minimum version", entity=False) == (
        "minimum version 5"
    )
    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso support"


def test_repeated_budget_label_is_ambiguous_but_exact_values_are_stable() -> None:
    brief = "Acme budget: $100/month. Beta budget: $200/month."

    assert canonicalize_brief_anchor(brief, "budget", entity=False) is None
    assert canonicalize_brief_anchor(brief, "$100/month", entity=False) == (
        "$100/month"
    )
    assert canonicalize_brief_anchor(brief, "$200/month", entity=False) == (
        "$200/month"
    )


def test_copular_budget_constraint_maps_to_its_value() -> None:
    brief = "Compare Acme. Budget is $100 per month. Must support SSO."

    assert canonicalize_brief_anchor(brief, "Budget", entity=False) == (
        "$100 per month"
    )
    assert canonicalize_brief_anchor(brief, "$100 per month", entity=False) == (
        "$100 per month"
    )


@pytest.mark.parametrize(
    "brief",
    [
        "Compare Acme. Budget: $100/month and must support SSO.",
        "Compare Acme. Budget under $100/month and SSO is required.",
    ],
)
def test_budget_label_stops_before_next_requirement(brief: str) -> None:
    assert canonicalize_brief_anchor(brief, "Budget", entity=False) == "$100/month"
    assert canonicalize_brief_anchor(brief, "$100/month", entity=False) == (
        "$100/month"
    )
    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"


def test_budget_must_be_variants_share_one_requirement_identity() -> None:
    brief = "Compare Acme. Budget must be under $100/month."
    anchors = (
        "Budget",
        "$100/month",
        "under $100/month",
        "Budget must be under $100/month",
    )

    assert {
        canonicalize_brief_anchor(brief, anchor, entity=False) for anchor in anchors
    } == {"$100/month"}


def test_natural_sentence_preserves_exact_entity_anchor() -> None:
    assert (
        canonicalize_brief_anchor(
            "Our vendor is Acme. Must support SSO.", "Acme", entity=True
        )
        == "acme"
    )
    assert (
        canonicalize_brief_anchor(
            "Compare Acme and Beta for 5 users. Must support SSO.",
            "Beta",
            entity=True,
        )
        == "beta"
    )
    assert (
        canonicalize_brief_anchor(
            "Compare Acme and Beta for five users.", "five users", entity=False
        )
        == "five users"
    )
    assert (
        canonicalize_brief_anchor("Acme requires SSO.", "Acme", entity=True) == "acme"
    )
    assert canonicalize_brief_anchor("Acme needs SSO.", "Acme", entity=True) == "acme"


def test_trailing_comparison_scope_is_not_part_of_requirement() -> None:
    brief = "Compare Acme and Beta for teams requiring SSO and SCIM."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert canonicalize_brief_anchor(brief, "SCIM", entity=False) == "scim"


def test_shortlist_prefix_is_not_part_of_entity_identity() -> None:
    included = "Shortlist includes Intercom, Zendesk, and Crisp. Must support SSO."
    bare = "Shortlist Intercom, Zendesk, and Crisp. Must support SSO."

    for brief in (included, bare):
        assert canonicalize_brief_anchor(brief, "Intercom", entity=True) == "intercom"
        assert comparison_entity_hints(brief) == {"intercom", "zendesk", "crisp"}


def test_assessment_prefix_preserves_every_vendor_identity() -> None:
    brief = "Please assess Acme, Beta, and Gamma. Criteria include SSO."

    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    assert all(
        canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
        for entity in ("Acme", "Beta", "Gamma")
    )


def test_assessment_scope_is_not_part_of_requirement_identity() -> None:
    brief = "Assess Stripe versus Square regarding PCI compliance."

    assert canonicalize_brief_anchor(brief, "PCI compliance", entity=False) == (
        "pci compliance"
    )


def test_nonrepeated_conjoined_company_name_is_preserved() -> None:
    brief = "Compare Research and Markets and Gartner. Must support SSO."

    assert comparison_entity_hints(brief) == {"research and markets", "gartner"}
    assert canonicalize_brief_anchor(
        brief, "Research and Markets", entity=True
    ) == "research and markets"


def test_sentence_final_legal_suffix_matches_without_terminal_period() -> None:
    brief = "Compare Acme, Inc. and Beta, LLC. Must support SSO."

    assert canonicalize_brief_anchor(brief, "Beta, LLC", entity=True) == "beta, llc"


@pytest.mark.parametrize(
    "directive",
    ["we need SSO", "the team requires SSO"],
)
def test_budget_value_stops_before_subject_prefixed_directive(
    directive: str,
) -> None:
    brief = f"Compare Acme and Beta; our budget is $100/month and {directive}."

    assert canonicalize_brief_anchor(brief, "Budget", entity=False) == "$100/month"
    assert canonicalize_brief_anchor(brief, "$100/month", entity=False) == "$100/month"
    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"


@pytest.mark.parametrize(
    "brief",
    [
        "Compare Acme, Beta, and Gamma; must support SSO.",
        "Compare Acme, Beta, and Gamma — must support SSO.",
        "Evaluate Acme, Beta, and Gamma, all requiring SSO.",
        "Between Acme, Beta, and Gamma, we need SSO.",
    ],
)
def test_trailing_requirement_prose_is_not_a_vendor_identity(brief: str) -> None:
    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    assert canonicalize_brief_anchor(brief, "Gamma", entity=True) == "gamma"


def test_review_vendor_list_rejects_later_acronym_alias() -> None:
    brief = "Review International Business Machines and Oracle. IBM must support SSO."

    assert comparison_entity_hints(brief) == {
        "international business machines",
        "oracle",
    }
    assert canonicalize_brief_anchor(brief, "IBM", entity=True) is None


@pytest.mark.parametrize(
    "brief,alias",
    [
        ("Review monday.com and Jira. monday must support SSO.", "monday"),
        ("Review eBay and Amazon. Bay must support SSO.", "Bay"),
    ],
)
def test_stylized_brand_review_list_rejects_shortened_alias(
    brief: str, alias: str
) -> None:
    assert len(comparison_entity_hints(brief)) == 2
    assert canonicalize_brief_anchor(brief, alias, entity=True) is None


def test_partial_legal_and_conjoined_entity_names_are_rejected() -> None:
    cases = (
        ("Compare Procter & Gamble and Unilever.", "Procter"),
        ("Compare Marks and Spencer with Tesco.", "Marks"),
        ("Compare Acme, Inc. and Beta.", "Acme"),
    )

    for brief, anchor in cases:
        assert canonicalize_brief_anchor(brief, anchor, entity=True) is None


@pytest.mark.parametrize(
    "entity",
    ["Marks and Spencer", "Barnes and Noble", "Johnson and Johnson"],
)
def test_complete_conjoined_company_name_is_preserved(entity: str) -> None:
    brief = f"Compare {entity} with Pfizer. Must support SSO."

    assert canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()


@pytest.mark.parametrize(
    "brief,first,second",
    [
        (
            "Compare Johnson and Johnson and Pfizer. Must support SSO.",
            "Johnson and Johnson",
            "Pfizer",
        ),
        (
            "Compare Marks and Spencer with Tesco. Must support SSO.",
            "Marks and Spencer",
            "Tesco",
        ),
        (
            "Compare Procter & Gamble & Unilever. Must support SSO.",
            "Procter & Gamble",
            "Unilever",
        ),
    ],
)
def test_two_vendor_lists_preserve_conjoined_company_name(
    brief: str, first: str, second: str
) -> None:
    assert comparison_entity_hints(brief) == {first.casefold(), second.casefold()}
    assert canonicalize_brief_anchor(brief, first, entity=True) == first.casefold()
    assert canonicalize_brief_anchor(brief, second, entity=True) == second.casefold()


def test_plain_three_vendor_and_list_remains_three_entities() -> None:
    brief = "Compare Acme and Beta and Gamma. Must support SSO."

    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    for entity in ("Acme", "Beta", "Gamma"):
        assert (
            canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
        )


def test_supplier_label_is_not_part_of_first_entity() -> None:
    brief = "Compare suppliers Acme and Beta. Must support SSO."

    assert comparison_entity_hints(brief) == {"acme", "beta"}
    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"


@pytest.mark.parametrize("prefix", ["-", "1)", "(1)"])
def test_bullet_vendor_items_preserve_conjoined_names(prefix: str) -> None:
    second_prefix = "-" if prefix == "-" else ("2)" if prefix == "1)" else "(2)")
    brief = (
        f"Compare:\n{prefix} Marks and Spencer\n{second_prefix} Tesco\n"
        "Requirements:\n- SSO"
    )

    assert comparison_entity_hints(brief) == {"marks and spencer", "tesco"}
    assert (
        canonicalize_brief_anchor(brief, "Marks and Spencer", entity=True)
        == "marks and spencer"
    )


@pytest.mark.parametrize(
    "brief,first,second",
    [
        (
            "Compare Procter and Gamble vs Johnson and Johnson. Must support SSO.",
            "Procter and Gamble",
            "Johnson and Johnson",
        ),
        (
            "Compare Procter & Gamble vs Johnson & Johnson. Must support SSO.",
            "Procter & Gamble",
            "Johnson & Johnson",
        ),
        (
            "Compare Marks and Spencer with Barnes and Noble. Must support SSO.",
            "Marks and Spencer",
            "Barnes and Noble",
        ),
    ],
)
def test_pair_separator_preserves_two_conjoined_company_names(
    brief: str, first: str, second: str
) -> None:
    assert comparison_entity_hints(brief) == {first.casefold(), second.casefold()}
    assert canonicalize_brief_anchor(brief, first, entity=True) == first.casefold()
    assert canonicalize_brief_anchor(brief, second, entity=True) == second.casefold()


@pytest.mark.parametrize(
    "brief",
    [
        "Our shortlist is Salesforce, HubSpot, and Zoho. Must support SSO.",
        "The shortlist consists of Salesforce, HubSpot, and Zoho. Must support SSO.",
        "候选是 Salesforce、HubSpot 和 Zoho。必须支持 SSO。",
    ],
)
def test_list_introduction_is_not_part_of_first_vendor(brief: str) -> None:
    assert comparison_entity_hints(brief) == {"salesforce", "hubspot", "zoho"}
    assert canonicalize_brief_anchor(brief, "Salesforce", entity=True) == "salesforce"


def test_annotated_ampersand_vendor_rejects_partial_pair_members() -> None:
    brief = "Compare Procter & Gamble (pg.com). Must support SSO."

    assert canonicalize_brief_anchor(brief, "Procter & Gamble", entity=True) == (
        "procter & gamble"
    )
    assert canonicalize_brief_anchor(brief, "Procter", entity=True) is None
    assert canonicalize_brief_anchor(brief, "Gamble", entity=True) is None


def test_conjoined_company_name_is_preserved_in_comma_vendor_list() -> None:
    brief = "Compare Marks and Spencer, Tesco, and Pfizer. Must support SSO."

    assert (
        canonicalize_brief_anchor(brief, "Marks and Spencer", entity=True)
        == "marks and spencer"
    )


@pytest.mark.parametrize(
    "brief,entity",
    [
        ("Compare Disney+ and Netflix. Must support SSO.", "Disney+"),
        ("Compare C++ Builder and Visual Studio. Must support SSO.", "C++ Builder"),
        (
            "Compare Barnes & Noble, Tesco, and Pfizer. Must support SSO.",
            "Barnes & Noble",
        ),
    ],
)
def test_punctuation_inside_vendor_name_is_preserved(brief: str, entity: str) -> None:
    assert canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()


def test_partial_ampersand_company_name_is_rejected() -> None:
    brief = "Compare Barnes & Noble, Tesco, and Pfizer. Must support SSO."

    assert canonicalize_brief_anchor(brief, "Barnes", entity=True) is None
    assert canonicalize_brief_anchor(brief, "Noble", entity=True) is None


@pytest.mark.parametrize(
    "brief,entity,partial",
    [
        (
            "Compare U.S. Bank (usbank.com) and Mercury (mercury.com). "
            "Must support API access.",
            "U.S. Bank",
            "Bank",
        ),
        (
            "Compare J.P. Morgan and Mercury. Must support API access.",
            "J.P. Morgan",
            "Morgan",
        ),
        (
            "Compare P.F. Chang's and DoorDash. Must support API access.",
            "P.F. Chang's",
            "Chang's",
        ),
    ],
)
def test_dotted_initials_keep_complete_vendor_identity(
    brief: str, entity: str, partial: str
) -> None:
    hints = comparison_entity_hints(brief)

    assert entity.casefold() in hints
    assert canonicalize_brief_anchor(brief, entity, entity=True) == entity.casefold()
    assert canonicalize_brief_anchor(brief, partial, entity=True) is None


def test_sentence_final_initialism_does_not_cross_wire_next_vendor() -> None:
    brief = "Compare Acme and Beta. Acme operates in the U.S. Beta must support SSO."

    assert split_brief_sentences(brief) == [
        "Compare Acme and Beta",
        " Acme operates in the U.S",
        " Beta must support SSO",
        "",
    ]
    assert brief_anchor_association_valid(brief, "Acme", "SSO") is False
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


def test_legal_suffix_before_predicate_stays_in_same_sentence() -> None:
    brief = "Compare Acme Inc. and Beta. Acme Inc. supports SSO."

    assert split_brief_sentences(brief) == [
        "Compare Acme Inc. and Beta",
        " Acme Inc. supports SSO",
        "",
    ]
    assert brief_anchor_association_valid(brief, "Acme Inc.", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is False


@pytest.mark.parametrize(
    "brief,entity,requirement",
    [
        (
            "Compare Acme Inc. and Beta Inc. Acme Inc. currently supports SSO.",
            "Acme Inc.",
            "SSO",
        ),
        (
            "Compare Acme Inc. and Beta Inc. Acme Inc. recently changed pricing.",
            "Acme Inc.",
            "recently changed pricing",
        ),
    ],
)
def test_legal_suffix_before_adverbial_predicate_stays_scoped(
    brief: str, entity: str, requirement: str
) -> None:
    assert brief_anchor_association_valid(brief, entity, requirement) is True


def test_repeated_declarative_requirement_clauses_share_one_anchor() -> None:
    brief = "Compare Acme and Beta. Acme supports SSO. Beta supports SSO."

    assert canonicalize_brief_anchor(brief, "SSO", entity=False) == "sso"
    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize(
    "brief,alias",
    [
        (
            "Compare International Business Machines and Oracle. IBM must support SSO.",
            "IBM",
        ),
        (
            "Compare Amazon Web Services and Azure. AWS must support SSO.",
            "AWS",
        ),
        (
            "Compare Google Cloud Platform and Azure. GCP must support SSO.",
            "GCP",
        ),
    ],
)
def test_alias_outside_comparison_list_cannot_replace_complete_entity(
    brief: str, alias: str
) -> None:
    assert canonicalize_brief_anchor(brief, alias, entity=True) is None


@pytest.mark.parametrize(
    "brief,alias,canonical",
    [
        (
            "Compare Amazon Web Services. AWS must support SSO.",
            "AWS",
            "amazon web services",
        ),
        (
            "Compare International Business Machines. IBM must support SSO.",
            "IBM",
            "international business machines",
        ),
        (
            "Compare Google Cloud Platform. GCP must support SSO.",
            "GCP",
            "google cloud platform",
        ),
    ],
)
def test_single_vendor_initialism_resolves_to_complete_identity(
    brief: str, alias: str, canonical: str
) -> None:
    assert canonicalize_brief_anchor(brief, alias, entity=True) == canonical


def test_single_explicit_vendor_rejects_unrelated_entity() -> None:
    brief = "Compare Acme. Beta appears only in an internal note."

    assert canonicalize_brief_anchor(brief, "Beta", entity=True) is None


@pytest.mark.parametrize(
    "brief", ["Acme vs Beta for SSO.", "Acme versus Beta for SSO."]
)
def test_infix_comparison_preserves_both_vendors(brief: str) -> None:
    assert comparison_entity_hints(brief) == {"acme", "beta"}
    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(brief, "Beta", entity=True) == "beta"


@pytest.mark.parametrize(
    "scope",
    ["on", "based on", "across", "regarding", "in terms of"],
)
def test_comparison_criteria_are_not_part_of_vendor_identity(scope: str) -> None:
    brief = f"Compare Intercom and Zendesk {scope} pricing and SSO."

    assert comparison_entity_hints(brief) == {"intercom", "zendesk"}
    assert canonicalize_brief_anchor(brief, "Intercom", entity=True) == "intercom"
    assert canonicalize_brief_anchor(brief, "Zendesk", entity=True) == "zendesk"


def test_shortlist_scope_applies_to_every_vendor() -> None:
    brief = "Shortlist Acme, Beta, Gamma for SSO."

    assert comparison_entity_hints(brief) == {"acme", "beta", "gamma"}
    assert all(
        brief_anchor_association_valid(brief, entity, "SSO")
        for entity in ("Acme", "Beta", "Gamma")
    )


def test_chinese_requirement_tail_is_not_a_vendor() -> None:
    brief = "比较 Acme 和 Beta，需要 SSO。"

    assert comparison_entity_hints(brief) == {"acme", "beta"}
    assert canonicalize_brief_anchor(brief, "Acme", entity=True) == "acme"
    assert canonicalize_brief_anchor(brief, "Beta", entity=True) == "beta"
    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


def test_vendor_scoped_requirement_stays_with_its_vendor() -> None:
    brief = "Compare Acme and Beta. Beta must support SSO."

    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True
    assert brief_anchor_association_valid(brief, "Acme", "SSO") is False
    assert (
        brief_anchor_association_valid(
            "Compare Acme and Beta. Must support SSO.", "Acme", "SSO"
        )
        is True
    )
    scoped = "Compare Acme and Beta. For Acme, SSO is required."
    assert brief_anchor_association_valid(scoped, "Acme", "SSO") is True
    assert brief_anchor_association_valid(scoped, "Beta", "SSO") is False


@pytest.mark.parametrize(
    "brief",
    [
        "Compare Acme and Beta for our team, but Acme must support SSO.",
        "Compare Acme and Beta for procurement; Acme must support SSO.",
        "Compare Acme and Beta for our team but Acme must support SSO.",
    ],
)
def test_comparison_for_scope_stops_before_vendor_specific_clause(brief: str) -> None:
    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is False


@pytest.mark.parametrize(
    "scope",
    ["for", "on", "based on", "across", "regarding", "in terms of"],
)
def test_comparison_scope_criteria_apply_to_every_vendor(scope: str) -> None:
    brief = f"Compare Acme and Beta {scope} pricing, SSO, and SOC 2."

    for entity in ("Acme", "Beta"):
        for requirement in ("pricing", "SSO", "SOC 2"):
            assert brief_anchor_association_valid(brief, entity, requirement) is True


@pytest.mark.parametrize("separator", [":", "—"])
def test_colon_or_dash_criteria_are_not_parsed_as_vendors(separator: str) -> None:
    brief = f"Compare Acme and Beta {separator} price, SSO, SOC 2."

    assert comparison_entity_hints(brief) == {"acme", "beta"}
    assert canonicalize_brief_anchor(brief, "Beta", entity=True) == "beta"


def test_any_option_requirement_applies_to_each_compared_vendor() -> None:
    brief = "Compare Acme and Beta. Any option must support SSO."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize("subject", ["They", "These vendors", "Those options"])
def test_pronoun_shared_scope_applies_to_each_vendor(subject: str) -> None:
    brief = f"Compare Acme and Beta. {subject} must support SSO."

    assert brief_anchor_association_valid(brief, "Acme", "SSO") is True
    assert brief_anchor_association_valid(brief, "Beta", "SSO") is True


@pytest.mark.parametrize("subject", ["All", "Every", "Any"])
def test_bare_global_quantifier_applies_to_each_vendor(subject: str) -> None:
    brief = f"Compare Slack, Teams, and Zoom. {subject} must support SSO."

    for entity in ("Slack", "Teams", "Zoom"):
        assert brief_anchor_association_valid(brief, entity, "SSO") is True


@pytest.mark.parametrize(
    "brief",
    [
        "Vendors: Acme, Beta\nRequirements: SSO, SCIM",
        "Candidates: Acme, Beta\nCriteria: SSO, SCIM",
    ],
)
def test_structured_requirement_heading_is_not_a_vendor(brief: str) -> None:
    assert comparison_entity_hints(brief) == {"acme", "beta"}


@pytest.mark.parametrize("noun", ["Budget", "Price", "Cost"])
def test_financial_clause_after_vendor_list_is_not_a_vendor(noun: str) -> None:
    brief = f"Compare Acme and Beta; {noun} under $100/month."

    assert comparison_entity_hints(brief) == {"acme", "beta"}


@pytest.mark.parametrize("noun", ["budget", "price", "cost"])
def test_determiner_prefixed_financial_constraint_applies_globally(noun: str) -> None:
    brief = f"Compare Acme and Beta. The {noun} is $100/month."
    requirement = canonicalize_brief_anchor(brief, noun, entity=False)

    assert requirement == "$100/month"
    assert brief_anchor_association_valid(brief, "Acme", requirement) is True
    assert brief_anchor_association_valid(brief, "Beta", requirement) is True


@pytest.mark.parametrize(
    "brief,expected",
    [
        ("For Acme, compare pricing and security.", {"acme"}),
        (
            "Compare pricing and security for Acme and Beta.",
            {"acme", "beta"},
        ),
    ],
)
def test_criterion_led_comparison_extracts_vendors_not_criteria(
    brief: str, expected: set[str]
) -> None:
    assert comparison_entity_hints(brief) == expected


def test_negated_vendor_does_not_take_the_preceding_subjects_requirement() -> None:
    brief = "Compare Acme and Beta. Acme, but not Beta, supports SSO."
    requirement = canonicalize_brief_anchor(brief, "SSO", entity=False)

    assert requirement is not None
    assert brief_anchor_association_valid(brief, "Acme", requirement) is True
    assert brief_anchor_association_valid(brief, "Beta", requirement) is False


def test_requirement_clause_cannot_be_used_as_entity_identity() -> None:
    brief = "Compare Acme and Beta. SSO is required."

    assert canonicalize_brief_anchor(brief, "SSO", entity=True) is None


def test_source_record_requires_public_http_url() -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            title="Local file",
            url="file:///tmp/source",
            snippet="not public",
            engine="google_light",
            rank=1,
            observed_at=datetime.now(UTC),
        )


def test_source_and_citation_urls_preserve_provider_bytes() -> None:
    raw_url = "https://EXAMPLE.com/%7Evendor?Plan=Pro"
    source = SourceRecord(
        title="Pricing",
        url=raw_url,
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )
    assessment = ClaimAssessment(
        claim="The plan exists.",
        verdict=Verdict.SUPPORTED,
        confidence=0.8,
        explanation="Observed in current results.",
        recommendation="Review pricing details.",
        citation_urls=[raw_url],
    )

    assert source.url == raw_url
    assert assessment.citation_urls == [raw_url]


def test_citation_schema_keeps_uri_constraint_for_structured_output() -> None:
    schema = ClaimAssessment.model_json_schema()
    citation_schema = schema["properties"]["citation_urls"]["items"]

    assert citation_schema["format"] == "uri"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com\n@evil.com",
        "https://example.com\t@evil.com",
        "https://example.com/\x01path",
        " https://example.com/path",
    ],
)
def test_source_and_citation_urls_reject_controls_and_surrounding_space(
    url: str,
) -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            title="Unsafe",
            url=url,
            engine="google_light",
            rank=1,
            observed_at=datetime.now(UTC),
        )

    with pytest.raises(ValidationError):
        ClaimAssessment(
            claim="The plan exists.",
            verdict=Verdict.SUPPORTED,
            confidence=0.8,
            explanation="Observed in current results.",
            recommendation="Review pricing details.",
            citation_urls=[url],
        )


@pytest.mark.parametrize(
    "url", ["https://exa mple.com/path", "https://example.com:bad/path"]
)
def test_source_record_rejects_malformed_http_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            title="Malformed",
            url=url,
            engine="google_light",
            rank=1,
            observed_at=datetime.now(UTC),
        )

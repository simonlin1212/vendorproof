import hashlib
import re
import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlsplit

import tldextract
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    HttpUrl,
    TypeAdapter,
    WithJsonSchema,
    computed_field,
    field_validator,
)

_DOMAIN_EXTRACTOR = tldextract.TLDExtract(
    cache_dir=None,
    suffix_list_urls=(),
    fallback_to_snapshot=True,
    include_psl_private_domains=True,
)

HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
MAX_EXPLANATION_CHARS = 2_000
MAX_RECOMMENDATION_CHARS = 1_000
_SENTENCE_SEPARATOR = r"\.(?=\s|$)|[!?。！？]"
_ABBREVIATION_PERIOD = "\ue003"
_ABBREVIATION_SENTENCE_BREAK = "\ue004"


def split_brief_sentences(value: str, *, split_newlines: bool = False) -> list[str]:
    """Split prose without treating comparison/legal abbreviations as sentences."""

    def protect_dotted_initialism(match: re.Match[str]) -> str:
        initialism = match.group(0)
        following = re.match(r"\s+([A-Za-z][\w'’.-]*)", value[match.end() :])
        phrase = f"{initialism} {following.group(1)}" if following else initialism
        preceding = value[: match.start()]
        prior_phrase = normalize_requirement_anchor(
            phrase
        ) in normalize_requirement_anchor(preceding)
        latest_boundary = max(
            preceding.rfind(". "),
            preceding.rfind("! "),
            preceding.rfind("? "),
            preceding.rfind("。"),
            preceding.rfind("！"),
            preceding.rfind("？"),
        )
        clause_prefix = preceding[latest_boundary + 1 :]
        comparison_context = re.search(
            r"\b(?:compare|comparing|evaluate|evaluating|review|reviewing|"
            r"shortlist|between|versus|vs)\b|(?:比较|对比|评估|评价|审查)",
            clause_prefix,
            flags=re.IGNORECASE,
        )
        if prior_phrase or comparison_context:
            return initialism.replace(".", _ABBREVIATION_PERIOD)
        return initialism[:-1].replace(".", _ABBREVIATION_PERIOD) + "."

    protected = re.sub(
        r"(?m)^(\s*\d{1,3})\.(?=\s+\S)",
        rf"\1{_ABBREVIATION_PERIOD}",
        value,
    )
    protected = re.sub(
        r"(?<!\w)(?:[a-z]\.){2,}(?=\s+\w)",
        protect_dotted_initialism,
        protected,
        flags=re.IGNORECASE,
    )
    protected = re.sub(
        r"(?<!\w)vs\.(?=\s+\S)",
        f"vs{_ABBREVIATION_PERIOD}",
        protected,
        flags=re.IGNORECASE,
    )
    legal_suffix = r"inc|llc|ltd|plc|corp|co|pte|pty"
    continuation = r"and|or|with|versus|vs|against|to"
    protected = re.sub(
        rf"(?<!\w)({legal_suffix})\."
        rf"(?=\s+(?:(?:\([^)]{{1,200}}\)|\[[^]]{{1,200}}\])\s*)?"
        rf"(?:(?:{continuation}|{legal_suffix})\b|[,，&和与及或]))",
        lambda match: f"{match.group(1)}{_ABBREVIATION_PERIOD}",
        protected,
        flags=re.IGNORECASE,
    )
    protected = re.sub(
        rf"(?<!\w)((?i:{legal_suffix}))\."
        r"(?=\s+(?:(?i:currently|recently|now|today|historically|newly)\s+)*"
        r"(?i:supports?|offers?|has|includes?|provides?|requires?|needs?|"
        r"integrates?|costs?|prices?|operates?|changes?|changed|is|are|can|"
        r"pricing)\b)",
        lambda match: f"{match.group(1)}{_ABBREVIATION_PERIOD}",
        protected,
    )
    protected = re.sub(
        rf"(?<!\w)({legal_suffix})\.(?=\s|$)",
        lambda match: (
            f"{match.group(1)}{_ABBREVIATION_PERIOD}{_ABBREVIATION_SENTENCE_BREAK}"
        ),
        protected,
        flags=re.IGNORECASE,
    )
    separator = rf"{_ABBREVIATION_SENTENCE_BREAK}|{_SENTENCE_SEPARATOR}"
    if split_newlines:
        separator = rf"{separator}|\r?\n"
    return [
        sentence.replace(_ABBREVIATION_PERIOD, ".")
        for sentence in re.split(separator, protected)
    ]


def validate_public_url(value: str) -> str:
    raw = str(value)
    has_control = any(ord(character) < 32 or ord(character) == 127 for character in raw)
    if raw != raw.strip() or has_control:
        raise ValueError(
            "URL must not contain whitespace controls or surrounding space."
        )
    try:
        HTTP_URL_ADAPTER.validate_python(raw)
    except ValueError as exc:
        raise ValueError("URL must be a valid public HTTP or HTTPS URL.") from exc
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be a public HTTP or HTTPS URL.")
    return raw


PublicHttpUrl = Annotated[
    str,
    Field(min_length=8, max_length=2_000),
    AfterValidator(validate_public_url),
    WithJsonSchema(
        {
            "type": "string",
            "format": "uri",
            "minLength": 8,
            "maxLength": 2_000,
        }
    ),
]


class Verdict(StrEnum):
    SUPPORTED = "supported"
    CHANGED = "changed"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"


class ClaimFactCategory(StrEnum):
    PRICING = "pricing"
    USER_LIMITS = "user_limits"
    SHARED_INBOX = "shared_inbox"
    CHATBOT = "chatbot"
    KNOWLEDGE_BASE = "knowledge_base"
    INTEGRATION = "integration"
    SECURITY_CERTIFICATION = "security_certification"
    ENCRYPTION = "encryption"
    DATA_RESIDENCY = "data_residency"
    COMPLIANCE = "compliance"
    CONTRACT = "contract"
    RELIABILITY = "reliability"
    COMPANY_RISK = "company_risk"
    OTHER_CAPABILITY = "other_capability"


def normalize_requirement_anchor(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def strip_comparison_tail(value: str) -> str:
    """Remove requirement or scope prose that follows a vendor list."""
    tail_subject = (
        r"(?:all|any|both|each|every)\b|we\b|"
        r"(?:must|should|need(?:s|ed)?|require(?:s|d|ing)?|prefer(?:s|red)?)\b|"
        r"(?:requirements?|features?|must[- ]haves?|criteria|constraints?|"
        r"budget|price|cost)\b|"
        r"(?:必须|需要|应当|应该|要求|偏好|检查|验证)"
    )
    return re.split(
        rf"\s*(?:[;:；：–—]|[,，]\s*)\s*(?={tail_subject})",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]


def canonicalize_requirement_anchor(value: str) -> str:
    """Remove common directive wording while preserving the specific check."""
    anchor = normalize_requirement_anchor(value)
    anchor = re.sub(r"^[\s\-*•‣▪◦]+", "", anchor)
    anchor = re.sub(
        r"^(?:requirements?|features?|must[- ]haves?|criteria|constraints?)"
        r"\s*(?::|are|include(?:s)?)\s*",
        "",
        anchor,
        count=1,
    )
    anchor = re.sub(
        r"^(?:(?:must|should|need(?:s|ed)?|require(?:s|d)?|"
        r"prefer(?:s|red)?|flag|check|verify|review)\s+"
        r"(?:(?:to|that)\s+)?"
        r"(?:(?:current|latest|recent)\s+)?"
        r"(?:(?:have|support|include|offer|provide|use|be|"
        r"integrate(?:\s+with)?)\s+)?|"
        r"(?:budget|price|cost)\s*(?::|(?:must|should)?\s*be)\s*)",
        "",
        anchor,
        count=1,
    )
    anchor = re.sub(
        r"^(.+?)\s+(?:must|should|needs?\s+to|required\s+to)\s+be\s+"
        r"(?:supported|provided|offered|included|available|enabled|required)$",
        r"\1",
        anchor,
        count=1,
    )
    anchor = re.sub(
        r"^.*?\b(?:must|should|need(?:s|ed)?|require(?:s|d)?)\s+"
        r"(?:(?:to|that)\s+)?"
        r"(?:(?:have|support|include|offer|provide|use|be|"
        r"integrate(?:\s+with)?)\s+)?",
        "",
        anchor,
        count=1,
    )
    anchor = re.sub(
        r"^.*?(?:必须|需要|应当|应该|要求|偏好|检查|验证)"
        r"(?:支持|具备|包含|提供)?",
        "",
        anchor,
        count=1,
    )
    anchor = re.sub(r"\s+(?:is|are)\s+required$", "", anchor, count=1)
    return re.sub(r"^(?:a|an|the)\s+", "", anchor, count=1)


def canonicalize_entity_anchor(
    protected_brief: str, normalized_anchor: str, marker: str
) -> str | None:
    """Accept an exact entity, but reject a partial name in the comparison list."""
    all_sentences = [
        sentence
        for sentence in split_brief_sentences(protected_brief)
        if sentence.strip()
    ]
    sentences = [sentence for sentence in all_sentences if marker in sentence]
    comparison_cue = re.compile(
        r"\b(?:compare|comparing|evaluate|evaluating|assess|assessing|"
        r"analyse|analysing|analyze|analyzing|review|reviewing|between|"
        r"candidates?|vendors?|shortlist|options?|choices?|versus|vs)\b|"
        r"(?:比较|对比|评估|评价|审查|候选|选项)"
    )
    comparison_sentences = [
        sentence for sentence in all_sentences if comparison_cue.search(sentence)
    ]
    comparison_head = next(
        (sentence for sentence in comparison_sentences if marker in sentence),
        sentences[0],
    )
    comparison_head = re.sub(r"\bvs\.", "vs", comparison_head)
    comparison_head = strip_comparison_tail(comparison_head)
    comparison_head = re.split(
        r"\s+(?:based\s+on|in\s+terms\s+of|on|across|regarding)\s+",
        comparison_head,
        maxsplit=1,
    )[0]
    comparison_head = re.sub(
        rf"{marker}\s*(?:\(|\[|\{{)(?:https?://)?(?:www\.)?"
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
        r"(?:/[^\s)\]}]*)?(?:\)|\]|\})",
        marker,
        comparison_head,
    )
    if (
        re.search(
            rf"{marker}\s*,?\s+(?:inc|incorporated|llc|ltd|limited|corp|"
            r"corporation|company|co)\b",
            comparison_head,
        )
        or re.search(
            rf"{marker}\s+(?:&|and)\s+"
            r"(?!(?:must|should|need(?:s|ed)?|require(?:s|d|ing)?|"
            r"prefer(?:s|red)?|flag|check|verify|review)\b)"
            r"[\w.-]+(?:\s+[\w.-]+){0,3}\s+"
            r"(?:and|or|with|versus|vs|against)\b",
            comparison_head,
        )
        or re.search(
            rf"(?:{marker}\s+(?:&|and)\s+[^,]{{1,120}}|"
            rf"[^,]{{1,120}}\s+(?:&|and)\s+{marker})\s*,",
            comparison_head,
        )
    ):
        return None
    list_separator = r"and|or|versus|vs|with|to|against"
    atoms = re.split(
        rf"(?:\r?\n|[,;:，；：、]|\b(?:{list_separator})\b|[和与及或]|"
        r"\s+&\s+|\s+[/+]\s+)",
        comparison_head,
        flags=re.IGNORECASE,
    )
    exact = False
    partial = False
    for raw_atom in atoms:
        if marker not in raw_atom:
            continue
        atom = re.sub(r"^[\s\-*•‣▪◦]+", "", normalize_requirement_anchor(raw_atom))
        atom = re.sub(r"^\d{1,3}\.\s*", "", atom, count=1)
        atom = re.sub(
            r"^.*?\b(?:compare|comparing|evaluate|evaluating|assess|assessing|"
            r"analyse|analysing|analyze|analyzing|review|reviewing|"
            r"between|looking\s+at|considering|"
            r"(?:candidates?|vendors?)\s+(?:are|include(?:s)?)|"
            r"shortlist(?:\s+(?:is|are|includes?|consists?\s+of))?|"
            r"(?:options?|choices?)\s+(?:are|include(?:s)?))\s+",
            "",
            atom,
            count=1,
        )
        atom = re.sub(
            r"^(?:the\s+)?(?:(?:software|saas|support|customer[- ]support)\s+)*"
            r"(?:vendors?|suppliers?|options?|choices?|candidates?|products?|tools?|"
            r"platforms?)\s*:?\s+",
            "",
            atom,
            count=1,
        )
        atom = re.sub(r"^(?:比较|对比|评估|评价|审查)", "", atom, count=1)
        atom = re.sub(r"^(?:候选|选项)?(?:是|包括|包含)\s*", "", atom, count=1)
        atom = re.sub(
            r"^(?:our\s+vendor\s+is|we\s+use|need)\s+",
            "",
            atom,
            count=1,
        )
        atom = re.sub(r"^.*\bfrom\s+", "", atom, count=1)
        atom = atom.strip()
        atom = re.sub(
            rf"^{marker}\s*(?:\(|\[|\{{)(?:https?://)?(?:www\.)?"
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
            r"(?:/[^\s)\]}]*)?(?:\)|\]|\})(?=\s|$)",
            marker,
            atom,
            count=1,
        )
        atom = re.sub(rf"^{marker}\s*\([^)]{{1,40}}\)$", marker, atom, count=1)
        atom = re.sub(
            rf"^{marker}(?:['’]s\s+.*|\s+(?:(?:must|should)\s+"
            r"(?:support|offer|have|provide|integrate)|for|"
            r"supports?|offers?|has|costs?|can|provides?|requires?|needs?|"
            r"integrates?|pricing|today|currently)\b.*)$",
            marker,
            atom,
            count=1,
        )
        cleaned = atom.strip(" ()[]{}:;,-")
        if cleaned == marker:
            exact = True
        else:
            partial = True
    if exact:
        return normalized_anchor
    if partial:
        return None
    return normalized_anchor


def canonicalize_brief_anchor(brief: str, anchor: str, *, entity: bool) -> str | None:
    """Map an exact anchor to one deterministic brief atom."""
    normalized_anchor = normalize_requirement_anchor(anchor)
    if entity:
        annotated_entity = re.fullmatch(
            r"(.+?)\s*(?:\(|\[|\{)\s*(?:https?://)?(?:www\.)?"
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
            r"(?:/[^\s)\]}]*)?\s*(?:\)|\]|\})",
            normalized_anchor,
        )
        if annotated_entity:
            normalized_anchor = annotated_entity.group(1).strip()
    if not normalized_anchor:
        return None
    if entity:
        explicit_entities = {
            normalize_requirement_anchor(value)
            for value in comparison_entity_hints(brief, include_review=False)
        }
        explicit_entity_keys = {value.rstrip(".!?") for value in explicit_entities}
        normalized_anchor_key = normalized_anchor.rstrip(".!?")
        symbolic_pair_member = False
        if (
            len(explicit_entities) == 1
            and normalized_anchor_key not in explicit_entity_keys
        ):
            sole_entity = next(iter(explicit_entities))
            sole_entity_has_domain = (
                brief_domain_for_entity(brief, sole_entity) is not None
            )
            symbolic_pair_member = not sole_entity_has_domain and normalized_anchor in {
                member.strip() for member in sole_entity.split(" & ")
            }
            entity_words = re.findall(r"[a-z0-9]+", sole_entity)
            initialism = "".join(word[0] for word in entity_words)
            compact_anchor = re.sub(r"[^a-z0-9]", "", normalized_anchor)
            if len(initialism) >= 2 and compact_anchor == initialism:
                return sole_entity
        if (
            explicit_entities
            and normalized_anchor_key not in explicit_entity_keys
            and not symbolic_pair_member
        ):
            anchor_pattern = re.escape(normalized_anchor).replace(r"\ ", r"\s+")
            named_company_with_conjunction = (
                " and " in normalized_anchor or " & " in normalized_anchor
            ) and re.search(
                rf"(?<!\w){anchor_pattern}(?!\w)(?:\s+"
                r"(?:with|versus|vs|against|to)\b|,)",
                normalize_requirement_anchor(brief),
            )
            if not named_company_with_conjunction:
                return None
    protected_marker = "\ue000"
    normalized_brief = unicodedata.normalize("NFKC", brief).casefold()
    anchor_pattern = re.escape(normalized_anchor).replace(r"\ ", r"\s+")
    if not entity:
        if re.search(
            rf"(?<!\w)for\s+(?:(?:a|an|the)\s+)?{anchor_pattern}(?!\w)",
            normalized_brief,
        ):
            return normalized_anchor
        comparison_scope_brief = re.sub(
            r"(?<!\w)vs\.(?=\s+\S)", "vs", normalized_brief
        )
        if re.search(
            r"(?<!\w)(?:compare|comparing|evaluate|evaluating|assess|assessing|"
            r"analyse|analysing|analyze|analyzing|shortlist|shortlisting)(?!\w)"
            r"[^.!?\r\n]{0,500}\b(?:based\s+on|in\s+terms\s+of|on|"
            r"across|regarding)\b"
            rf"[^.!?\r\n]{{0,200}}(?<!\w){anchor_pattern}(?!\w)",
            comparison_scope_brief,
        ):
            return normalized_anchor
        if re.search(
            r"(?<!\w)(?:compare|comparing|evaluate|evaluating|assess|assessing|"
            r"analyse|analysing|analyze|analyzing|shortlist|shortlisting)(?!\w)"
            r"[^.!?\r\n]{0,500}(?<!\w)for(?!\w)"
            r"[^.!?\r\n]{0,200}(?<!\w)"
            r"(?:requiring|needing|that\s+(?:require|need)|must\s+"
            r"(?:support|have|include))(?!\w)"
            rf"[^.!?\r\n]{{0,200}}(?<!\w){anchor_pattern}(?!\w)",
            normalized_brief,
        ):
            return normalized_anchor
        labeled_values = list(
            re.finditer(
                r"(?<!\w)(budget|price|cost)(?!\w)\s*"
                r"(?::|：|(?:is|are)\b|(?:(?:must|should)\s+be\s+)?"
                r"(?:under|below|up\s+to|less\s+than|max(?:imum)?(?:\s+of)?)|"
                r"(?:must|should)\s+be)\s*"
                r"((?:[^.,，\r\n;!?。；！？]|[.,，](?=\d))+)",
                normalized_brief,
            )
        )

        def canonical_labeled_value(match: re.Match[str]) -> str:
            value = re.split(
                r"\s+(?:and|or|but|then)\s+(?="
                r"(?:(?:must|should|need(?:s)?|require(?:s)?|prefer(?:s)?|"
                r"flag|check|verify)\b|"
                r"(?:(?:we|they|the\s+team|our\s+team|the\s+solution|"
                r"the\s+vendor|the\s+vendors)\s+"
                r"(?:must|should|need(?:s)?|require(?:s)?|prefer(?:s)?))\b|"
                r"[^,;.!?]{1,80}\s+(?:is|are)\s+required\b))",
                match.group(2),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return canonicalize_requirement_anchor(value)

        if normalized_anchor in {match.group(1) for match in labeled_values}:
            matching_labels = [
                match for match in labeled_values if match.group(1) == normalized_anchor
            ]
            if len(matching_labels) != 1:
                return None
            canonical_value = canonical_labeled_value(matching_labels[0])
            return canonical_value if 2 <= len(canonical_value) <= 200 else None
        for value_match in labeled_values:
            canonical_value = canonical_labeled_value(value_match)
            is_numeric_value = any(
                character.isdigit() for character in normalized_anchor
            )
            anchor_in_value = re.search(
                rf"(?<!\w){anchor_pattern}(?!\w)", canonical_value
            )
            anchor_in_labeled_span = re.search(
                rf"(?<!\w){anchor_pattern}(?!\w)", value_match.group(0)
            )
            if (
                is_numeric_value
                and (anchor_in_value or anchor_in_labeled_span)
                and 2 <= len(canonical_value) <= 200
            ):
                return canonical_value
    protected_anchor = protected_marker
    if entity and normalized_anchor[-1:] in {".", "!", "?"}:
        protected_anchor += normalized_anchor[-1]
    protected_brief, match_count = re.subn(
        rf"(?<![a-z0-9]){anchor_pattern}"
        r"(?![a-z0-9]|\.[a-z]{2,63}(?:\W|$))",
        protected_anchor,
        normalized_brief,
    )
    if not match_count:
        return None
    if entity and normalized_anchor in explicit_entities:
        return normalized_anchor
    if entity and normalized_anchor_key in explicit_entity_keys:
        return normalized_anchor_key
    if entity and re.search(
        rf"{protected_marker}\s*(?:&|and)\s*{protected_marker}"
        r"(?=\s*(?:(?:with|versus|vs|against|to|and|or)\b|,|\.|$))",
        protected_brief,
        flags=re.IGNORECASE,
    ):
        return None
    if entity:
        return canonicalize_entity_anchor(
            protected_brief, normalized_anchor, protected_marker
        )
    conjunctions = (
        "as\\s+well\\s+as|and|or|but|while|whereas|yet|although|though|"
        "plus|however|then|versus|vs"
    )
    split_pattern = (
        rf"(?:[,:;，：；、]|\b(?:{conjunctions})\b|(?:和|与|及|或)|"
        r"\s+&\s+|\s*[/+]\s*)"
    )
    candidates: list[str] = []
    explicit_requirement_entities = sorted(
        comparison_entity_hints(brief), key=len, reverse=True
    )
    raw_atoms = (
        raw_atom
        for sentence in split_brief_sentences(protected_brief, split_newlines=True)
        for raw_atom in re.split(split_pattern, sentence, flags=re.IGNORECASE)
    )
    for raw_atom in raw_atoms:
        if protected_marker not in raw_atom:
            continue
        atom = normalize_requirement_anchor(raw_atom).replace(
            protected_marker, normalized_anchor
        )
        for explicit_entity in explicit_requirement_entities:
            entity_pattern = re.escape(explicit_entity).replace(r"\ ", r"\s+")
            atom = re.sub(
                rf"^(?:for\s+)?{entity_pattern}(?:['’]s)?\s+"
                r"(?:(?:must|should|needs?\s+to|required\s+to)\s+)?"
                r"(?:supports?|offers?|has|includes?|provides?|requires?|needs?|"
                r"integrates?|costs?|prices?)\s+",
                "",
                atom,
                count=1,
                flags=re.IGNORECASE,
            )
        canonical = canonicalize_requirement_anchor(atom)
        if len(canonical) >= 2:
            candidates.append(canonical)
    if normalized_anchor in candidates:
        return normalized_anchor
    unique_candidates = set(candidates)
    if len(unique_candidates) != 1:
        return None
    return unique_candidates.pop()


def query_mentions_entity(entity_anchor: str, query: str) -> bool:
    """Ensure the search query remains tied to the user-named entity."""
    normalized_entity = normalize_requirement_anchor(entity_anchor)
    normalized_query = normalize_requirement_anchor(query)
    if not normalized_entity:
        return False
    if any("\u3400" <= character <= "\u9fff" for character in normalized_entity):
        accepted_suffixes = (
            "\u5b98\u7f51",
            "\u5b98\u65b9",
            "\u6587\u6863",
            "\u5e2e\u52a9",
            "\u72b6\u6001",
            "\u5b9a\u4ef7",
            "\u4ef7\u683c",
            "\u5b89\u5168",
            "\u5408\u89c4",
            "\u670d\u52a1",
            "\u96c6\u6210",
            "\u77e5\u8bc6\u5e93",
            "\u5171\u4eab\u6536\u4ef6\u7bb1",
            "\u5fc5\u987b",
            "\u9700\u8981",
            "\u5e94\u5f53",
            "\u5e94\u8be5",
            "\u8981\u6c42",
            "\u652f\u6301",
            "\u63d0\u4f9b",
            "\u62e5\u6709",
        )
        start = 0
        while True:
            index = normalized_query.find(normalized_entity, start)
            if index < 0:
                return False
            before = normalized_query[index - 1] if index else ""
            tail = normalized_query[index + len(normalized_entity) :]
            before_ok = not before or not ("\u3400" <= before <= "\u9fff")
            after_ok = (
                not tail
                or not ("\u3400" <= tail[0] <= "\u9fff")
                or tail.startswith(accepted_suffixes)
            )
            if before_ok and after_ok:
                return True
            start = index + 1
    phrase_pattern = re.escape(normalized_entity).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<!\w){phrase_pattern}(?!\w)", normalized_query))


def text_mentions_requirement(requirement_anchor: str, text: str) -> bool:
    """Match a validated requirement phrase without applying entity identity rules."""
    requirement = normalize_requirement_anchor(requirement_anchor)
    normalized_text = normalize_requirement_anchor(text)
    if not requirement:
        return False
    if any("\u3400" <= character <= "\u9fff" for character in requirement):
        return requirement in normalized_text
    phrase_pattern = re.escape(requirement).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<!\w){phrase_pattern}(?!\w)", normalized_text))


def brief_domain_for_entity(brief: str, entity_anchor: str) -> str | None:
    """Return a domain explicitly written next to an entity in the user brief."""
    normalized_brief = unicodedata.normalize("NFKC", brief).casefold()
    entity = re.escape(normalize_requirement_anchor(entity_anchor)).replace(
        r"\ ", r"\s+"
    )
    match = re.search(
        rf"(?<![a-z0-9]){entity}(?![a-z0-9])\s*(?:\(|\[|\{{)?\s*"
        r"(?:https?://)?(?:www\.)?"
        r"((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})",
        normalized_brief,
    )
    return validate_entity_domain(match.group(1)) if match else None


def comparison_entity_hints(brief: str, *, include_review: bool = False) -> set[str]:
    """Extract conservative vendor-name hints from an explicit comparison clause."""
    source = unicodedata.normalize("NFKC", brief)
    normalized = unicodedata.normalize("NFKC", brief).casefold()
    comparison_verbs = (
        r"compare|comparing|evaluate|evaluating|assess|assessing|"
        r"analyse|analysing|analyze|analyzing|shortlist|between|versus|vs"
    )
    if include_review:
        comparison_verbs += r"|review|reviewing"
    cue = re.compile(
        rf"\b(?:{comparison_verbs})\b|"
        r"\b(?:candidates?|vendors?|suppliers?|shortlist|options?|choices?)\b"
        r"(?=\s*(?::|are\b|include(?:s)?\b))|"
        r"(?:\u6bd4\u8f83|\u5bf9\u6bd4|\u8bc4\u4f30|\u8bc4\u4ef7|\u5ba1\u67e5|"
        r"\u5019\u9009|\u9009\u9879)"
    )
    hints: set[str] = set()
    if not include_review:
        for sentence in split_brief_sentences(source):
            review = re.search(
                r"\breview(?:ing)?\s+(.+)", sentence, flags=re.IGNORECASE
            )
            if review is None:
                continue
            review_list = re.split(
                r"\s+for\s+", review.group(1), maxsplit=1, flags=re.IGNORECASE
            )[0]
            review_list = strip_comparison_tail(review_list)
            legal_comma_marker = "\ue002"
            review_list = re.sub(
                r",(?=\s*(?:inc|incorporated|llc|ltd|limited|corp|corporation|"
                r"company|co|plc)\.?\b)",
                legal_comma_marker,
                review_list,
                flags=re.IGNORECASE,
            )
            review_atoms = re.split(
                r"\s*(?:,|\b(?:and|or|versus|vs|against|with)\b|"
                r"[、，和与及或])\s*",
                review_list,
                flags=re.IGNORECASE,
            )
            candidates = []
            for atom in review_atoms:
                candidate = atom.replace(legal_comma_marker, ",").strip(
                    " ()[]{}:;,-*•‣▪◦"
                )
                candidate = re.sub(
                    r"\s*(?:\(|\[|\{)(?:https?://)?(?:www\.)?"
                    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                    r"[a-z]{2,63}(?:/[^\s)\]}]*)?(?:\)|\]|\})\s*$",
                    "",
                    candidate,
                    flags=re.IGNORECASE,
                ).strip()
                if candidate:
                    candidates.append(candidate)
            requirement_like = re.compile(
                r"\b(?:current|latest|recent|pricing|price|cost|budget|support|"
                r"inbox|chatbot|knowledge|sso|scim|security|compliance|"
                r"integration|outage|contract|billing|feature|capability|"
                r"residency|encryption|reliability)\b",
                flags=re.IGNORECASE,
            )
            if len(candidates) < 2 or any(
                requirement_like.search(candidate) for candidate in candidates
            ):
                continue
            hints.update(normalize_requirement_anchor(value) for value in candidates)
    sentences = split_brief_sentences(normalized)
    for sentence_index, sentence in enumerate(sentences):
        match = cue.search(sentence)
        if match is None:
            continue
        matched_cue = match.group(0).strip()
        if re.fullmatch(r"options?|choices?", matched_cue):
            prior_sentence = sentences[sentence_index - 1] if sentence_index else ""
            vendor_list_context = re.search(
                r"\b(?:compare|comparing|evaluate|evaluating)\b"
                r"[^.!?]{0,160}\b(?:platforms?|vendors?|tools?|products?|"
                r"solutions?)\b",
                prior_sentence,
            ) or re.search(
                r"\b(?:vendor|supplier|product|tool|platform)\s+$",
                sentence[: match.start()],
            )
            if vendor_list_context is None:
                continue
        infix_comparison = re.fullmatch(r"versus|vs", matched_cue)
        comparison = (sentence if infix_comparison else sentence[match.end() :]).strip(
            " :-\u2013\u2014"
        )
        comparison = re.sub(
            r"^(?:is|are|include(?:s)?|consists?\s+of|:|\uff1a|"
            r"\u662f|\u5305\u62ec|\u5305\u542b)\s*",
            "",
            comparison,
            count=1,
        )
        comparison = re.sub(r"\bvs\.", "vs", comparison)
        criterion_led = re.match(
            r"^(?:the\s+)?(?:price|pricing|cost|budget|sso|scim|soc\s*2|"
            r"support|inbox|chatbot|knowledge|security|compliance|integration|"
            r"outage|contract|billing|feature|capability|residency|encryption|"
            r"reliability)\b",
            comparison,
        )
        if criterion_led:
            leading_for = re.search(
                r"^\s*for\s+(.+?)\s*[,;:]\s*$", sentence[: match.start()]
            )
            trailing_for = re.search(r"\s+for\s+(.+)$", comparison)
            if leading_for:
                comparison = leading_for.group(1)
            elif trailing_for:
                comparison = trailing_for.group(1)
            else:
                continue
        comparison = re.split(
            r"\r?\n\s*(?:requirements?|features?|must[- ]haves?|criteria|"
            r"constraints?)\s*:",
            comparison,
            maxsplit=1,
        )[0]
        criterion_delimiter = re.search(r"\s*[:\uff1a–—]\s*", comparison)
        if criterion_delimiter:
            suffix = comparison[criterion_delimiter.end() :]
            prefix = comparison[: criterion_delimiter.start()]
            criterion_like = re.search(
                r"\b(?:price|pricing|cost|budget|sso|scim|soc\s*2|support|"
                r"inbox|chatbot|knowledge|security|compliance|integration|"
                r"outage|contract|billing|feature|capability|residency|"
                r"encryption|reliability)\b",
                suffix,
            )
            if criterion_like and re.search(
                r"(?:,|\b(?:and|or|versus|vs|against|with|to)\b)", prefix
            ):
                comparison = prefix
        comparison = strip_comparison_tail(comparison)
        scope_match = re.search(
            r"\s+(?:for|based\s+on|in\s+terms\s+of|on|across|regarding)\s+",
            comparison,
        )
        if scope_match:
            comparison = comparison[: scope_match.start()]
        bullet_items = re.findall(
            r"(?:^|\n)\s*(?:[-*\u2022\u2023\u25aa\u25e6]|"
            r"\(?\d{1,3}[.)])\s+([^\n]+)",
            comparison,
        )
        if len(bullet_items) >= 2:
            for item in bullet_items:
                candidate = re.sub(
                    r"\s*(?:\(|\[|\{)(?:https?://)?(?:www\.)?"
                    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                    r"[a-z]{2,63}(?:/[^\s)\]}]*)?(?:\)|\]|\})\s*$",
                    "",
                    item.strip(),
                ).strip(" ()[]{}:;,-*\u2022\u2023\u25aa\u25e6")
                if candidate and len(candidate) <= 120:
                    hints.add(candidate)
            continue
        legal_comma_marker = "\ue002"
        comparison = re.sub(
            r",(?=\s*(?:inc|incorporated|llc|ltd|limited|corp|corporation|"
            r"company|co|plc)\.?\b)",
            legal_comma_marker,
            comparison,
        )
        conjoined_word_marker = "\ue006"
        conjoined_symbol_marker = "\ue007"
        word_conjunctions: list[re.Match[str]] = []
        symbolic_conjunctions: list[re.Match[str]] = []
        comma_delimiters = len(re.findall(r"[,，]", comparison))
        pair_separator = re.search(
            r"\s+(?:versus|vs|against|with|to)\s+", comparison
        )
        if pair_separator and not re.search(r"[,;；，]", comparison):
            left = comparison[: pair_separator.start()]
            separator = comparison[pair_separator.start() : pair_separator.end()]
            right = comparison[pair_separator.end() :]
            if len(re.findall(r"\s+and\s+", left)) == 1:
                left = re.sub(r"\s+and\s+", conjoined_word_marker, left)
            if len(re.findall(r"\s+and\s+", right)) == 1:
                right = re.sub(r"\s+and\s+", conjoined_word_marker, right)
            if len(re.findall(r"\s+&\s+", left)) == 1:
                left = re.sub(r"\s+&\s+", conjoined_symbol_marker, left)
            if len(re.findall(r"\s+&\s+", right)) == 1:
                right = re.sub(r"\s+&\s+", conjoined_symbol_marker, right)
            comparison = left + separator + right
        elif comma_delimiters >= 2:
            symbolic_conjunctions = list(re.finditer(r"\s+&\s+", comparison))
            if symbolic_conjunctions:
                comparison = re.sub(
                    r"\s+&\s+", conjoined_symbol_marker, comparison
                )
        elif not re.search(r"[,;；，]", comparison):
            word_conjunctions = list(re.finditer(r"\s+and\s+", comparison))
            symbolic_conjunctions = list(re.finditer(r"\s+&\s+", comparison))
            if len(word_conjunctions) == 1 and symbolic_conjunctions:
                comparison = re.sub(
                    r"\s+&\s+", conjoined_symbol_marker, comparison
                )
            elif len(word_conjunctions) == 2:
                repeated_name = re.match(
                    r"^\s*([^,;]+?)\s+and\s+\1\s+and\s+",
                    comparison,
                    flags=re.IGNORECASE,
                )
                if repeated_name:
                    first = word_conjunctions[0]
                    comparison = (
                        comparison[: first.start()]
                        + conjoined_word_marker
                        + comparison[first.end() :]
                    )
                else:
                    first, second = word_conjunctions
                    middle = comparison[first.end() : second.start()].strip()
                    organization_tail = {
                        "associates",
                        "group",
                        "holdings",
                        "industries",
                        "markets",
                        "partners",
                        "services",
                        "solutions",
                        "systems",
                        "technologies",
                    }
                    if middle.casefold().rstrip(".") in organization_tail:
                        comparison = (
                            comparison[: first.start()]
                            + conjoined_word_marker
                            + comparison[first.end() :]
                        )
            elif len(symbolic_conjunctions) == 2:
                first = symbolic_conjunctions[0]
                comparison = (
                    comparison[: first.start()]
                    + conjoined_symbol_marker
                    + comparison[first.end() :]
                )
        symbolic_separator = r"\s+[+/]\s+"
        if "," in comparison or len(symbolic_conjunctions) == 2:
            symbolic_separator += r"|\s+&\s+"
        atoms = re.split(
            rf"\s*(?:\r?\n|[,;；]|\b(?:and|or|versus|vs|against|to|with)\b|"
            rf"[\u3001\uff0c\u548c\u4e0e\u53ca\u6216]|{symbolic_separator})\s*",
            comparison,
        )
        for atom in atoms:
            atom = (
                atom.replace(legal_comma_marker, ",")
                .replace(conjoined_word_marker, " and ")
                .replace(conjoined_symbol_marker, " & ")
            )
            candidate = re.sub(
                r"\s*(?:\(|\[|\{)(?:https?://)?(?:www\.)?"
                r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
                r"(?:/[^\s)\]}]*)?(?:\)|\]|\})\s*$",
                "",
                atom.strip(),
            ).strip(" ()[]{}:;,-*•‣▪◦")
            candidate = re.sub(
                r"^\(?\d{1,3}[.)]\s*", "", candidate, count=1
            )
            candidate = re.sub(
                r"^(?:the\s+)?"
                r"(?:(?:software|saas|support|customer[- ]support)\s+)*"
                r"(?:vendors?|suppliers?|options?|choices?|candidates?|products?|tools?|"
                r"platforms?)\s*:?\s+",
                "",
                candidate,
            )
            candidate = re.sub(r"\s*\([^()]{1,40}\)?$", "", candidate).strip()
            if candidate and len(candidate) <= 120:
                hints.add(candidate)
    return hints


def brief_anchor_association_valid(
    brief: str, entity_anchor: str, requirement_anchor: str
) -> bool:
    """Require vendor-scoped requirements to remain attached to that vendor."""
    normalized_brief = unicodedata.normalize("NFKC", brief).casefold()
    requirement = normalize_requirement_anchor(requirement_anchor)
    requirement_pattern = re.escape(requirement).replace(r"\ ", r"\s+")
    sentences = split_brief_sentences(normalized_brief, split_newlines=True)
    global_subject = (
        r"(?:(?:our|the)\s+(?:team|company|organization|solutions?|products?|"
        r"tools?|platforms?|software|vendors?|options?)|we|they|"
        r"(?:these|those)\s+(?:vendors?|options?|candidates?|products?|"
        r"solutions?|tools?|platforms?)|"
        r"(?:all|every|each|both|any)\s+(?:vendors?|options?|candidates?|products?|"
        r"solutions?|tools?|platforms?)|all|every|each|both|any)"
    )
    global_directive = re.compile(
        rf"^(?:(?:the\s+)?(?:budget|price|cost)\b|"
        rf"(?:{global_subject}\s+)?"
        r"(?:must|should|need|needs|require|requires|required|prefer|flag|"
        r"check|verify|review|budget|price|cost|security)\b|"
        r"(?:\u5fc5\u987b|\u9700\u8981|\u5e94\u5f53|\u5e94\u8be5|\u8981\u6c42|"
        r"\u504f\u597d|\u68c0\u67e5|\u9a8c\u8bc1)|"
        r"(?:requirements?|features?|must[- ]haves?|criteria|constraints?)"
        r"(?:\s+(?:are|include(?:s)?)|\s*:)\s*)"
    )
    explicit_global_directive = re.compile(
        rf"^(?:{global_subject}\s+"
        r"(?:must|should|need|needs|require|requires|required|prefer|flag|"
        r"check|verify|review)\b|"
        r"(?:requirements?|features?|must[- ]haves?|criteria|constraints?)"
        r"(?:\s+(?:are|include(?:s)?)|\s*:)\s*)"
    )
    comparison_entities = comparison_entity_hints(brief)
    normalized_entity = normalize_requirement_anchor(entity_anchor)
    entity_pattern = re.escape(normalized_entity).replace(r"\ ", r"\s+")
    entity_marker = "\ue001"
    scoped_entity_patterns = [
        re.escape(normalize_requirement_anchor(entity)).replace(r"\ ", r"\s+")
        for entity in sorted(comparison_entities, key=len, reverse=True)
    ]
    scoped_entity_pattern = "|".join(
        [re.escape(entity_marker), *scoped_entity_patterns]
    )
    scoped_conjunction = (
        r"\b(?:and|or|but|while|whereas|yet|although|though|plus|however|then|"
        r"as\s+well\s+as)\b(?=\s+(?:(?:"
        + scoped_entity_pattern
        + r")(?=\s|$|['’:(])|[^,;.!?]{1,80}?\s+"
        r"(?:must|should|needs?|requires?|has|supports?|offers?|provides?|"
        r"costs?|prices?|budgets?|(?:is|are)\s+(?:required|supported|provided|"
        r"offered|included|available|enabled))\b))"
    )
    found_requirement = False
    for sentence in sentences:
        requirement_is_cjk = any(
            "\u3400" <= character <= "\u9fff" for character in requirement
        )
        if not (
            requirement in sentence
            if requirement_is_cjk
            else re.search(rf"(?<!\w){requirement_pattern}(?!\w)", sentence)
        ):
            continue
        comparison_cue_present = re.search(
            r"\b(?:compare|comparing|evaluate|evaluating|review|reviewing|"
            r"shortlist|between)\b|(?:\u6bd4\u8f83|\u5bf9\u6bd4|\u8bc4\u4f30)",
            sentence,
        )
        scope = re.search(
            r"\b(?:for|on|across|regarding|based\s+on|in\s+terms\s+of)\b",
            sentence,
        )
        scoped_entity_union = "|".join(scoped_entity_patterns)
        vendor_specific_tail = (
            re.search(
                rf"(?:[,;\uff0c\uff1b]|\b(?:but|while|whereas|yet|although|"
                rf"though|however|then)\b)\s*(?:{scoped_entity_union})"
                r"(?:['\u2019]s)?\s+(?:must|should|needs?|requires?|has|"
                r"supports?|offers?|provides?)\b",
                sentence[scope.end() :] if scope else "",
            )
            if scoped_entity_union
            else None
        )
        if (
            comparison_cue_present
            and scope
            and re.search(
                rf"(?<!\w){requirement_pattern}(?!\w)", sentence[scope.end() :]
            )
            and not vendor_specific_tail
            and any(
                normalize_requirement_anchor(entity)
                == normalize_requirement_anchor(entity_anchor)
                for entity in comparison_entities
            )
        ):
            return True
        directive_matches = list(
            re.finditer(
                r"\b(?:(?:must|should)(?:\s+be\s+able\s+to)?\s+"
                r"(?:have|support|offer|provide)|"
                r"needs?(?:\s+to\s+(?:have|support|offer|provide))?|"
                r"requires?(?:\s+to\s+(?:have|support|offer|provide))?|"
                r"must|should|has|supports?|offers?|provides?)\b",
                sentence,
            )
        )
        if len(directive_matches) == 1:
            scope_prefix = sentence[: directive_matches[0].start()]
            if re.search(r"\bfor\b", scope_prefix):
                scope_prefix = re.split(
                    r"[,;\uff0c\uff1b]|\b(?:but|while|whereas|yet|although|"
                    r"though|however|then)\b",
                    scope_prefix,
                )[-1]
            prefix_entities = {
                entity
                for entity in comparison_entities
                if query_mentions_entity(entity, scope_prefix)
            }
            maximal_prefix_entities = {
                entity
                for entity in prefix_entities
                if not any(
                    entity != other and query_mentions_entity(entity, other)
                    for other in prefix_entities
                )
            }
            if (
                len(maximal_prefix_entities) >= 2
                and re.search(r"\b(?:and|or)\b", scope_prefix)
                and any(
                    normalize_requirement_anchor(entity)
                    == normalize_requirement_anchor(entity_anchor)
                    for entity in maximal_prefix_entities
                )
            ):
                return True
        for_scope = re.match(r"^\s*for\s+([^,\uff0c]{1,120})[,\uff0c]", sentence)
        if for_scope:
            found_requirement = True
            if query_mentions_entity(entity_anchor, for_scope.group(1)):
                return True
            continue
        protected_sentence = re.sub(
            rf"(?<!\w){entity_pattern}(?!\w)", entity_marker, sentence
        )
        requirement_marker = "\ue005"
        if "," in requirement or "，" in requirement:
            if requirement_is_cjk:
                protected_sentence = protected_sentence.replace(
                    requirement, requirement_marker
                )
            else:
                protected_sentence = re.sub(
                    rf"(?<!\w){requirement_pattern}(?!\w)",
                    requirement_marker,
                    protected_sentence,
                )
        active_entities: set[str] = set()
        for raw_clause in re.split(
            rf"(?:[,;\uff0c\uff1b]|\s+/\s+|{scoped_conjunction})",
            protected_sentence,
            flags=re.IGNORECASE,
        ):
            clause = raw_clause.replace(entity_marker, normalized_entity).replace(
                requirement_marker, requirement
            )
            stripped = clause.strip()
            scoped_entities = {
                entity
                for entity in comparison_entities
                if query_mentions_entity(entity, stripped)
            }
            maximal_scoped_entities = {
                entity
                for entity in scoped_entities
                if not any(
                    entity != other and query_mentions_entity(entity, other)
                    for other in scoped_entities
                )
            }
            negated_scope = re.match(
                r"^(?:(?:but\s+)?not|unlike|except|rather\s+than|"
                r"as\s+opposed\s+to)\b",
                stripped,
            )
            if maximal_scoped_entities and not negated_scope:
                active_entities = maximal_scoped_entities
            if not (
                requirement in clause
                if requirement_is_cjk
                else re.search(rf"(?<!\w){requirement_pattern}(?!\w)", clause)
            ):
                continue
            found_requirement = True
            candidate_named = query_mentions_entity(entity_anchor, stripped)
            shadowed_by_longer_entity = any(
                normalize_requirement_anchor(entity)
                != normalize_requirement_anchor(entity_anchor)
                and query_mentions_entity(entity_anchor, entity)
                for entity in scoped_entities
            )
            if candidate_named and not shadowed_by_longer_entity:
                return True
            if scoped_entities:
                continue
            global_clause = re.sub(
                r"^(?:and|or|but|while|whereas|yet|although|though|plus|"
                r"however|then|as\s+well\s+as)\s+",
                "",
                stripped,
                count=1,
            )
            global_clause = re.sub(r"^[\s\-*•‣▪◦]+", "", global_clause)
            if explicit_global_directive.search(global_clause):
                return True
            if active_entities:
                if any(
                    normalize_requirement_anchor(entity) == normalized_entity
                    for entity in active_entities
                ):
                    return True
                continue
            if global_directive.search(global_clause) or re.match(
                rf"^(?:(?:a|an|the)\s+)?{requirement_pattern}(?!\w)",
                global_clause,
            ):
                return True
    return not found_requirement


def validate_entity_domain(value: str) -> str:
    domain = value.strip().casefold().rstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if not re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain
    ):
        raise ValueError("entity_domain must be a valid official domain name.")
    extracted = _DOMAIN_EXTRACTOR(domain)
    if not extracted.domain or not extracted.suffix:
        raise ValueError("entity_domain must include a registrable domain name.")
    if extracted.subdomain:
        raise ValueError("entity_domain must be the official apex domain name.")
    return domain


class ClaimCandidate(BaseModel):
    entity_anchor: str = Field(min_length=1, max_length=120)
    entity_domain: str = Field(min_length=4, max_length=253)
    requirement_anchor: str = Field(min_length=2, max_length=200)
    fact_category: ClaimFactCategory
    text: str = Field(min_length=1, max_length=500)
    query: str = Field(min_length=3, max_length=300)
    why_check: str = Field(default="Time-sensitive external claim.", max_length=500)
    priority: int = Field(default=3, ge=1, le=5)
    domain_from_brief: bool = Field(default=False, exclude=True)

    @field_validator("entity_domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return validate_entity_domain(value)

    @field_validator(
        "entity_anchor", "requirement_anchor", "text", "query", "why_check"
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("text fields must contain non-whitespace characters.")
        return normalized

    @computed_field
    @property
    def comparison_key(self) -> str:
        entity_anchor = normalize_requirement_anchor(self.entity_anchor).removesuffix(
            "."
        )
        anchor = canonicalize_requirement_anchor(self.requirement_anchor).rstrip(".!?")
        entity_digest = hashlib.sha256(entity_anchor.encode()).hexdigest()[:16]
        anchor_digest = hashlib.sha256(anchor.encode()).hexdigest()[:16]
        return f"v5_entity_{entity_digest}_{anchor_digest}"


def reject_ambiguous_entity_domains(
    candidates: list[ClaimCandidate],
) -> tuple[list[ClaimCandidate], int]:
    """Remove claims whose displayed entity maps to multiple official domains."""
    domains_by_entity: dict[str, set[str]] = {}
    for candidate in candidates:
        entity = normalize_requirement_anchor(candidate.entity_anchor)
        domains_by_entity.setdefault(entity, set()).add(candidate.entity_domain)
    ambiguous = {
        entity for entity, domains in domains_by_entity.items() if len(domains) > 1
    }
    if not ambiguous:
        return candidates, 0
    filtered = [
        candidate
        for candidate in candidates
        if normalize_requirement_anchor(candidate.entity_anchor) not in ambiguous
    ]
    return filtered, len(candidates) - len(filtered)


class SourceRecord(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    url: PublicHttpUrl
    snippet: str = Field(default="", max_length=2_000)
    source: str = Field(default="", max_length=200)
    published_at: str | None = Field(default=None, max_length=100)
    engine: Literal["google_light", "google_news"]
    rank: int = Field(ge=1, le=100)
    observed_at: datetime
    search_id: str | None = Field(default=None, max_length=100)


class SearchOutcome(BaseModel):
    sources: list[SourceRecord] = Field(default_factory=list, max_length=20)
    failed_engines: list[Literal["google_light", "google_news"]] = Field(
        default_factory=list, max_length=2
    )
    entity_domain_verified: bool = False


class ClaimBatch(BaseModel):
    claims: list[ClaimCandidate] = Field(default_factory=list, max_length=8)


class ClaimAssessment(BaseModel):
    claim: str = Field(min_length=1, max_length=500)
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1, max_length=MAX_EXPLANATION_CHARS)
    recommendation: str = Field(min_length=1, max_length=MAX_RECOMMENDATION_CHARS)
    citation_urls: list[PublicHttpUrl] = Field(default_factory=list, max_length=10)


class ClaimResult(BaseModel):
    candidate: ClaimCandidate
    sources: list[SourceRecord] = Field(default_factory=list, max_length=20)
    assessment: ClaimAssessment
    search_error: str | None = None
    entity_domain_verified: bool = False


class SnapshotReceipt(BaseModel):
    snapshot_id: str = Field(min_length=1, max_length=100)
    previous_snapshot_id: str | None = Field(default=None, max_length=100)
    changed_claims: int = Field(default=0, ge=0, le=100)


class AuditReport(BaseModel):
    comparison_schema: Literal["v5"] = "v5"
    generated_at: datetime
    overall_action: Literal["publish", "review", "hold"]
    claims: list[ClaimResult]
    extraction_warning: str | None = Field(default=None, max_length=500)
    snapshot: SnapshotReceipt | None = None
    persistence_error: str | None = None

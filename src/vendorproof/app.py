from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
from flask import Flask, render_template, request

from vendorproof.providers import (
    GeminiClaimExtractor,
    GeminiEvidenceJudge,
    SerpApiSearchGateway,
    XanoSnapshotStore,
    create_gemini_client,
)
from vendorproof.service import AuditService, InputError

DEFAULT_MODEL = "gemini-3.5-flash"
SAMPLE_BRIEF = """Compare Intercom, Zendesk, and Crisp for a five-person SaaS team.
Budget: US$100 per month. Must have a shared inbox, chatbot, knowledge base, and
Slack integration. Prefer month-to-month billing. Flag recent outages, pricing
changes, or major service issues."""


def create_app(
    service_factory: Callable[[], AuditService] | None = None,
) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=20_000)
    factory = service_factory or _service_from_environment

    @app.get("/")
    def index() -> str:
        return render_template(
            "index.html",
            sample_brief=SAMPLE_BRIEF,
            report=None,
            brief="",
            error=None,
            access_required=bool(os.getenv("REVIEWER_ACCESS_CODE")),
        )

    @app.post("/analyze")
    def analyze() -> tuple[str, int] | str:
        brief = request.form.get("brief", "")
        access_code = request.form.get("access_code", "")
        required_code = os.getenv("REVIEWER_ACCESS_CODE", "")
        if required_code and access_code != required_code:
            return _render_error(
                "The reviewer access code is missing or incorrect.", brief, 403
            )
        try:
            report = factory().audit(brief)
        except InputError as exc:
            return _render_error(str(exc), brief, 400)
        except Exception:
            app.logger.exception("VendorProof analysis failed")
            return _render_error(
                "Live research is temporarily unavailable. Please retry in a moment.",
                brief,
                503,
            )
        return render_template(
            "index.html",
            sample_brief=SAMPLE_BRIEF,
            report=report,
            brief=brief,
            error=None,
            access_required=bool(required_code),
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "vendorproof"}

    def _render_error(message: str, brief: str, status: int) -> tuple[str, int]:
        return (
            render_template(
                "index.html",
                sample_brief=SAMPLE_BRIEF,
                report=None,
                brief=brief,
                error=message,
                access_required=bool(os.getenv("REVIEWER_ACCESS_CODE")),
            ),
            status,
        )

    return app


def _service_from_environment() -> AuditService:
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if not serpapi_key:
        raise RuntimeError("SERPAPI_API_KEY is not configured.")
    client = create_gemini_client()
    model = os.getenv("VENDORPROOF_MODEL", DEFAULT_MODEL)
    xano_endpoint = os.getenv("XANO_SNAPSHOT_ENDPOINT")
    store = (
        XanoSnapshotStore(
            xano_endpoint,
            api_token=os.getenv("XANO_API_TOKEN"),
        )
        if xano_endpoint
        else None
    )
    return AuditService(
        extractor=GeminiClaimExtractor(client, model),
        searcher=SerpApiSearchGateway(api_key=serpapi_key),
        judge=GeminiEvidenceJudge(client, model),
        store=store,
    )

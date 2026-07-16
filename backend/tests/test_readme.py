import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
DEPLOY_LINK = re.compile(
    r"\[!\[Deploy (?P<label>EquityLens) with Vercel\]"
    r"\(https://vercel.com/button\)\]"
    r"\((?P<url>https://vercel.com/new/clone\?[^)]+)\)"
)
LOCAL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")

EXPECTED_ENV = {
    "DATABASE_URL",
    "SECRET_KEY_ACCESS_API",
    "GOOGLE_CLIENT_ID",
    "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
    "OPENAI_API_KEY",
    "OPENAI_ORGANIZATION",
    "OPENAI_BASE_URL",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_STRUCTURED_OUTPUT_METHOD",
    "TAVILY_API_KEY",
    "CHAT_WEB_SEARCH_PROVIDER",
    "CHAT_TAVILY_SEARCH_DEPTH",
    "CHAT_TAVILY_MAX_RESULTS",
    "FIRST_SUPERUSER",
    "FIRST_SUPERUSER_PASSWORD",
    "BLOB_READ_WRITE_TOKEN",
    "SEC_USER_AGENT",
    "GUEST_SIGNING_SECRET",
    "QUOTA_HASH_SECRET",
    "INTERNAL_JOB_SECRET",
    "DEPLOYMENT_TARGET",
    "OBJECT_STORAGE_PROVIDER",
    "JOB_BACKEND",
    "DOCUMENT_PARSER",
    "COOKIE_SECURE",
    "MARKET_DATA_PROVIDER",
    "RESEARCH_MODEL",
    "SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE",
}


def readme_text() -> str:
    return README.read_text()


def deploy_parameters() -> dict[str, dict[str, str]]:
    links = {}
    for match in DEPLOY_LINK.finditer(readme_text()):
        query = parse_qs(urlparse(match.group("url")).query)
        links[match.group("label")] = {
            key: values[0] for key, values in query.items()
        }
    return links


def test_readme_identifies_the_product_and_delivery_status() -> None:
    content = readme_text()

    assert content.startswith('<div align="center">\n\n# EquityLens')
    assert "Phase 2 Beta" in content
    assert "US equity research" in content


def test_readme_credits_the_upstream_foundation() -> None:
    content = readme_text()

    assert "## Acknowledgements" in content
    assert "https://github.com/mazzasaverio/fastapi-langchain-rag" in content


def test_readme_local_links_resolve() -> None:
    missing = []
    for target in LOCAL_LINK.findall(readme_text()):
        path = target.split("#", maxsplit=1)[0]
        if path and not (ROOT / path).exists():
            missing.append(target)

    assert missing == []


def test_vercel_button_targets_the_services_project() -> None:
    deploys = deploy_parameters()

    assert set(deploys) == {"EquityLens"}
    actual = deploys["EquityLens"]
    assert actual["repository-url"] == "https://github.com/Linon419/equitylens"
    assert "root-directory" not in actual
    assert actual["project-name"] == "equitylens"
    assert set(actual["env"].split(",")) == EXPECTED_ENV
    assert actual["envLink"].endswith("deploy/vercel/README.md")


def test_services_button_defaults_only_public_profile_values() -> None:
    defaults = json.loads(deploy_parameters()["EquityLens"]["envDefaults"])

    assert defaults == {
        "DEPLOYMENT_TARGET": "vercel",
        "OBJECT_STORAGE_PROVIDER": "vercel_blob",
        "JOB_BACKEND": "vercel_workflow",
        "DOCUMENT_PARSER": "managed",
        "COOKIE_SECURE": "true",
        "MARKET_DATA_PROVIDER": "yahoo",
        "LLM_STRUCTURED_OUTPUT_METHOD": "json_schema",
        "CHAT_WEB_SEARCH_PROVIDER": "tavily",
        "CHAT_TAVILY_SEARCH_DEPTH": "basic",
        "CHAT_TAVILY_MAX_RESULTS": "5",
        "RESEARCH_MODEL": "gpt-5.6",
    }


def test_supporting_docs_describe_the_services_project() -> None:
    vercel = (ROOT / "deploy" / "vercel" / "README.md").read_text()
    frontend = (ROOT / "frontend" / "README.md").read_text()

    assert "one Vercel Project" in vercel
    assert "Vercel Services" in vercel
    assert "Service Binding" in vercel
    assert "# EquityLens Web" in frontend
    assert "../deploy/vercel/README.md" in frontend


def test_readme_links_graph_design_plan_and_documents_guest_quota() -> None:
    content = readme_text()

    assert (
        "docs/superpowers/specs/2026-07-14-agentic-supply-chain-graph-design.md"
        in content
    )
    assert (
        "docs/superpowers/plans/2026-07-14-agentic-supply-chain-graph.md"
        in content
    )
    assert "two accepted graph jobs per UTC day" in content


def test_readme_documents_the_research_chat_release_surface() -> None:
    content = readme_text()
    deployment = (ROOT / "docs" / "deployment.md").read_text()
    status = (ROOT / "docs" / "product-status.md").read_text()

    assert "Citation-backed company research chat" in content
    assert "two chat messages per UTC day" in content
    assert "ten chat messages per UTC day" in content
    assert "seven days" in content
    assert "CHAT_INDEX_WORKFLOW_TRIGGER_URL" in deployment
    assert "chat-web/" in deployment
    assert "proxy_buffering off;" in deployment
    assert "company-research-chat-design.md" in status
    assert "company-research-chat.md" in status
    assert "Research chat" in status and "Available" in status


def test_readme_documents_hackathon_evaluation_requirements() -> None:
    content = readme_text()

    assert "## Judge's quick path" in content
    assert "## GPT-5.6 integration" in content
    assert "RESEARCH_MODEL=gpt-5.6" in content
    assert "https://developers.openai.com/api/docs/guides/latest-model.md" in content
    assert "## Sample data and reproducible evaluation" in content
    assert "backend/tests/fixtures/chat" in content
    assert "## How Codex accelerated development" in content
    assert "## Key technical decisions" in content

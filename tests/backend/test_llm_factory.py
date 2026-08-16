from backend.config.settings import Settings
from backend.llm.factory import build_llm_provider
from backend.llm.groq.mock_provider import MockGroqProvider
from backend.llm.groq.real_provider import RealGroqProvider


def test_no_api_key_selects_mock_provider():
    settings = Settings(groq_api_key="", _env_file=None)
    provider = build_llm_provider(settings)
    assert isinstance(provider, MockGroqProvider)


def test_api_key_present_selects_real_provider():
    settings = Settings(groq_api_key="fake-key-for-test", _env_file=None)
    provider = build_llm_provider(settings)
    assert isinstance(provider, RealGroqProvider)


async def test_mock_provider_never_fabricates_beyond_evidence():
    provider = MockGroqProvider()
    response = await provider.complete(
        system="test",
        messages=[{"role": "user", "content": "EVIDENCE_JSON:\n[]"}],
        max_tokens=500,
    )
    assert response.provider_mode == "mock"
    import json

    payload = json.loads(response.text)
    assert payload["findings"] == []


async def test_mock_provider_grounds_findings_in_evidence_confidence():
    provider = MockGroqProvider()
    evidence = [
        {"evidence_id": "E-1", "file": "a.py", "line": 10, "result": "hardcoded secret found", "confidence": 0.9, "source": "regex_heuristics"}
    ]
    import json

    response = await provider.complete(
        system="test",
        messages=[{"role": "user", "content": f"EVIDENCE_JSON:\n{json.dumps(evidence)}"}],
        max_tokens=500,
    )
    payload = json.loads(response.text)
    assert len(payload["findings"]) == 1
    assert payload["findings"][0]["evidence_ids"] == ["E-1"]
    assert payload["findings"][0]["confidence"] == 0.9

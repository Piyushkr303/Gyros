import pytest

from backend.core.conditions.safe_evaluator import UnsafeExpressionError, safe_eval


def test_simple_comparison():
    assert safe_eval("confidence > 0.8", {"confidence": 0.9}) is True
    assert safe_eval("confidence > 0.8", {"confidence": 0.5}) is False


def test_boolean_operators():
    ctx = {"severity": "HIGH", "confidence": 0.9}
    assert safe_eval("severity == 'HIGH' and confidence > 0.8", ctx) is True
    assert safe_eval("severity == 'HIGH' and confidence > 0.95", ctx) is False
    assert safe_eval("severity == 'LOW' or confidence > 0.5", ctx) is True
    assert safe_eval("not (severity == 'LOW')", ctx) is True


def test_case_insensitive_string_comparison():
    assert safe_eval("severity == 'high'", {"severity": "HIGH"}) is True


def test_dotted_attribute_access():
    ctx = {"security_agent": {"findings_count": 3}}
    assert safe_eval("security_agent.findings_count > 0", ctx) is True
    assert safe_eval("security_agent.findings_count > 10", ctx) is False


def test_missing_name_resolves_to_none_and_is_falsy_in_comparison():
    assert safe_eval("missing_key > 5", {}) is False


def test_always_true_literal():
    assert safe_eval("True", {}) is True


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo hi')",
        "os.system('echo hi')",
        "(lambda: 1)()",
        "[1,2,3][0]",
        "a.b.c",
        "print('x')",
        "1 if True else 2",
    ],
)
def test_unsafe_expressions_are_rejected(expr):
    with pytest.raises(UnsafeExpressionError):
        safe_eval(expr, {"a": {"b": {"c": 1}}})


def test_invalid_syntax_is_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("severity ==", {})

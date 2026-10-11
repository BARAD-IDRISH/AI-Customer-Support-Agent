
from types import SimpleNamespace

from google.genai import types

import app.agent as agent


def make_response(text=None, function_call=None):
    if function_call:
        parts = [
            types.Part(
                function_call=types.FunctionCall(
                    name=function_call["name"],
                    args=function_call.get("args", {}),
                )
            )
        ]
    else:
        parts = [types.Part(text=text or "")]

    content = types.Content(role="model", parts=parts)

    return SimpleNamespace(
        candidates=[SimpleNamespace(content=content)],
        text=text,
    )


def install_fake_gemini(monkeypatch, responses):
    calls = []

    def fake_generate_content(**kwargs):
        snapshot = dict(kwargs)
        snapshot["contents"] = list(kwargs["contents"])
        calls.append(snapshot)

        if not responses:
            raise AssertionError("Unexpected extra Gemini request")

        return responses.pop(0)

    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=fake_generate_content
        )
    )

    monkeypatch.setattr(agent, "client", fake_client)
    return calls


def get_function_responses(call_arguments):
    responses = []

    for request in call_arguments:
        for content in request["contents"]:
            for part in content.parts:
                response = getattr(
                    part, "function_response", None
                )

                if response is not None:
                    responses.append(response)

    return responses


def test_agent_executes_order_lookup(monkeypatch):
    install_fake_gemini(
        monkeypatch,
        [
            make_response(
                function_call={
                    "name": "lookup_order",
                    "args": {
                        "order_id": "ORD1001",
                        "customer_email": "maya@example.com",
                    },
                }
            ),
            make_response("Your order is shipped."),
        ],
    )

    monkeypatch.setitem(
        agent.TOOL_FUNCTIONS,
        "lookup_order",
        lambda **kwargs: {
            "success": True,
            "order": {
                "order_id": "ORD1001",
                "status": "shipped",
            },
        },
    )

    result = agent.chat("Check my order.")

    assert result == "Your order is shipped."


def test_agent_returns_direct_answer_without_tool(monkeypatch):
    calls = install_fake_gemini(
        monkeypatch,
        [make_response("Hello! How can I help you?")],
    )

    result = agent.chat("Hello")

    assert result == "Hello! How can I help you?"
    assert len(calls) == 1


def test_unknown_tool_is_not_executed(monkeypatch):
    calls = install_fake_gemini(
        monkeypatch,
        [
            make_response(
                function_call={
                    "name": "delete_all_orders",
                    "args": {},
                }
            ),
            make_response("I cannot perform that action."),
        ],
    )

    result = agent.chat("Delete all orders.")

    assert result == "I cannot perform that action."
    assert len(calls) == 2

    responses = get_function_responses(calls)

    assert len(responses) == 1
    assert responses[0].name == "delete_all_orders"
    assert responses[0].response["result"]["success"] is False


def test_tool_exception_is_handled(monkeypatch):
    calls = install_fake_gemini(
        monkeypatch,
        [
            make_response(
                function_call={
                    "name": "lookup_order",
                    "args": {
                        "order_id": "ORD1001",
                        "customer_email": "maya@example.com",
                    },
                }
            ),
            make_response("I couldn't retrieve the order."),
        ],
    )

    def broken_tool(**kwargs):
        raise RuntimeError("Simulated database failure")

    monkeypatch.setitem(
        agent.TOOL_FUNCTIONS,
        "lookup_order",
        broken_tool,
    )

    result = agent.chat("Check my order.")

    assert result == "I couldn't retrieve the order."
    assert len(calls) == 2

    responses = get_function_responses(calls)

    assert len(responses) == 1

    tool_result = responses[0].response["result"]

    assert tool_result["success"] is False
    assert tool_result["error"] == "Tool execution failed."


def test_agent_stops_after_five_rounds(monkeypatch):
    responses = [
        make_response(
            function_call={
                "name": "lookup_order",
                "args": {
                    "order_id": "ORD1001",
                    "customer_email": "maya@example.com",
                },
            }
        )
        for _ in range(5)
    ]

    calls = install_fake_gemini(monkeypatch, responses)
    execution_count = 0

    def fake_lookup(**kwargs):
        nonlocal execution_count
        execution_count += 1
        return {"success": True, "status": "shipped"}

    monkeypatch.setitem(
        agent.TOOL_FUNCTIONS,
        "lookup_order",
        fake_lookup,
    )

    result = agent.chat("Check my order.")

    assert len(calls) == 5
    assert execution_count == 5
    assert "tool-call limit" in result.lower()


def test_api_quota_error_returns_friendly_message(monkeypatch):
    class FakeQuotaError(Exception):
        code = 429

    def fail_request(**kwargs):
        raise FakeQuotaError("Simulated quota exhaustion")

    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=fail_request
        )
    )

    monkeypatch.setattr(agent, "client", fake_client)

    result = agent.chat("Hello")

    assert "rate-limited" in result.lower()
    assert "quota exhaustion" not in result.lower()

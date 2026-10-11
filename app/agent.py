
import logging
import os
from uuid import uuid4

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.tools import (
    lookup_order,
    check_refund_eligibility,
    create_support_ticket,
)

# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
)

MODEL = "gemini-3-flash-preview"
MAX_ROUNDS = 5

if not API_KEY:
    raise RuntimeError(
        "Gemini API key not found. Set GEMINI_API_KEY "
        "or GOOGLE_API_KEY in your .env file."
    )

client = genai.Client(api_key=API_KEY)


# --------------------------------------------------
# Tool function mapping
# Kept replaceable so tests can mock tool functions.
# --------------------------------------------------

TOOL_FUNCTIONS = {
    "lookup_order": lookup_order,
    "check_refund_eligibility": check_refund_eligibility,
    "create_support_ticket": create_support_ticket,
}


# --------------------------------------------------
# System prompt
# --------------------------------------------------

SYSTEM_PROMPT = """
You are a friendly AI customer support assistant.

Your responsibilities:
1. Help customers check their order status.
2. Check refund eligibility using the available tool.
3. Create support tickets for unresolved issues.
4. Ask for missing information when necessary.
5. Explain results clearly and professionally.

IMPORTANT RULES:
- Use tools to retrieve actual order information.
- Never invent order details, refund eligibility, or ticket IDs.
- Never claim an action succeeded unless the tool confirms it.
- For order lookup, collect both order ID and customer email.
- For refund checks, collect both order ID and customer email.
- Before creating a ticket, collect customer email, category,
  and a clear description of the issue.
- Allowed ticket categories are delivery, refund, payment,
  product, and other.
- Include an order ID when the issue concerns a specific order.
- Never reveal another customer's private information.
- If a tool fails, explain that the request could not be completed.
- Do not invent tracking numbers or refund policies.
- Be concise, helpful, and honest.
"""


# --------------------------------------------------
# Gemini function declarations
# Parameter names match app/tools.py.
# --------------------------------------------------

lookup_order_declaration = types.FunctionDeclaration(
    name="lookup_order",
    description=(
        "Look up an order using the customer's registered email "
        "address and order ID. Both are required."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "order_id": types.Schema(
                type=types.Type.STRING,
                description="The order ID, such as ORD1001.",
            ),
            "customer_email": types.Schema(
                type=types.Type.STRING,
                description="The customer's registered email address.",
            ),
        },
        required=["order_id", "customer_email"],
    ),
)

check_refund_declaration = types.FunctionDeclaration(
    name="check_refund_eligibility",
    description=(
        "Check whether a customer's order is eligible for a refund. "
        "Requires order ID and registered customer email."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "order_id": types.Schema(
                type=types.Type.STRING,
                description="The order ID to check.",
            ),
            "customer_email": types.Schema(
                type=types.Type.STRING,
                description="The customer's registered email address.",
            ),
        },
        required=["order_id", "customer_email"],
    ),
)

create_ticket_declaration = types.FunctionDeclaration(
    name="create_support_ticket",
    description=(
        "Create a support ticket for a verified customer."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "customer_email": types.Schema(
                type=types.Type.STRING,
                description="The customer's registered email address.",
            ),
            "category": types.Schema(
                type=types.Type.STRING,
                description=(
                    "Issue category: delivery, refund, payment, "
                    "product, or other."
                ),
            ),
            "message": types.Schema(
                type=types.Type.STRING,
                description="A clear description of the customer's issue.",
            ),
            "order_id": types.Schema(
                type=types.Type.STRING,
                description="Optional related order ID.",
            ),
        },
        required=["customer_email", "category", "message"],
    ),
)

SUPPORT_TOOLS = [
    types.Tool(
        function_declarations=[
            lookup_order_declaration,
            check_refund_declaration,
            create_ticket_declaration,
        ]
    )
]


# --------------------------------------------------
# Friendly API error handling
# --------------------------------------------------

def friendly_api_error(exc):
    """Return a user-friendly message and log diagnostic details."""

    status = getattr(exc, "code", None)

    if status is None:
        status = getattr(exc, "status_code", None)

    error_text = str(exc)

    if API_KEY:
        error_text = error_text.replace(API_KEY, "[REDACTED]")

    error_lower = error_text.lower()

    logger.warning(
        "Gemini API failure | status=%s | type=%s | details=%s",
        status,
        type(exc).__name__,
        error_text[:1500],
    )

    if (
        status == 429
        or "429" in error_lower
        or "rate limit" in error_lower
        or "resource_exhausted" in error_lower
        or "quota" in error_lower
    ):
        return (
            "The AI service is temporarily rate-limited. "
            "Please try again later."
        )

    if (
        status in (401, 403)
        or "unauthorized" in error_lower
    ):
        return (
            "The AI service is temporarily unavailable "
            "because of a configuration or authorization issue."
        )

    if (
        isinstance(status, int) and status >= 500
    ) or any(
        phrase in error_lower
        for phrase in (
            "timeout",
            "timed out",
            "service unavailable",
            "internal server error",
        )
    ):
        return (
            "The AI service is temporarily unavailable. "
            "Please try again shortly."
        )

    return (
        "Sorry, I couldn't process your request right now. "
        "Please try again later."
    )


# --------------------------------------------------
# Response helpers
# --------------------------------------------------

def _get_response_text(response):
    """Safely extract text from a Gemini response."""

    response_text = getattr(response, "text", None)

    if response_text:
        return response_text.strip()

    candidates = getattr(response, "candidates", None) or []

    if not candidates:
        return ""

    content = getattr(candidates[0], "content", None)

    if content is None:
        return ""

    text_parts = []

    for part in getattr(content, "parts", None) or []:
        part_text = getattr(part, "text", None)

        if part_text:
            text_parts.append(part_text)

    return "\n".join(text_parts).strip()


def _get_function_calls(response):
    """Extract function calls from a Gemini response."""

    function_calls = getattr(response, "function_calls", None)

    if function_calls:
        return list(function_calls)

    candidates = getattr(response, "candidates", None) or []

    if not candidates:
        return []

    content = getattr(candidates[0], "content", None)

    if content is None:
        return []

    calls = []

    for part in getattr(content, "parts", None) or []:
        function_call = getattr(part, "function_call", None)

        if function_call is not None:
            calls.append(function_call)

    return calls


# --------------------------------------------------
# Tool execution
# --------------------------------------------------

def _execute_tool(name, args, request_id):
    """Execute a tool using the replaceable TOOL_FUNCTIONS mapping."""

    if not isinstance(args, dict):
        args = dict(args)

    if name == "lookup_order":
        tool_args = {
            "order_id": args.get("order_id", ""),
            "customer_email": args.get("customer_email", ""),
        }

    elif name == "check_refund_eligibility":
        tool_args = {
            "order_id": args.get("order_id", ""),
            "customer_email": args.get("customer_email", ""),
        }

    elif name == "create_support_ticket":
        tool_args = {
            "customer_email": args.get("customer_email", ""),
            "category": args.get("category", ""),
            "message": args.get("message", ""),
            "order_id": args.get("order_id"),
            "request_id": request_id,
        }

    else:
        logger.warning("Unknown Gemini tool requested: %s", name)
        return {
            "success": False,
            "error": "Unknown tool.",
        }

    tool_function = TOOL_FUNCTIONS[name]
    return tool_function(**tool_args)


# --------------------------------------------------
# Main chat function
# --------------------------------------------------

def chat(message, request_id=None):
    """
    Process a customer message using Gemini function calling.

    Args:
        message: Customer's message.
        request_id: Stable ID for deduplicating ticket creation
                    when retrying the same request.

    Returns:
        A user-friendly response string.
    """

    if not isinstance(message, str) or not message.strip():
        return "Please enter a message."

    message = message.strip()

    if request_id is None:
        request_id = str(uuid4())

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=message),
            ],
        )
    ]

    for round_number in range(MAX_ROUNDS):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=SUPPORT_TOOLS,
                    temperature=0.2,
                ),
            )

        except Exception as exc:
            return friendly_api_error(exc)

        function_calls = _get_function_calls(response)

        # Return the final text when there are no more tool calls.
        if not function_calls:
            answer = _get_response_text(response)

            if answer:
                return answer

            logger.warning(
                "Gemini returned no text and no function calls."
            )

            return (
                "I couldn't generate a response just now. "
                "Please try again."
            )

        # Preserve Gemini's function-call response.
        candidates = getattr(response, "candidates", None) or []

        if candidates:
            model_content = getattr(
                candidates[0],
                "content",
                None,
            )

            if model_content is not None:
                contents.append(model_content)

        # Execute each requested tool and send its result back.
        for function_call in function_calls:
            tool_name = getattr(function_call, "name", None)
            raw_args = getattr(function_call, "args", None) or {}

            try:
                tool_args = dict(raw_args)

                logger.info(
                    "Executing Gemini tool: %s",
                    tool_name,
                )

                tool_result = _execute_tool(
                    tool_name,
                    tool_args,
                    request_id,
                )

            except Exception:
                logger.exception(
                    "Tool execution failed: %s",
                    tool_name,
                )

                tool_result = {
                    "success": False,
                    "error": "Tool execution failed.",
                }

            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=tool_name,
                            response={
                                "result": tool_result,
                            },
                        )
                    ],
                )
            )

    logger.warning(
        "Gemini tool-call limit reached after %s rounds.",
        MAX_ROUNDS,
    )

    return "Tool-call limit reached. Please try again."

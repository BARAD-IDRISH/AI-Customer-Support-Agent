
from datetime import date
from app.database import get_connection


REFUND_WINDOW_DAYS = 7

ALLOWED_CATEGORIES = {
    "delivery",
    "refund",
    "payment",
    "product",
    "other",
}


def lookup_order(order_id: str, customer_email: str) -> dict:
    """Look up an order only when its ID and customer email match."""

    if not isinstance(order_id, str) or not isinstance(customer_email, str):
        return {"success": False, "error": "Invalid order details."}

    order_id = order_id.strip().upper()
    customer_email = customer_email.strip().lower()

    if not order_id or not customer_email:
        return {
            "success": False,
            "error": "Order ID and customer email are required.",
        }

    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT
                o.order_id,
                o.product_name,
                o.status,
                o.order_date,
                o.expected_delivery,
                o.delivered_at,
                o.amount
            FROM orders AS o
            JOIN customers AS c
                ON o.customer_id = c.customer_id
            WHERE o.order_id = ?
              AND LOWER(c.email) = ?
            """,
            (order_id, customer_email),
        ).fetchone()

    if order is None:
        return {
            "success": False,
            "error": "We couldn't find an order matching those details.",
        }

    return {"success": True, "order": dict(order)}


def check_refund_eligibility(
    order_id: str,
    customer_email: str,
) -> dict:
    """Check eligibility without issuing a refund."""

    order_result = lookup_order(order_id, customer_email)

    if not order_result["success"]:
        return {
            "success": False,
            "eligible": False,
            "reason": "Order could not be verified.",
        }

    order = order_result["order"]

    if order["status"].lower() != "delivered":
        return {
            "success": True,
            "eligible": False,
            "reason": "Only delivered orders can use this refund process.",
        }

    delivered_at = order.get("delivered_at")

    if not delivered_at:
        return {
            "success": False,
            "eligible": False,
            "reason": "Delivery date is missing; manual review is required.",
        }

    try:
        delivery_date = date.fromisoformat(delivered_at)
    except (ValueError, TypeError):
        return {
            "success": False,
            "eligible": False,
            "reason": "Delivery date is invalid; manual review is required.",
        }

    days_since_delivery = (date.today() - delivery_date).days

    if days_since_delivery < 0:
        return {
            "success": False,
            "eligible": False,
            "reason": "Delivery date is in the future; manual review is required.",
        }

    eligible = days_since_delivery <= REFUND_WINDOW_DAYS

    return {
        "success": True,
        "eligible": eligible,
        "order_id": order["order_id"],
        "amount": order["amount"],
        "days_since_delivery": days_since_delivery,
        "reason": (
            "Eligible for refund review."
            if eligible
            else "The standard 7-day refund window has expired."
        ),
    }


def create_support_ticket(
    customer_email: str,
    category: str,
    message: str,
    order_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """
    Create a ticket for a verified customer.

    Repeating a request_id returns the existing ticket.
    Callers should reuse the same ID when retrying a request.
    """

    if not all(
        isinstance(value, str)
        for value in (customer_email, category, message)
    ):
        return {"success": False, "error": "Invalid ticket details."}

    customer_email = customer_email.strip().lower()
    category = category.strip().lower()
    message = message.strip()

    if not customer_email or len(customer_email) > 254:
        return {
            "success": False,
            "error": "A valid customer email is required.",
        }

    if category not in ALLOWED_CATEGORIES:
        return {
            "success": False,
            "error": "Unsupported ticket category.",
        }

    if not message or len(message) > 2000:
        return {
            "success": False,
            "error": "Message must contain 1–2000 characters.",
        }

    if request_id is not None:
        if (
            not isinstance(request_id, str)
            or not request_id.strip()
            or len(request_id) > 200
        ):
            return {
                "success": False,
                "error": "Invalid request ID.",
            }

        request_id = request_id.strip()

    verified_order_id = None

    with get_connection() as conn:
        customer = conn.execute(
            """
            SELECT customer_id
            FROM customers
            WHERE LOWER(email) = ?
            """,
            (customer_email,),
        ).fetchone()

        if customer is None:
            return {
                "success": False,
                "error": "Customer could not be verified.",
            }

        if order_id:
            order_result = lookup_order(order_id, customer_email)

            if not order_result["success"]:
                return {
                    "success": False,
                    "error": "Order could not be verified.",
                }

            verified_order_id = order_result["order"]["order_id"]

        # Return the existing ticket if this request was already processed.
        if request_id is not None:
            existing = conn.execute(
                """
                SELECT ticket_id, status
                FROM tickets
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()

            if existing is not None:
                return {
                    "success": True,
                    "ticket_id": existing["ticket_id"],
                    "status": existing["status"],
                    "duplicate": True,
                    "message": "This request already has a support ticket.",
                }

        try:
            cursor = conn.execute(
                """
                INSERT INTO tickets (
                    customer_id, order_id, category,
                    message, request_id
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    customer["customer_id"],
                    verified_order_id,
                    category,
                    message,
                    request_id,
                ),
            )

            ticket_id = cursor.lastrowid

        except Exception:
            # A concurrent request may have inserted the same ID.
            if request_id is not None:
                existing = conn.execute(
                    """
                    SELECT ticket_id, status
                    FROM tickets
                    WHERE request_id = ?
                    """,
                    (request_id,),
                ).fetchone()

                if existing is not None:
                    return {
                        "success": True,
                        "ticket_id": existing["ticket_id"],
                        "status": existing["status"],
                        "duplicate": True,
                        "message": "This request already has a support ticket.",
                    }

            raise

    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": "open",
        "duplicate": False,
        "message": "Support ticket created successfully.",
    }

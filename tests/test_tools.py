
from app.database import init_db, get_connection
from app.tools import (
    lookup_order,
    check_refund_eligibility,
    create_support_ticket,
)


def test_lookup_order_success():
    init_db()

    result = lookup_order("ORD1001", "maya@example.com")

    assert result["success"] is True
    assert result["order"]["product_name"] == "Wireless Headphones"
    assert result["order"]["status"] == "shipped"


def test_lookup_order_rejects_wrong_email():
    init_db()

    result = lookup_order("ORD1001", "arjun@example.com")

    assert result["success"] is False
    assert "order" not in result


def test_lookup_order_rejects_unknown_order():
    init_db()

    result = lookup_order("ORD9999", "maya@example.com")

    assert result["success"] is False


def test_lookup_order_rejects_empty_input():
    result = lookup_order("", "maya@example.com")

    assert result["success"] is False


def test_refund_rejected_for_undelivered_order():
    init_db()

    result = check_refund_eligibility(
        "ORD1001", "maya@example.com"
    )

    assert result["success"] is True
    assert result["eligible"] is False


def test_refund_rejected_for_wrong_customer():
    init_db()

    result = check_refund_eligibility(
        "ORD1002", "maya@example.com"
    )

    assert result["success"] is False
    assert result["eligible"] is False


def test_create_support_ticket_success():
    init_db()

    result = create_support_ticket(
        customer_email="maya@example.com",
        category="delivery",
        message="My order has not arrived.",
        order_id="ORD1001",
    )

    assert result["success"] is True
    assert result["status"] == "open"
    assert result["ticket_id"] is not None


def test_create_ticket_rejects_unverified_order():
    init_db()

    result = create_support_ticket(
        customer_email="maya@example.com",
        category="delivery",
        message="Please check my order.",
        order_id="ORD1002",
    )

    assert result["success"] is False


def test_duplicate_request_id_returns_same_ticket():
    init_db()

    first = create_support_ticket(
        customer_email="maya@example.com",
        category="delivery",
        message="My shipment has not arrived.",
        order_id="ORD1001",
        request_id="test-idempotency-key-001",
    )

    second = create_support_ticket(
        customer_email="maya@example.com",
        category="delivery",
        message="My shipment has not arrived.",
        order_id="ORD1001",
        request_id="test-idempotency-key-001",
    )

    assert first["success"] is True
    assert second["success"] is True
    assert second["duplicate"] is True
    assert first["ticket_id"] == second["ticket_id"]

    with get_connection() as conn:
        count = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM tickets
            WHERE request_id = ?
            """,
            ("test-idempotency-key-001",),
        ).fetchone()["total"]

    assert count == 1

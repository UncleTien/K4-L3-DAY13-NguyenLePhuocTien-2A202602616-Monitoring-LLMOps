from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    assert scrub_text("CCCD: 079203012345") == "CCCD: [REDACTED_CCCD]"


def test_scrub_credit_card_formats() -> None:
    for card in ("4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111"):
        assert scrub_text(f"Card: {card}") == "Card: [REDACTED_CREDIT_CARD]"


def test_scrub_event_nested_context_and_exception() -> None:
    from app.logging_config import scrub_event

    event = {
        "event": "Contact student@example.com",
        "session_id": "student@example.com",
        "exception": "ValueError: CCCD 079203012345",
        "payload": {"items": ["4111 1111 1111 1111", {"phone": "0901234567"}]},
        "tokens_in": 42,
    }
    safe = scrub_event(None, "error", event)
    assert safe["event"] == "Contact [REDACTED_EMAIL]"
    assert safe["session_id"] == "[REDACTED_EMAIL]"
    assert safe["exception"] == "ValueError: CCCD [REDACTED_CCCD]"
    assert safe["payload"]["items"] == [
        "[REDACTED_CREDIT_CARD]", {"phone": "[REDACTED_PHONE_VN]"}
    ]
    assert safe["tokens_in"] == 42

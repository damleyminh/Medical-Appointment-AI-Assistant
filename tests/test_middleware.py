"""
tests/test_middleware.py — Unit tests for middleware components.

Run with:  pytest tests/ -v
"""
import pytest
from src.middleware.pii import PIIMiddleware
from src.middleware.call_limits import CallLimitMiddleware
from src.middleware.hitl import HumanInTheLoopMiddleware


# ── PIIMiddleware ─────────────────────────────────────────────────────────────

class TestPIIMiddleware:
    def setup_method(self):
        self.mw = PIIMiddleware()

    def test_masks_phone_number(self):
        text = "Call me at 416-555-1234 for details."
        masked, pii_map = self.mw.mask(text)
        assert "416-555-1234" not in masked
        assert len(pii_map) == 1
        assert "416-555-1234" in pii_map.values()

    def test_masks_email(self):
        text = "Contact me at jane.doe@example.com"
        masked, pii_map = self.mw.mask(text)
        assert "jane.doe@example.com" not in masked
        assert any("EMAIL" in k for k in pii_map)

    def test_masks_ssn(self):
        text = "My SSN is 123-45-6789"
        masked, pii_map = self.mw.mask(text)
        assert "123-45-6789" not in masked
        assert any("SSN" in k for k in pii_map)

    def test_no_pii_returns_empty_map(self):
        text = "I need to reschedule my appointment."
        masked, pii_map = self.mw.mask(text)
        assert masked == text
        assert pii_map == {}

    def test_unmask_restores_original(self):
        text = "Call 416-555-9999 or email test@clinic.com"
        masked, pii_map = self.mw.mask(text)
        restored = self.mw.unmask(masked, pii_map)
        assert "416-555-9999" in restored
        assert "test@clinic.com" in restored

    def test_multiple_pii_types(self):
        text = "Name: John, phone: 647-123-4567, email: j@h.ca, SSN: 987-65-4321"
        masked, pii_map = self.mw.mask(text)
        assert "647-123-4567" not in masked
        assert "j@h.ca" not in masked
        assert "987-65-4321" not in masked
        assert len(pii_map) >= 3


# ── CallLimitMiddleware ───────────────────────────────────────────────────────

class TestCallLimitMiddleware:
    def test_increments_count(self):
        mw = CallLimitMiddleware(max_calls=5)
        assert mw.check_and_increment(0) == 1
        assert mw.check_and_increment(3) == 4

    def test_raises_at_limit(self):
        mw = CallLimitMiddleware(max_calls=3)
        with pytest.raises(RuntimeError):
            mw.check_and_increment(3)

    def test_raises_beyond_limit(self):
        mw = CallLimitMiddleware(max_calls=2)
        with pytest.raises(RuntimeError):
            mw.check_and_increment(5)

    def test_allows_up_to_limit(self):
        mw = CallLimitMiddleware(max_calls=3)
        assert mw.check_and_increment(2) == 3


# ── HumanInTheLoopMiddleware (API mode) ───────────────────────────────────────

class TestHITLMiddleware:
    def setup_method(self):
        self.mw = HumanInTheLoopMiddleware()
        self.draft = "Your appointment has been rescheduled to March 10."

    def test_approve_returns_draft_unchanged(self):
        action, final = self.mw.review_api(self.draft, "approved")
        assert action == "approved"
        assert final == self.draft

    def test_edit_returns_edited_text(self):
        edited = "Your appointment has been moved to March 12 at 2 PM."
        action, final = self.mw.review_api(self.draft, "edited", edited_text=edited)
        assert action == "edited"
        assert final == edited

    def test_escalate_returns_escalation_message(self):
        action, final = self.mw.review_api(self.draft, "escalated")
        assert action == "escalated"
        assert "escalated" in final.lower()
        assert "staff" in final.lower()

    def test_edit_without_text_falls_back_to_draft(self):
        action, final = self.mw.review_api(self.draft, "edited", edited_text=None)
        assert final == self.draft


# ── Appointment Tools ─────────────────────────────────────────────────────────

class TestAppointmentTools:
    def test_lookup_valid_appointment(self):
        from src.tools.appointment_tools import lookup_appointment
        apt = lookup_appointment("APT-001")
        assert apt is not None
        assert apt["id"] == "APT-001"

    def test_lookup_invalid_appointment(self):
        from src.tools.appointment_tools import lookup_appointment
        assert lookup_appointment("APT-999") is None

    def test_get_available_slots_returns_list(self):
        from src.tools.appointment_tools import get_available_slots
        slots = get_available_slots("general")
        assert isinstance(slots, list)
        assert len(slots) > 0

    def test_get_prep_mri(self):
        from src.tools.appointment_tools import get_prep_instructions
        result = get_prep_instructions("mri")
        assert "MRI" in result
        assert "metal" in result.lower()

    def test_get_prep_ct(self):
        from src.tools.appointment_tools import get_prep_instructions
        result = get_prep_instructions("ct")
        assert "CT" in result

    def test_get_prep_unknown_falls_back_to_general(self):
        from src.tools.appointment_tools import get_prep_instructions
        result = get_prep_instructions("laser_surgery")
        assert "General" in result or "medication" in result.lower()

    def test_cancel_appointment(self):
        from src.tools.appointment_tools import cancel_appointment
        result = cancel_appointment("APT-002", "personal reasons")
        assert result["success"] is True
        assert result["appointment"]["status"] == "cancelled"

    def test_cancel_unknown_appointment(self):
        from src.tools.appointment_tools import cancel_appointment
        result = cancel_appointment("APT-999")
        assert result["success"] is False

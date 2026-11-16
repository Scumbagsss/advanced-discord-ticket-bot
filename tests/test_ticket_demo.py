"""Tests exercise the separate synthetic backend; no private code is imported."""
import tempfile
from pathlib import Path
import unittest

from ticket_demo import Actor, TicketStore, WorkflowError


class TicketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "tickets.sqlite3"
        self.store = TicketStore(self.db)
        self.player = Actor("player-01")
        self.staff = Actor("staff-01", True)
        self.id = self.store.create(self.player, "Support", "Synthetic message")

    def tearDown(self):
        self.temp.cleanup()

    def test_initial_state(self):
        self.assertEqual(self.store.get(self.id)["status"], "open")

    def test_history_created(self):
        self.assertEqual(self.store.history(self.id)[0]["operation"], "created")

    def test_persistence(self):
        self.assertEqual(TicketStore(self.db).get(self.id)["subject"], "Support")

    def test_staff_assignment(self):
        self.assertEqual(self.store.assign(self.staff, self.id, "staff-02")["assignee"], "staff-02")

    def test_player_cannot_assign(self):
        with self.assertRaises(WorkflowError):
            self.store.assign(self.player, self.id, "staff-02")

    def test_start_requires_assignee(self):
        with self.assertRaises(WorkflowError):
            self.store.start(self.staff, self.id)

    def test_start_after_assignment(self):
        self.store.assign(self.staff, self.id, "staff-02")
        self.assertEqual(self.store.start(self.staff, self.id)["status"], "in_progress")

    def test_duplicate_assign_does_not_duplicate_event(self):
        self.store.assign(self.staff, self.id, "staff-02")
        self.store.assign(self.staff, self.id, "staff-02")
        self.assertEqual(len(self.store.history(self.id)), 2)

    def test_duplicate_start_does_not_duplicate_event(self):
        self.store.assign(self.staff, self.id, "staff-02")
        self.store.start(self.staff, self.id)
        self.store.start(self.staff, self.id)
        self.assertEqual(len(self.store.history(self.id)), 3)

    def test_staff_can_close(self):
        ticket = self.store.close(self.staff, self.id, "Resolved")
        self.assertEqual(ticket["status"], "closed")
        self.assertEqual(ticket["closed_reason"], "Resolved")

    def test_player_cannot_close(self):
        with self.assertRaises(WorkflowError):
            self.store.close(self.player, self.id, "Attempt")

    def test_closing_requires_reason(self):
        with self.assertRaises(WorkflowError):
            self.store.close(self.staff, self.id, "  ")

    def test_cannot_modify_closed_ticket(self):
        self.store.close(self.staff, self.id, "Resolved")
        for operation in (
            lambda: self.store.close(self.staff, self.id, "Again"),
            lambda: self.store.assign(self.staff, self.id, "staff-02"),
            lambda: self.store.start(self.staff, self.id),
        ):
            with self.assertRaises(WorkflowError):
                operation()

    def test_unknown_ticket(self):
        with self.assertRaises(WorkflowError):
            self.store.get(100500)

    def test_invalid_actor(self):
        with self.assertRaises(WorkflowError):
            self.store.create(Actor(" "), "Subject", "Body")

    def test_subject_limits(self):
        with self.assertRaises(WorkflowError):
            self.store.create(self.player, "x" * 121, "Body")

    def test_html_escaping(self):
        ticket_id = self.store.create(self.player, "<script>x</script>", "<b>text</b>")
        html = self.store.export_html(ticket_id)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;b&gt;", html)

    def test_sql_injection_string_as_data(self):
        subject = "'; DROP TABLE tickets; --"
        ticket_id = self.store.create(self.player, subject, "Content")
        self.assertEqual(self.store.get(ticket_id)["subject"], subject)

    def test_close_reason_is_escaped_in_export(self):
        self.store.close(self.staff, self.id, "<script>unsafe</script>")
        html = self.store.export_html(self.id)
        self.assertIn("&lt;script&gt;unsafe&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_unauthorized_action_preserves_audit_history(self):
        original = self.store.history(self.id)
        with self.assertRaises(WorkflowError):
            self.store.assign(self.player, self.id, "hijack")
        self.assertEqual(self.store.history(self.id), original)

    def test_reject_in_memory(self):
        with self.assertRaises(ValueError):
            TicketStore(":memory:")


if __name__ == "__main__":
    unittest.main()

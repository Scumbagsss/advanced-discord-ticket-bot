"""Runnable synthetic ticket backend. Not the production Discord application."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
import json
import sqlite3
from pathlib import Path


class WorkflowError(Exception):
    """Invalid workflow operation."""


@dataclass(frozen=True)
class Actor:
    id: str
    staff: bool = False


class TicketStore:
    """SQLite ticket workflow. The caller must authenticate Actor identities."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("Use a file-backed database")
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('open','in_progress','closed')),
                    assignee TEXT,
                    closed_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                    actor TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    details TEXT NOT NULL,
                    at TEXT NOT NULL
                );
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def validate(value: str, name: str, limit: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise WorkflowError(f"Invalid {name}")
        return value.strip()

    @staticmethod
    def require_staff(actor: Actor) -> str:
        if not isinstance(actor, Actor) or not actor.staff:
            raise WorkflowError("Staff permission required")
        return TicketStore.validate(actor.id, "actor", 80)

    @staticmethod
    def event(db, ticket_id: int, actor: str, operation: str, details: str = ""):
        db.execute(
            "INSERT INTO events (ticket_id,actor,operation,details,at) VALUES (?,?,?,?,?)",
            (ticket_id, actor, operation, details, datetime.now(timezone.utc).isoformat()),
        )

    @staticmethod
    def row(db, ticket_id: int):
        if type(ticket_id) is not int or ticket_id <= 0:
            raise WorkflowError("Invalid ticket ID")
        ticket = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if ticket is None:
            raise WorkflowError("Ticket does not exist")
        return ticket

    def create(self, actor: Actor, subject: str, description: str) -> int:
        if not isinstance(actor, Actor):
            raise WorkflowError("Invalid actor")
        author = self.validate(actor.id, "actor", 80)
        subject = self.validate(subject, "subject", 120)
        description = self.validate(description, "description", 2000)
        with self.connect() as db:
            cur = db.execute(
                "INSERT INTO tickets (author,subject,description,status) VALUES (?,?,?,'open')",
                (author, subject, description),
            )
            ticket_id = int(cur.lastrowid)
            self.event(db, ticket_id, author, "created")
        return ticket_id

    def get(self, ticket_id: int) -> dict:
        with self.connect() as db:
            return dict(self.row(db, ticket_id))

    def assign(self, actor: Actor, ticket_id: int, assignee: str) -> dict:
        staff = self.require_staff(actor)
        assignee = self.validate(assignee, "assignee", 80)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = self.row(db, ticket_id)
            if ticket["status"] == "closed":
                raise WorkflowError("Ticket already closed")
            if ticket["assignee"] != assignee:
                db.execute("UPDATE tickets SET assignee=? WHERE id=?", (assignee, ticket_id))
                self.event(db, ticket_id, staff, "assigned", assignee)
        return self.get(ticket_id)

    def start(self, actor: Actor, ticket_id: int) -> dict:
        staff = self.require_staff(actor)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = self.row(db, ticket_id)
            if ticket["status"] == "closed":
                raise WorkflowError("Ticket already closed")
            if not ticket["assignee"]:
                raise WorkflowError("Assign staff before starting")
            if ticket["status"] == "open":
                db.execute("UPDATE tickets SET status='in_progress' WHERE id=?", (ticket_id,))
                self.event(db, ticket_id, staff, "started")
        return self.get(ticket_id)

    def close(self, actor: Actor, ticket_id: int, reason: str) -> dict:
        staff = self.require_staff(actor)
        reason = self.validate(reason, "reason", 500)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = self.row(db, ticket_id)
            if ticket["status"] == "closed":
                raise WorkflowError("Ticket already closed")
            db.execute(
                "UPDATE tickets SET status='closed',closed_reason=? WHERE id=?",
                (reason, ticket_id),
            )
            self.event(db, ticket_id, staff, "closed", reason)
        return self.get(ticket_id)

    def history(self, ticket_id: int) -> list[dict]:
        with self.connect() as db:
            self.row(db, ticket_id)
            return [
                dict(event) for event in db.execute(
                    "SELECT actor,operation,details,at FROM events WHERE ticket_id=? ORDER BY id",
                    (ticket_id,),
                )
            ]

    def export_html(self, ticket_id: int) -> str:
        ticket = self.get(ticket_id)
        entries = "".join(
            f"<li>{escape(item['operation'])}: {escape(item['details'])}</li>"
            for item in self.history(ticket_id)
        )
        return (
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            f"<title>Ticket {ticket_id}</title>"
            f"<h1>{escape(ticket['subject'])}</h1>"
            f"<p>{escape(ticket['description'])}</p><ul>{entries}</ul></html>"
        )


def main():
    parser = argparse.ArgumentParser(description="Synthetic ticket backend demo")
    parser.add_argument("--db", default="demo-tickets.sqlite3")
    args = parser.parse_args()
    store = TicketStore(args.db)
    player, staff = Actor("demo-player"), Actor("demo-moderator", True)
    ticket_id = store.create(player, "Example request", "Synthetic test message")
    store.assign(staff, ticket_id, staff.id)
    store.start(staff, ticket_id)
    store.close(staff, ticket_id, "Demo completed")
    print(json.dumps({"ticket": store.get(ticket_id), "events": store.history(ticket_id)}, indent=2))


if __name__ == "__main__":
    main()

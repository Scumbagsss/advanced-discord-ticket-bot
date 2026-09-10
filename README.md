# Advanced Discord Ticket Bot

> **Portfolio showcase — production source is private and this repository is intentionally non-runnable.**

Multi-category Discord ticket system with staff assignment, statuses, participants and HTML transcripts.

## What it demonstrates

- Multiple ticket categories
- Dynamic forms
- Private ticket channels
- Staff assignment
- Status workflow
- Participant management
- Required close reason
- HTML transcript export

## Technology

Python • discord.py • Dynamic Modals • Persistent Views • HTML export

## High-level workflow

1. Choose ticket category
2. Collect category-specific fields
3. Create private ticket
4. Route/assign staff
5. Resolve and export transcript

## Public interface preview

The public skeleton exposes only the architectural surface:

- `create_ticket(...)`
- `assign_staff(...)`
- `set_status(...)`
- `add_participant(...)`
- `close_ticket(...)`
- `export_transcript(...)`

The production implementations behind these methods are withheld. See [`NOTICE.md`](NOTICE.md).

## Repository contents

- `src/public_interface.py` — non-runnable interface skeleton;
- `docs/ARCHITECTURE.md` — high-level design;
- `examples/config.example.jsonc` — sanitized configuration shape;
- `LICENSE` — explicit all-rights-reserved notice.

## Status

Production-tested private project / portfolio edition.

# DEV_LOG

## Project Overview & Tech Stack
- **Backend:** FastAPI (Python), SQLAlchemy (Async), Uvicorn.
- **Frontend:** React, Next.js / Vite, TailwindCSS.
- **Database:** SQLite (`arp.db`) - Async.
- **Architecture:** Monolith API backend with a separate frontend. Double-Entry Accounting Ledger implemented.

## Current Milestone
- Fully synchronized frontend and backend modules.
- Implemented and verified double-entry accounting mechanics.
- Shifts and void operations correctly managed and audited.
- Core booking features (Flight, Transport, Visa, etc.) are stable and adhere to specified requirements.

## Architecture Decisions
- **Documentation:** Kept central and continuously updated in `/docs` and manuals.
- **Accounting (Double-Entry):** Using `journal_entries` and `journal_entry_lines` for immutable accounting records, replacing single-table balance columns. Balances are dynamically calculated using `get_entity_balance`.
- **Shifts:** Shift widget integrated; financial transactions are tied to the active shift.
- **Bookings:** Strict adherence to data model (counters `PREFIX-XXXX`, defaults to `pending`, `cost_price` hidden on schema level, removed redundant fields like `seat_number`).

## Active Discussion & Review
- Initial WeasyPrint PDF fallback mode active due to missing `libgobject` on host environment. Dockerization is planned/pending to solve this cleanly.
- Accounting engine validated against actual DB state.

## Immediate Next Tasks
- Test WeasyPrint and Arabic layout inside a Linux Docker container.
- Extend test coverage for remaining specialized edge cases.
- Final production readiness and performance optimizations.

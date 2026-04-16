---
name: feedback_testing
description: Integration tests must use real database, never mocks. Also no snapshot tests for API responses.
type: feedback
---
# Testing Rules

## No database mocks in integration tests
Use real DB connection for all files in `tests/integration/`.

**Why:** Q1 incident — mocked tests passed, production migration failed. Mock schema diverged from real DB.

**How to apply:** When writing or reviewing integration tests, always use the test database config. If a test file imports a mock DB helper, flag it.

## No snapshot tests for API responses
API response structure changes often. Snapshots create false failures.

**Why:** Team spent 2 hours updating 47 snapshots after a single field rename.

**How to apply:** Test specific fields and status codes, not entire response bodies.

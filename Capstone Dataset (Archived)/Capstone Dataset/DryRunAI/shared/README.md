# DryRunAI Shared Infrastructure

The `shared/` package contains reusable infrastructure for every DryRunAI service.

Services should use shared modules for:

- Project constants from `shared.constants`
- Config loading from `shared.config`
- CSV, JSON, image, and safe file IO from `shared.io`
- Structured rotating logging from `shared.logging`
- Path, time, ID, string, and hashing helpers from `shared.utils`
- Common validation from `shared.validation`
- Project exceptions from `shared.exceptions`

Builders should keep business logic inside their own service packages and depend on `shared/` for infrastructure only.

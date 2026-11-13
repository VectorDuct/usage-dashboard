# Changelog

## 0.1.0 — initial release candidate

- Independently implemented portable dashboard with configurable demo/file/HTTP/Naoya aggregate sources.
- Explicit daily windows, separate request/Token units, unknown-safe balances, freshness checks and shared Token pool projection.
- Local daily SQLite snapshots, English/Chinese UI, light/dark themes, responsive layout, source filtering.
- CLI, Python packaging metadata, Docker/Compose, CI, sample configs and source contract.

Naoya compatibility is verified against synthetic fixtures of the documented summary dialect, not a live provider. No existing production deployment/data has been migrated. Public load testing, provider-specific integration tests and Windows runtime testing are not claimed.

Local validation: 26 Python regression/integration tests passed on Python 3.11 and 3.12; synthetic browser checks passed for desktop/mobile, language/theme, literal untrusted labels, disconnect and recovery. The container built and ran as UID 10001 with network disabled and a read-only root filesystem. Python wheel building was also exercised. The GitHub CI workflow is provided but has not run on a hosted repository.

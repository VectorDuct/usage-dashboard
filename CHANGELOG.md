# Changelog

Notable changes are documented using [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories. Release dates reflect publication of the corresponding version.

## [Unreleased]

## [0.1.0] - 2026-11-16

### Added

- Private vulnerability disclosure policy and expanded contributor verification guide.
- EditorConfig settings for UTF-8, LF line endings, final newlines, and Python indentation.
- Illustrative OpenAI-compatible, Anthropic, and Vertex AI aggregate-source configuration in `examples/config.multi-provider.example.json`.
- Independently implemented portable dashboard with configurable demo, file, HTTP and real-time aggregate sources.
- Explicit daily windows, separate request/Token units, unknown-safe balances, freshness checks and shared Token pool projection.
- Local daily SQLite snapshots, English/Chinese UI, light/dark themes, responsive layout, source filtering.
- CLI, Python packaging metadata, Docker/Compose, CI, sample configs and source contract.
- Sovereign Telemetry runs on Python 3.11+ with a standard-library runtime and IANA timezone data; Windows deployments may require the optional `tzdata` package.

- Deterministic source release ZIP including security policy, contributor guide, EditorConfig, examples, and a per-file SHA-256 manifest.

### Fixed

- Source archive manifests use portable forward-slash paths and platform-independent filename ordering.

### Security

- Read-only aggregate-source collection without model invocation, account modification, or access to provider databases.
- Server-side source credentials and allowlisted SQLite snapshots; raw upstream authentication/error responses are not exposed in browser APIs.
- No built-in user authentication: private deployments require an authenticated HTTPS reverse proxy when exposed beyond loopback.
- No external fonts, scripts, or telemetry beacons; configured source polling is functional traffic, not external analytics.

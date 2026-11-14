# Security Policy

## Supported Versions

| Version | Security fixes |
| --- | --- |
| 0.1.x | Supported; use the latest available patch |
| Other versions | Not supported |

## Reporting a Vulnerability

Report suspected vulnerabilities privately to [contact@vectorduct.com](mailto:contact@vectorduct.com) or [founders@vectorduct.com](mailto:founders@vectorduct.com). Do not open public GitHub issues containing vulnerability details or exploit instructions before coordinated disclosure.

We aim to acknowledge reports within 48 hours. Resolution time depends on the finding; acknowledgment is not a repair SLA. Include the version, a redacted configuration, expected and observed behavior, and synthetic source data. Do not send provider credentials, account records, real SQLite databases, private prompts, or full environment dumps. Coordinate publication with maintainers after assessment and remediation.

## Security Boundary

- The dashboard reads configured aggregate sources and stores allowlisted daily snapshots in local SQLite. It does not invoke models, modify provider accounts, or provide access to provider databases.
- Source authentication secrets are read from server-side environment variables. Upstream credentials and raw authentication/error responses must not appear in browser APIs or snapshot records.
- The application has no built-in user authentication. Keep private source metrics behind an authenticated HTTPS reverse proxy when exposing the dashboard beyond loopback.
- Source exporters must supply non-sensitive aggregate labels and identifiers. Allowlisted text fields are not a secret-redaction system; operators control source selection and deployment exposure.
- There are no external fonts, scripts, or telemetry beacons in the dashboard UI. Configured server-side source polling is functional traffic. Operators must secure the host, environment, source endpoints, and snapshot directory.

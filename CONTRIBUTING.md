# Contributing

Run `python3 -m unittest discover -s tests -v` before proposing changes. Runtime code should remain standard-library only unless a concrete requirement justifies a dependency. Add regression coverage for changed aggregation, freshness, auth and adapter behavior.

Use synthetic fixtures. Never include provider credentials, account records, prompt/response bodies, real operational databases or deployment snapshots in issues or patches. Describe a source's aggregate schema and redact identifiers. Exporters should map to the existing contract before a provider-specific adapter is proposed.

Keep UI changes usable in both languages, light/dark themes and a 390 px viewport. No external fonts, scripts or telemetry. Optional browser checks live in `tests/browser.mjs`.

Report a suspected vulnerability privately to the repository maintainer through the hosting platform's private security reporting feature when available; do not post live credentials in a public issue.

# Contributing

## Local Verification

Use Python 3.11 or newer. From the repository root, run:

```bash
python3 -m unittest discover -s tests -v
python3 -m usage_dashboard --config examples/config.demo.json --check
python3 -m pip install .
usage-dashboard --version
python3 tools/release.py
```

CI tests Python 3.11, 3.12, and 3.13, verifies the installed command from outside the repository, and builds the container:

```bash
docker build -t usage-dashboard:test .
```

On Windows, use `python` if `python3` is unavailable; install `tzdata` when system IANA timezone data is missing. The configuration check does not fetch sources or create a SQLite file.

## Code Style and Boundaries

Follow existing Python formatting and type annotations, use valid UTF-8, and keep configuration/fixtures synthetic. Keep changes focused and include verification results in pull requests. Runtime code should remain standard-library only unless a concrete requirement justifies a dependency. Add regression coverage for changed aggregation, freshness, auth and adapter behavior.

Use synthetic fixtures. Never include provider credentials, account records, prompt/response bodies, real operational databases or deployment snapshots in issues or patches. Describe a source's aggregate schema and redact identifiers. Exporters should map to the existing contract before a provider-specific adapter is proposed.

Keep UI changes usable in both languages, light/dark themes and a 390 px viewport. No external fonts, scripts or telemetry. Optional browser checks live in `tests/browser.mjs`.

Report suspected vulnerabilities privately as described in [SECURITY.md](./SECURITY.md), not in public issues.

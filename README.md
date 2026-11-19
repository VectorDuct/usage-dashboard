# Usage Dashboard (`usage-dashboard`)

**[简体中文](./README.zh-CN.md)** · **[Source Contract](./docs/data-contract.md)**

> **VectorDuct Primitive: Sovereign Telemetry** ([vectorduct.com](https://vectorduct.com/#stack))

A lightweight, read-only observability dashboard for tracking model API usage, quota balances, and daily historical snapshots. Aggregate metrics from your own services while keeping credentials and upstream account records strictly on the server.

## Releases

[v0.1.0 — Initial Public Release](https://github.com/VectorDuct/usage-dashboard/releases/tag/v0.1.0). Download the source ZIP and `SHA256SUMS`; extract it and run `python -m pip install .` in the extracted directory (Python 3.11+).

Verify downloaded assets against `SHA256SUMS` before installation (Linux: `sha256sum -c SHA256SUMS`). Source ZIPs also include a per-file `MANIFEST.sha256`.

## What It Does

- **Multiple Configurable Sources**: Aggregates metrics across multi-model endpoints (OpenAI-compatible, DeepSeek, Anthropic, Google Cloud Vertex AI) through local JSON files, authenticated HTTPS JSON endpoints, and real-time summary adapters; also supports synthetic demo feeds.
- **Quota & Health Tracking**: Displays request and token quotas, remaining balances, source freshness, and completion success rates.
- **Deterministic Aggregation**: Aggregates model metrics strictly across matching units and daily time windows. Failed or unreachable sources are surfaced explicitly rather than masked as healthy.
- **SQLite Daily Snapshots**: Automatically records daily historical snapshots in a local SQLite database with configurable retention (`1–365` days) and zero upstream database dependencies.
- **Zero-Build Runtime**: Built on the Python 3.11+ standard library (using system IANA timezone data). Includes a responsive light/dark web interface with English and Chinese localization.

## Quick Start

Run the dashboard locally with synthetic demo data (makes no external network requests):

```bash
python3 -m usage_dashboard
```

Open [http://127.0.0.1:8900](http://127.0.0.1:8900). Press `Ctrl+C` to stop. *(On Windows, use `python` and install timezone data if needed via `python -m pip install tzdata`.)*

Run with the Chinese demo preset:

```bash
python3 -m usage_dashboard --config examples/config.demo.json
```

Optional installation into a virtual environment:

```bash
python -m pip install .
usage-dashboard --version
usage-dashboard --config /path/to/config.json
```

## Using Your Own Data

Copy `examples/config.http.json` to `config.json`, point the `url` to your metrics exporter, and inject the bearer token via an environment variable:

```json
{
  "site": {"title": "Team Usage", "description": "Internal model usage telemetry.", "language": "en"},
  "timezone": "UTC",
  "data_dir": "data",
  "sources": [{
    "id": "team",
    "label": "Team Workspace",
    "type": "http",
    "url": "https://metrics.example.com/usage.json",
    "bearer_env": "USAGE_SOURCE_TOKEN"
  }]
}
```

Validate your configuration and start the service:

```bash
python3 -m usage_dashboard --config config.json --check
python3 -m usage_dashboard --config config.json
```

`--check` validates configuration syntax without fetching remote sources or creating a SQLite file. Relative paths in `config.json` resolve relative to the configuration file's directory.

For three independent provider usage pools, see the [multi-provider example](./examples/config.multi-provider.example.json):

```bash
python3 -m usage_dashboard --config examples/config.multi-provider.example.json --check
```

The HTTPS URLs are illustrative summary exporters for OpenAI-compatible, Anthropic, and Google Cloud Vertex AI usage, not native provider APIs. Replace them with your own exporters implementing the [aggregate source contract](./docs/data-contract.md), and supply exporter tokens through the named environment variables. Do not use provider API keys as exporter tokens. Configuration validation does not verify endpoint reachability, authentication, or returned data. Sources must describe disjoint usage/quota pools to avoid double-counting.

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| `host`, `port` | `127.0.0.1`, `8900` | Listen address (`--host` / `--port` CLI flags override). |
| `timezone` | `UTC` | Display clock timezone; source quota windows remain independent. |
| `poll_interval` | `30` | Seconds between sequential collection cycles. |
| `stale_after` | `120` | Maximum accepted observation age in seconds. |
| `timeout` | `5` | Per-request network timeout in seconds. |
| `history_days` | `30` | SQLite daily snapshot retention (`1–365` days). |
| `data_dir` | `data` | Local SQLite directory (keep outside version control). |
| `site.language` | `en` | Initial UI language (`en` or `zh-CN`). |
| `sources[].enabled` | `true` | Enable or disable collection and display for a specific source. |

Configure up to 32 distinct source IDs (`[a-zA-Z0-9_-]`). Remote HTTP sources must use `HTTPS`, responses are capped at `2 MiB`, and redirects are refused.

## Docker Deployment

```bash
docker compose up --build -d
```

The default Compose setup starts the demo on `127.0.0.1:8900` as non-root `UID 10001` with a read-only root filesystem, a named data volume, and resource limits. To mount production configuration, add a local override file (`compose.local.yaml`):

```yaml
services:
  dashboard:
    command: ["python", "-m", "usage_dashboard", "--host", "0.0.0.0", "--config", "/app/config.json"]
    volumes:
      - ./config.json:/app/config.json:ro
    environment:
      - USAGE_SOURCE_TOKEN
```

```bash
docker compose -f compose.yaml -f compose.local.yaml up --build -d
```

## Security & Deployment Posture

The dashboard renders a read-only aggregate view without built-in user authentication. Place it behind an authenticated HTTPS reverse proxy (e.g., Nginx, Caddy, or Cloudflare Access) when deploying outside a private loopback network. Only allowlisted aggregate fields are stored; upstream headers, URLs, and raw error bodies are discarded.

## Development & Testing

```bash
python3 -m unittest discover -s tests -v
python3 -m usage_dashboard --config examples/config.demo.json --check
```

Optional browser UI verification using Playwright:

```bash
npm install --no-save --package-lock=false playwright
npx playwright install chromium
DASHBOARD_URL=http://127.0.0.1:8900 node tests/browser.mjs
```

## License

MIT License. Maintained by [VectorDuct](https://vectorduct.com).

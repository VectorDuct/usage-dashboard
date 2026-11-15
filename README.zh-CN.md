# Usage Dashboard (`usage-dashboard`)

**[English](./README.md)** · **[数据源协议 (Source Contract)](./docs/data-contract.md)**

> **VectorDuct 核心原语：Sovereign Telemetry（主权遥测账本）** ([vectorduct.com](https://vectorduct.com/#stack))

轻量级、只读的模型用量与配额可观测性看板。支持从自有服务端聚合模型调用与额度指标，在本地持久化每日快照，同时确保上游凭据与账户记录严格保留在服务端边界内。

## 核心功能

- **多类型数据源接入**：通过本地 JSON 文件、带 Bearer 鉴权的 HTTPS JSON 端点及实时汇总适配器，聚合多模型端点（OpenAI 兼容接口、DeepSeek、Anthropic、Google Cloud Vertex AI）的指标；同时支持内置合成演示数据。
- **配额与健康度监控**：展示请求次数（Requests）与 Token 额度、剩余可用量、数据源新鲜度（Freshness）及调用成功率。
- **确定性聚合计算**：严格按相同计量单位与每日时间窗口聚合模型指标；未知余额保持未知状态，采集失败的数据源会明确标记异常，绝不伪装为健康状态。
- **SQLite 每日历史快照**：自动在本地 SQLite 数据库中保存每日历史用量快照，支持配置保留天数（`1–365` 天），无需访问上游业务数据库。
- **零构建标准库运行时**：运行时仅依赖 Python 3.11+ 标准库（配合系统 IANA 时区数据），内置中英双语切换、亮/暗色主题及移动端自适应布局。

## 快速体验

在项目根目录下直接启动（默认加载本地合成演示数据，不发起任何外部网络请求）：

```bash
python3 -m usage_dashboard
```

浏览器打开 [http://127.0.0.1:8900](http://127.0.0.1:8900) 即可预览，按 `Ctrl+C` 停止。（Windows 环境请使用 `python`，如缺少时区数据可执行 `python -m pip install tzdata`）。

加载中文演示配置：

```bash
python3 -m usage_dashboard --config examples/config.demo.json
```

也可安装到虚拟环境中作为命令行工具运行：

```bash
python -m pip install .
usage-dashboard --version
usage-dashboard --config /path/to/config.json
```

## 接入自有数据

复制 `examples/config.http.json` 为 `config.json`，修改数据源 URL，并通过部署环境的密钥管理机制注入对应的环境变量（配置文件中仅填写环境变量名，切勿直接写入密钥明文）：

```json
{
  "site": {"title": "Team Usage", "description": "内部模型用量与配额看板", "language": "zh-CN"},
  "timezone": "Asia/Shanghai",
  "data_dir": "data",
  "sources": [{
    "id": "team",
    "label": "核心研发工作区",
    "type": "http",
    "url": "https://metrics.example.com/usage.json",
    "bearer_env": "USAGE_SOURCE_TOKEN"
  }]
}
```

校验配置并启动服务：

```bash
python3 -m usage_dashboard --config config.json --check
python3 -m usage_dashboard --config config.json
```

三个独立提供商用量池的配置可参考[多提供商示例](./examples/config.multi-provider.example.json)：

```bash
python3 -m usage_dashboard --config examples/config.multi-provider.example.json --check
```

其中的 HTTPS URL 是 OpenAI 兼容接口、Anthropic 与 Google Cloud Vertex AI 用量汇总导出端点的占位示例，不是供应商原生 API。请替换为实现[聚合数据源协议](./docs/data-contract.md)的自有导出服务，并通过指定环境变量注入导出服务令牌；不要将供应商 API Key 当作导出服务令牌。`--check` 不发起网络请求或创建 SQLite 文件，也不验证端点连通性、鉴权或返回数据。各数据源必须对应互不重叠的用量与配额池，避免重复统计。

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `host`, `port` | `127.0.0.1`, `8900` | 监听地址与端口（可通过命令行 `--host` / `--port` 覆盖）。 |
| `timezone` | `UTC` | 界面时钟显示时区；各数据源自身的配额窗口保持独立。 |
| `poll_interval` | `30` | 每轮采集完成后的轮询间隔秒数。 |
| `stale_after` | `120` | 数据观测值的最大有效秒数，超时则标记为过期（Stale）。 |
| `timeout` | `5` | 单个数据源网络请求超时时间（秒）。 |
| `history_days` | `30` | SQLite 每日历史快照保留天数（`1–365` 天）。 |
| `data_dir` | `data` | 本地 SQLite 存储目录（请勿纳入 Git 版本控制）。 |
| `site.language` | `en` | 初始界面语言：`en` 或 `zh-CN`（访客可在前端自由切换）。 |
| `sources[].enabled` | `true` | 是否启用该数据源的采集与前端展示（最多支持 32 个独立数据源）。 |

## Docker 部署

```bash
docker compose up --build -d
```

默认 Compose 配置以非特权用户 `UID 10001`、只读根文件系统及资源限制在 `127.0.0.1:8900` 启动演示实例。生产环境可通过 `compose.local.yaml` 挂载私有配置并注入环境变量：

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

## 安全与部署建议

本看板为只读聚合视图，不含内置登录鉴权。在非本机回环网络部署时，请将其置于带身份验证的 HTTPS 反向代理之后。系统仅存储白名单内的聚合指标，自动丢弃上游账户明细、请求头及原始错误正文。

## 开发与测试

```bash
python3 -m unittest discover -s tests -v
python3 -m usage_dashboard --config examples/config.demo.json --check
```

## 开源许可

MIT License. 由 [VectorDuct](https://vectorduct.com) 维护。

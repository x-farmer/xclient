# xclient

`xclient` is a minimal Python CLI that uses the official OpenAI Python SDK to
exercise the x-farmer API Gateway as an OpenAI-compatible endpoint.

It is intentionally thin:

- It does not send custom raw HTTP requests.
- It does not validate raw response bodies.
- It does not reimplement OpenAI protocol handling.
- If the OpenAI SDK call succeeds, the client reports success by printing the
  assistant output.
- If the OpenAI SDK call fails, the client prints the SDK exception clearly.

## Install For Local Development

```shell
uv sync
```

Run the CLI through the project environment:

```shell
uv run xclient --help
```

If you activate `.venv` manually before installing the package, run from source
with `PYTHONPATH=src`:

```shell
source .venv/bin/activate
PYTHONPATH=src python -m xclient --help
PYTHONPATH=src python -m xclient chat --help
```

`tests/test_cli.py` is a pytest test module, not the CLI entry point.

## Local Gateway

Use the API Gateway OpenAI-compatible base URL, including the `/v1` prefix:

```shell
http://localhost:8080/v1
```

Public OpenAI-compatible endpoints require an x-farmer API Token as the OpenAI
SDK `api_key`.

## Non-Streaming Chat

```shell
uv run xclient chat \
  --base-url http://localhost:8080/v1 \
  --api-key xfk_xxx \
  --model demo/llama3-2-latest \
  --message "hello"
```

## Streaming Chat

```shell
uv run xclient chat \
  --base-url http://localhost:8080/v1 \
  --api-key xfk_xxx \
  --model demo/llama3-2-latest \
  --message "hello" \
  --stream
```

## Using Environment Variables

`xclient chat` reads these environment variables when the matching CLI flag is
omitted:

- `XF_BASE_URL`
- `XF_API_KEY`
- `XF_MODEL`

```shell
export XF_BASE_URL=http://localhost:8080/v1
export XF_API_KEY=xfk_xxx
export XF_MODEL=demo/llama3-2-latest

uv run xclient chat --message "hello"
```

CLI flags take precedence over environment variables:

```shell
uv run xclient chat \
  --model demo/llama3-2-latest \
  --message "hello"
```

## Debug Output

Use `--debug` to print only non-secret selected settings and SDK exception
details. Debug output never prints the API key.

```shell
uv run xclient chat \
  --base-url http://localhost:8080/v1 \
  --api-key xfk_xxx \
  --model demo/llama3-2-latest \
  --message "hello" \
  --debug
```

## Tracing

`xclient` can emit one OpenTelemetry span per chat request and export it over
OTLP to a collector. Tracing is **disabled by default** — a plain invocation
never tries to reach a collector. Opt in with `XF_OBS_TRACING_ENABLED=true`.
All tracing knobs are environment variables (the CLI owns no config file):

| Variable | Purpose | Default |
| --- | --- | --- |
| `XF_OBS_TRACING_ENABLED` | Turn tracing on/off. | `false` |
| `XF_OBS_TRACING_ENDPOINT` | OTLP endpoint (`host:port` for gRPC, URL/host for HTTP). | `localhost:4317` |
| `XF_OBS_TRACING_PROTOCOL` | `grpc` or `http`. | `grpc` |
| `XF_OBS_TRACING_INSECURE` | Skip TLS (dev only). | `true` |
| `XF_OBS_TRACING_AUTH_TOKEN` | OTLP ingest bearer token; empty sends no auth header. | (empty) |
| `XF_OBS_TRACING_SAMPLE_RATIO` | Head-based sampling ratio `0.0`–`1.0`. | `1.0` |
| `XF_OBS_TRACING_EXPORTER` | `otlp` or `none` (`none` also disables tracing). | `otlp` |
| `XF_OBS_SERVICE_NAME` / `XF_OBS_ENVIRONMENT` | Resource attributes on the spans. | `x-farmer-client` / `development` |

The API key and the ingest token are treated as secrets and never appear in
spans, logs, or `--debug` output.

### Local Development (uv)

Point xclient at the local dev observability stack (OpenTelemetry Collector +
Jaeger). Run with host networking it accepts OTLP/gRPC on `127.0.0.1:4317`:

```shell
export XF_OBS_TRACING_ENABLED=true
export XF_OBS_TRACING_ENDPOINT=127.0.0.1:4317
export XF_OBS_TRACING_PROTOCOL=grpc
export XF_OBS_TRACING_INSECURE=true

uv run xclient chat \
  --base-url http://localhost:8080/v1 \
  --api-key xfk_xxx \
  --model demo/llama3-2-latest \
  --message "hello"
```

Then open the traces in the dev Jaeger UI at `http://localhost:16686/`.

### Docker Container (Production Tracing System)

The production collector is reached over OTLP/HTTP on 443 at `otel.xfarms.io:443`
(real TLS at the Cloudflare/nginx edge) and requires the ingest bearer token.
Pass the tracing settings to the container as environment variables; keep the
token in your shell/secret store and never commit it:

```shell
docker run --rm \
  -e XF_API_KEY=xfk_xxx \
  -e XF_OBS_ENVIRONMENT=production \
  -e XF_OBS_TRACING_ENABLED=true \
  -e XF_OBS_TRACING_ENDPOINT=otel.xfarms.io:443 \
  -e XF_OBS_TRACING_PROTOCOL=http \
  -e XF_OBS_TRACING_INSECURE=false \
  -e XF_OBS_TRACING_AUTH_TOKEN="$XF_OTLP_INGEST_TOKEN" \
  ghcr.io/x-farmer/xclient:<tag> \
  chat \
    --base-url https://<api-gateway-host>/v1 \
    --model demo/llama3-2-latest \
    --message "hello"
```

`XF_OBS_TRACING_AUTH_TOKEN` must match the production collector's
`XF_OTLP_INGEST_TOKEN`. Spans land in the prod Jaeger UI fronted by nginx at
`https://xfarms.io:5053/` (HTTP Basic Auth).

## Tests

```shell
uv run pytest
```

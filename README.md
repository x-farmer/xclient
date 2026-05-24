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
  --model bill-qwen3:latest \
  --message "hello"
```

## Streaming Chat

```shell
uv run xclient chat \
  --base-url http://localhost:8080/v1 \
  --api-key xfk_xxx \
  --model bill-qwen3:latest \
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
export XF_MODEL=bill-qwen3:latest

uv run xclient chat --message "hello"
```

CLI flags take precedence over environment variables:

```shell
uv run xclient chat \
  --model bill-qwen3:latest \
  --message "hello"
```

## Debug Output

Use `--debug` to print only non-secret selected settings and SDK exception
details. Debug output never prints the API key.

```shell
uv run xclient chat \
  --base-url http://localhost:8080/v1 \
  --api-key xfk_xxx \
  --model bill-qwen3:latest \
  --message "hello" \
  --debug
```

## Tests

```shell
uv run pytest
```

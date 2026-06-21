FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

WORKDIR /app
COPY pyproject.toml README.md ./
COPY underwriting_core ./underwriting_core
COPY underwriting_app ./underwriting_app
COPY underwriting_mcp ./underwriting_mcp
COPY rulesets ./rulesets
COPY samples ./samples

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[server,aws]" \
    && useradd --create-home --uid 10001 appuser

USER appuser
EXPOSE 8000
CMD ["python", "-m", "underwriting_mcp"]

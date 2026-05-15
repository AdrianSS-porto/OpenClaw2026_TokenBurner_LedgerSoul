FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/
COPY src /app/src
COPY soul.md agent.md README.md architecture.md lifecycle.md tools.md guardrails.md evals.md demo.md deploy.md /app/
COPY examples /app/examples
COPY scripts /app/scripts

RUN pip install --upgrade pip && pip install -e ".[dev]"
RUN chmod +x /app/scripts/*.sh

EXPOSE 8000

CMD ["uvicorn", "ledgersoul.server.api:app", "--host", "0.0.0.0", "--port", "8000"]

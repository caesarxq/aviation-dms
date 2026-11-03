FROM python:3.11-slim@sha256:db20d8506e2f15b6db39b40b6015ca46bae855dec6dd326d462cfe79ae972893

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /app/data && chown 10001:10001 /app/data

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
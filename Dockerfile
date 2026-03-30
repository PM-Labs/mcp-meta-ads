FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --upgrade pip && pip install uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt
COPY . .

ENV PORT=8080
ENV BACKEND_PORT=8081
EXPOSE 8080

RUN chmod +x start.sh
CMD ["./start.sh"]

FROM python:3.11-slim

WORKDIR /app

# Instala ferramentas básicas essenciais de compilação C para o Python leve
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Garante a pasta interna para o armazenamento temporário
RUN mkdir -p uploads

# Comunica a porta padrão HTTP interna do container para o roteador Easypanel
EXPOSE 80

# Inicia o servidor HTTP nativo
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]

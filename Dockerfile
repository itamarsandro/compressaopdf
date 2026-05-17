FROM python:3.11-slim

WORKDIR /app

# Instala as dependências de sistema essenciais e o motor gráfico Ghostscript
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Garante a pasta interna para o armazenamento temporário das transações
RUN mkdir -p uploads

# Comunica a porta 81 interna para o roteador Easypanel
EXPOSE 81

# Inicia o servidor HTTP nativo na porta 81
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "81"]

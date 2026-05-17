from celery import Celery
from pypdf import PdfReader, PdfWriter
import os

# Configura a conexão apontando para o serviço redis-pdf na sala 1
REDIS_URL = os.getenv("REDIS_URL", "redis://redis-pdf:6379/1")

# Nome da fila isolado
app_celery = Celery("tasks_pdf", broker=REDIS_URL, backend=REDIS_URL)

app_celery.conf.worker_concurrency = 1

@app_celery.task
def processar_pdf(caminho_original):
    try:
        if not os.path.exists(caminho_original):
            return {"erro": "Arquivo original não localizado pelo worker.", "sucesso": False}

        caminho_saida = caminho_original.rsplit(".", 1)[0] + f"_compactado.pdf"

        # Abre o documento PDF original recebido
        reader = PdfReader(caminho_original)
        writer = PdfWriter()

        # PASSO 1: Copia todas as páginas do Reader para o Writer PRIMEIRO
        for page in reader.pages:
            writer.add_page(page)

        # PASSO 2: Transfere metadados originais
        if reader.metadata:
            writer.add_metadata(reader.metadata)

        # PASSO 3: COMPACTAÇÃO CORRIGIDA - Compacta as páginas que JÁ ESTÃO no Writer
        for page in writer.pages:
            page.compress_content_streams()

        # Escreve o novo arquivo PDF compactado
        with open(caminho_saida, "wb") as f:
            writer.write(f)

        # Remove o PDF original enviado para não lotar o servidor
        if os.path.exists(caminho_original):
            os.remove(caminho_original)

        return {"url_download": f"/uploads/{os.path.basename(caminho_saida)}", "sucesso": True}
    except Exception as e:
        return {"erro": str(e), "sucesso": False}

from celery import Celery
from pypdf import PdfReader, PdfWriter
import os

# Configura a conexão apontando para o NOVO serviço redis-pdf na sala 1
REDIS_URL = os.getenv("REDIS_URL", "redis://redis-pdf:6379/1")

# Nome da fila isolado para não cruzar com as imagens
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

        # Varre as páginas compactando os streams
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)

        # Transfere metadados originais
        if reader.metadata:
            writer.add_metadata(reader.metadata)

        # Escreve o novo arquivo PDF compactado
        with open(caminho_saida, "wb") as f:
            writer.write(f)

        # Remove o PDF original enviado
        if os.path.exists(caminho_original):
            os.remove(caminho_original)

        return {"url_download": f"/uploads/{os.path.basename(caminho_saida)}", "sucesso": True}
    except Exception as e:
        return {"erro": str(e), "sucesso": False}

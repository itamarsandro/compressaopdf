from celery import Celery
from pypdf import PdfReader, PdfWriter
import os

# Configura a conexão de transporte com o serviço Redis do ecossistema isolado
REDIS_URL = os.getenv("REDIS_URL", "redis://fila-redis:6379/0")
app_celery = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

# Força a concorrência em 1 para total estabilidade e proteção de memória RAM do host
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

        # Varre as páginas compactando os streams internos de texto, imagens e vetores estruturais
        for page in reader.pages:
            page.compress_content_streams()  # Algoritmo interno de compressão de streams sem perda estrutural
            writer.add_page(page)

        # Transfere metadados originais se existirem para manter a integridade do documento
        if reader.metadata:
            writer.add_metadata(reader.metadata)

        # Escreve o novo arquivo PDF compactado no volume compartilhado
        with open(caminho_saida, "wb") as f:
            writer.write(f)

        # Remove IMEDIATAMENTE o PDF original enviado para liberar espaço de armazenamento
        if os.path.exists(caminho_original):
            os.remove(caminho_original)

        return {"url_download": f"/uploads/{os.path.basename(caminho_saida)}", "sucesso": True}
    except Exception as e:
        return {"erro": str(e), "sucesso": False}

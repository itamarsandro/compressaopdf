from celery import Celery
import os
import subprocess

# Configura a conexão apontando para o serviço redis-pdf na sala 1
REDIS_URL = os.getenv("REDIS_URL", "redis://redis-pdf:6379/1")

# Nome da fila isolado
app_celery = Celery("tasks_pdf", broker=REDIS_URL, backend=REDIS_URL)

app_celery.conf.worker_concurrency = 1

@app_celery.task
def processar_pdf(caminho_original, nivel_compressao="ebook"):
    try:
        if not os.path.exists(caminho_original):
            return {"erro": "Arquivo original não localizado pelo worker.", "sucesso": False}

        caminho_saida = caminho_original.rsplit(".", 1)[0] + f"_compactado.pdf"

        # Mapeamento seguro dos parâmetros oficiais do Ghostscript baseado na escolha do usuário
        # /screen = 72 dpi (alta compressão)
        # /ebook  = 150 dpi (média compressão)
        # /printer = 300 dpi (baixa compressão)
        config_presets = {
            "screen": "/screen",
            "ebook": "/ebook",
            "printer": "/printer"
        }
        
        preset_gs = config_presets.get(nivel_compressao, "/ebook")

        # Executa a chamada binária nativa do Ghostscript para re-compressão profunda de imagens e fontes
        comando_gs = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS={preset_gs}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={caminho_saida}",
            caminho_original
        ]

        # Executa o subprocesso no Linux do Container
        resultado_proc = subprocess.run(comando_gs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if resultado_proc.returncode != 0:
            return {"erro": f"Falha no binário do Ghostscript: {resultado_proc.stderr}", "sucesso": False}

        # Remove o PDF original enviado para poupar o armazenamento do servidor
        if os.path.exists(caminho_original):
            os.remove(caminho_original)

        # Garante se o arquivo final realmente foi criado com sucesso antes de dar o retorno
        if not os.path.exists(caminho_saida):
            return {"erro": "O Ghostscript encerrou sem gerar o arquivo de saída.", "sucesso": False}

        return {"url_download": f"/uploads/{os.path.basename(caminho_saida)}", "sucesso": True}
    except Exception as e:
        return {"erro": str(e), "sucesso": False}

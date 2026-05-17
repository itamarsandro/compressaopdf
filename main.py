from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from worker import processar_pdf
from celery.result import AsyncResult
import uuid
import os

app = FastAPI(title="Fábrica de PDFs")

# Pasta para salvar os arquivos temporários e compactados
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Permitir o mapeamento de arquivos estáticos da pasta uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

def deletar_arquivo_servidor(caminho_arquivo: str):
    """Função executada em segundo plano para deletar o arquivo após o download."""
    try:
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
            print(f"Arquivo {caminho_arquivo} removido com sucesso do servidor.")
    except Exception as e:
        print(f"Erro ao remover arquivo em segundo plano: {str(e)}")

@app.get("/download/{filename}")
async def forcar_download_e_limpar(filename: str, background_tasks: BackgroundTasks):
    """Endpoint que força o download do PDF e agenda a sua destruição automática."""
    nome_seguro = os.path.basename(filename)
    caminho_completo = os.path.join(UPLOAD_DIR, nome_seguro)
    
    if not os.path.exists(caminho_completo):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou já deletado.")
    
    # Agenda a exclusão do arquivo para rodar IMEDIATAMENTE após a resposta ser entregue ao cliente
    background_tasks.add_task(deletar_arquivo_servidor, caminho_completo)
    
    # Retorna o arquivo forçando o download nativo do navegador (Content-Disposition: attachment)
    return FileResponse(
        path=caminho_completo,
        filename=nome_seguro,
        media_type="application/pdf"
    )

@app.get("/", response_class=HTMLResponse)
async def pagina_inicial():
    html_content = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fábrica de PDFs - Compactador Automático</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-slate-900 text-slate-100 font-sans min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-slate-800 p-8 rounded-2xl shadow-2xl border border-slate-700">
            <h1 class="text-3xl font-bold text-center mb-2 bg-gradient-to-r from-red-400 to-orange-500 bg-clip-text text-transparent">Fábrica de PDFs</h1>
            <p class="text-slate-400 text-center text-sm mb-8">Reduza o tamanho dos seus arquivos PDF instantaneamente usando filas assíncronas.</p>
            
            <form id="uploadForm" class="space-y-6">
                <div>
                    <label class="block text-sm font-medium mb-2">Selecione o Arquivo PDF</label>
                    <input type="file" id="arquivo" name="arquivo" accept=".pdf" required class="w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-red-500 file:text-slate-900 hover:file:bg-red-400 cursor-pointer bg-slate-900 p-3 rounded-xl border border-slate-700">
                </div>
                
                <button type="submit" class="w-full bg-gradient-to-r from-red-500 to-orange-600 text-slate-900 font-bold py-3 px-4 rounded-xl hover:from-red-400 hover:to-orange-500 transition duration-200 shadow-lg cursor-pointer">
                    Compactar PDF
                </button>
            </form>
            
            <div id="statusContainer" class="hidden mt-8 p-4 bg-slate-900 rounded-xl border border-slate-700 text-center space-y-4">
                <div id="iconContainer" class="flex justify-center items-center">
                    <div id="spinner" class="animate-spin rounded-full h-10 w-10 border-4 border-red-500 border-t-transparent"></div>
                    
                    <div id="successCheck" class="hidden text-emerald-400 bg-emerald-500/10 p-2 rounded-full">
                        <svg class="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                    </div>
                </div>
                
                <p id="statusTexto" class="text-sm font-medium text-red-400">Enviando PDF...</p>
                
                <div id="downloadContainer" class="hidden">
                    <a id="downloadLink" href="#" class="inline-block w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl transition duration-200 shadow-lg text-center">
                        Baixar PDF Compactado
                    </a>
                </div>
            </div>
        </div>

        <script>
            let checagemIntervalo = null;

            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const form = document.getElementById('uploadForm');
                const statusContainer = document.getElementById('statusContainer');
                const statusTexto = document.getElementById('statusTexto');
                const spinner = document.getElementById('spinner');
                const successCheck = document.getElementById('successCheck');
                const downloadContainer = document.getElementById('downloadContainer');
                const downloadLink = document.getElementById('downloadLink');
                
                // Inicializa a UI para estado de progresso
                statusContainer.classList.remove('hidden');
                downloadContainer.classList.add('hidden');
                successCheck.classList.add('hidden');
                spinner.classList.remove('hidden');
                statusTexto.innerText = "Enviando arquivo PDF para o servidor...";
                
                const formData = new FormData();
                formData.append('arquivo', document.getElementById('arquivo').files[0]);
                
                try {
                    // 1. Envia o arquivo original para o endpoint FastAPI
                    const resposta = await fetch('/upload', { method: 'POST', body: formData });
                    const dados = await resposta.json();
                    
                    if (!dados.id_tarefa) {
                        throw new Error("Falha ao injetar tarefa na fila de processamento.");
                    }
                    
                    const idTarefa = dados.id_tarefa;
                    statusTexto.innerText = "PDF recebido com sucesso! Compactando streams de dados...";
                    
                    // 2. Inicia o monitoramento periódico da fila do Celery Worker
                    if (checagemIntervalo) clearInterval(checagemIntervalo);
                    
                    checagemIntervalo = setInterval(async () => {
                        const checarStatus = await fetch(`/status/${idTarefa}`);
                        const statusDados = await checarStatus.json();
                        
                        if (statusDados.status === "Concluído") {
                            clearInterval(checagemIntervalo);
                            
                            if (statusDados.resultado.sucesso) {
                                // Altera o Spinner pelo ícone estável de Checkmark de Conclusão
                                spinner.classList.add('hidden');
                                successCheck.classList.remove('hidden');
                                statusTexto.innerText = "Sucesso! O tamanho do PDF foi reduzido.";
                                
                                // Extrai o nome do arquivo para direcionar para a rota de download forçado
                                const nomeArquivo = statusDados.resultado.url_download.split('/').pop();
                                downloadLink.href = `/download/${nomeArquivo}`;
                                downloadContainer.classList.remove('hidden');
                            } else {
                                spinner.classList.add('hidden');
                                statusTexto.innerText = "Erro interno na compactação: " + statusDados.resultado.erro;
                            }
                        }
                    }, 1200); // Executa ciclos de verificação rápidos a cada 1.2 segundos
                    
                } catch (erro) {
                    spinner.classList.add('hidden');
                    successCheck.classList.add('hidden');
                    statusTexto.innerText = "Erro operacional: " + erro.message;
                }
            });

            // Gerencia o clique no botão de download para limpar o estado de tela após a entrega do arquivo
            document.getElementById('downloadLink').addEventListener('click', () => {
                const statusTexto = document.getElementById('statusTexto');
                const downloadContainer = document.getElementById('downloadContainer');
                const successCheck = document.getElementById('successCheck');
                
                setTimeout(() => {
                    statusTexto.innerText = "Concluído! O arquivo foi baixado e destruído do servidor com segurança.";
                    downloadContainer.classList.add('hidden');
                    successCheck.classList.add('hidden');
                }, 800);
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.post("/upload")
async def upload_pdf(arquivo: UploadFile = File(...)):
    # Validação rigorosa de extensão em nível de API
    ext = arquivo.filename.split(".")[-1].lower()
    if ext != "pdf":
        raise HTTPException(status_code=400, detail="Formato inválido. Apenas arquivos .pdf são suportados.")
        
    id_unico = str(uuid.uuid4())
    caminho_entrada = os.path.join(UPLOAD_DIR, f"{id_unico}.pdf")
    
    # Salva o binário recebido no volume persistente compartilhado
    with open(caminho_entrada, "wb") as buffer:
        buffer.write(await arquivo.read())
    
    # Dispara a tarefa assíncrona na fila do Celery
    tarefa = processar_pdf.delay(caminho_entrada)
    
    return {"id_tarefa": tarefa.id, "status": "Processando"}

@app.get("/status/{tarefa_id}")
async def ver_status(tarefa_id: str):
    resultado = AsyncResult(tarefa_id)
    if resultado.ready():
        return {"status": "Concluído", "resultado": resultado.result}
    return {"status": "Processando..."}

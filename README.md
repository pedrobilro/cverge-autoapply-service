# Auto-Apply Playwright Service

Microservice Python com Playwright para preencher formulários de candidatura automaticamente.

## Deploy no Railway

### 1. Preparar GitHub
1. Cria um novo repositório no GitHub (ex: `autoapply-service`)
2. Faz upload dos ficheiros desta pasta:
   - `main.py`
   - `requirements.txt`
   - `railway.json`
   - `README.md`

### 2. Deploy no Railway
1. Vai a [railway.app](https://railway.app)
2. Login com GitHub
3. Clica "New Project" → "Deploy from GitHub repo"
4. Seleciona o repositório `autoapply-service`
5. Railway vai detetar automaticamente o Python e fazer deploy

### 3. Obter URL
1. Depois do deploy, vai à tab "Settings"
2. Clica "Generate Domain"
3. Copia o URL (ex: `https://autoapply-service-production-xxxx.up.railway.app`)

### 4. Configurar no Supabase
1. Adiciona o URL como secret `PYTHON_SERVICE_URL` no teu projeto Supabase
2. A Edge Function já vai estar configurada para usar este URL

## Testar Localmente

```bash
# Instalar dependências
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Correr servidor
uvicorn main:app --reload --port 8000

# Testar
curl -X POST http://localhost:8000/apply \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://jobs.lever.co/example/job",
    "full_name": "Pedro Bilro",
    "email": "pedro@example.com",
    "phone": "+351 900 000 000"
  }'
```

## Endpoints

- `GET /` - Health check
- `GET /health` - Status do serviço
- `POST /apply` - Executar candidatura automática

### POST /apply

**Request:**
```json
{
  "job_url": "https://jobs.lever.co/company/job-id",
  "full_name": "Nome Completo",
  "email": "email@example.com",
  "phone": "+351 900 000 000"
}
```

**Response:**
```json
{
  "ok": true,
  "job_url": "https://jobs.lever.co/company/job-id",
  "elapsed_s": 12.5,
  "screenshot": "base64_encoded_screenshot...",
  "log": [
    "[10:30:45] Iniciando candidatura...",
    "[10:30:47] ✓ Preencheu email...",
    "..."
  ]
}
```

## Custos Railway

- **Free tier**: $5 de crédito/mês
- **Custo por execução**: ~$0.01-0.02
- **Estimativa**: 200-500 candidaturas/mês no free tier

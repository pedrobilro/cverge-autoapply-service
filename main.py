from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
import json
import time
import base64
from typing import Dict, List

app = FastAPI()

# CORS para permitir chamadas da Edge Function
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Hints de sucesso
SUCCESS_HINTS = [
    "thank you", "thanks for applying", "application received",
    "we'll be in touch", "obrigado", "candidatura recebida",
    "application submitted", "successfully applied"
]

# Seletores CSS comuns para Lever
SELECTORS = {
    "first_name": "input[name='firstName'], input[aria-label*='first' i], input[placeholder*='first' i]",
    "last_name": "input[name='lastName'], input[aria-label*='last' i], input[placeholder*='last' i]",
    "full_name": "input[name='name'], input[aria-label*='name' i], input[placeholder*='name' i]",
    "email": "input[type='email'], input[name='email'], input[aria-label*='email' i]",
    "phone": "input[type='tel'], input[name='phone'], input[aria-label*='phone' i]",
    "resume": "input[type='file'][name*='resume'], input[type='file'][aria-label*='resume' i], input[type='file'][accept*='pdf']",
    "submit": "button:has-text('Submit'), button:has-text('Apply'), button:has-text('Enviar'), button[type='submit']",
    "open_apply": "a:has-text('Apply'), button:has-text('Apply')"
}

class ApplyRequest(BaseModel):
    job_url: str
    full_name: str
    email: str
    phone: str = ""

def log_message(messages: List[str], msg: str):
    """Adiciona mensagem ao log"""
    timestamp = time.strftime('%H:%M:%S')
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    messages.append(full_msg)

def fill_field(page, selector: str, value: str, messages: List[str]) -> bool:
    """Tenta preencher um campo se existir"""
    if not value:
        return False
    try:
        loc = page.locator(selector).first
        if loc.is_visible(timeout=3000):
            loc.fill(value)
            log_message(messages, f"✓ Preencheu: {selector[:50]} = '{value[:40]}'")
            return True
    except Exception as e:
        log_message(messages, f"✗ Falha ao preencher {selector[:30]}: {e}")
    return False

def try_open_apply_modal(page, messages: List[str]):
    """Tenta clicar no botão Apply se existir modal"""
    try:
        btn = page.locator(SELECTORS["open_apply"]).first
        if btn.is_visible(timeout=3000):
            btn.click()
            log_message(messages, "✓ Clicou em 'Apply' para abrir formulário")
            page.wait_for_timeout(1000)
    except Exception:
        pass

def apply_to_job(user_data: Dict[str, str]) -> Dict:
    """Executa a candidatura automática"""
    messages = []
    job_url = user_data.get("job_url", "")
    full_name = user_data.get("full_name", "")
    email = user_data.get("email", "")
    phone = user_data.get("phone", "")
    
    log_message(messages, f"Iniciando candidatura para: {job_url}")
    
    t0 = time.time()
    screenshot_b64 = None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(15000)
            
            # 1. Abrir página da vaga
            log_message(messages, "Abrindo página da vaga...")
            page.goto(job_url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            
            # 2. Tentar abrir modal de candidatura (se existir)
            try_open_apply_modal(page, messages)
            
            # 3. Preencher campos
            log_message(messages, "Preenchendo formulário...")
            
            # Nome completo (tenta full_name primeiro)
            filled_name = fill_field(page, SELECTORS["full_name"], full_name, messages)
            
            if not filled_name and full_name:
                # Dividir em primeiro/último nome
                parts = full_name.split(maxsplit=1)
                first = parts[0] if len(parts) > 0 else ""
                last = parts[1] if len(parts) > 1 else ""
                fill_field(page, SELECTORS["first_name"], first, messages)
                fill_field(page, SELECTORS["last_name"], last, messages)
            
            # Email e telefone
            fill_field(page, SELECTORS["email"], email, messages)
            fill_field(page, SELECTORS["phone"], phone, messages)
            
            # 4. Submeter
            log_message(messages, "Tentando submeter...")
            try:
                submit_btn = page.locator(SELECTORS["submit"]).first
                submit_btn.click(timeout=5000)
                log_message(messages, "✓ Clicou no botão Submit")
            except PwTimeout:
                log_message(messages, "✗ Botão Submit não encontrado")
            except Exception as e:
                log_message(messages, f"✗ Erro ao clicar Submit: {e}")
            
            # 5. Esperar resposta
            page.wait_for_timeout(3000)
            
            # 6. Validar sucesso
            html = page.content().lower()
            success_detected = any(hint in html for hint in SUCCESS_HINTS)
            
            # 7. Screenshot final
            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            log_message(messages, "✓ Screenshot capturado")
            
            # 8. Verificar se botão Submit desapareceu (bom sinal)
            try:
                btn = page.locator(SELECTORS["submit"]).first
                btn_disabled = btn.is_disabled() if btn.count() > 0 else True
            except Exception:
                btn_disabled = True
            
            ok = success_detected or btn_disabled
            
            log_message(messages, f"{'✓ Sucesso!' if ok else '⚠ Submissão não confirmada'}")
            
            browser.close()
            
    except Exception as e:
        log_message(messages, f"✗ ERRO CRÍTICO: {e}")
        ok = False
    
    elapsed = round(time.time() - t0, 2)
    
    return {
        "ok": ok,
        "job_url": job_url,
        "elapsed_s": elapsed,
        "screenshot": screenshot_b64,
        "log": messages
    }

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "auto-apply-playwright", "version": "1.0"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/apply")
async def auto_apply(request: ApplyRequest):
    """
    Endpoint que recebe dados e executa Playwright
    """
    try:
        user_data = {
            "job_url": request.job_url,
            "full_name": request.full_name,
            "email": request.email,
            "phone": request.phone,
        }
        
        # Chama o script Playwright
        result = apply_to_job(user_data)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

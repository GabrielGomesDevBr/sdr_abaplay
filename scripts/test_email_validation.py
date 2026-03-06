#!/usr/bin/env python3
"""
Testes isolados de validação de e-mail — sem dependência de banco de dados.
"""
import sys, os, ast, time
from pathlib import Path

ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, ROOT)

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name} — {detail}")
        failed += 1

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 1: Syntax AST de todos os arquivos")
print("="*60)

for fname in ['email_validator.py', 'lead_processor.py', 'main.py', 'ui_components.py']:
    fpath = os.path.join(ROOT, 'app', fname)
    try:
        with open(fpath) as f:
            ast.parse(f.read())
        test(f"Syntax OK: {fname}", True)
    except SyntaxError as e:
        test(f"Syntax OK: {fname}", False, str(e))

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 2: Imports no main.py via AST")
print("="*60)

with open(os.path.join(ROOT, 'app', 'main.py')) as f:
    tree = ast.parse(f.read())

found_validator = False
found_get_lead_email = False
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        if node.module == 'app.email_validator':
            found_validator = True
        if node.module == 'app.lead_processor':
            for alias in node.names:
                if alias.name == 'get_lead_email':
                    found_get_lead_email = True

test("main.py importa app.email_validator", found_validator)
test("main.py importa get_lead_email", found_get_lead_email)

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 3: Imports no lead_processor.py via AST")
print("="*60)

with open(os.path.join(ROOT, 'app', 'lead_processor.py')) as f:
    tree = ast.parse(f.read())

found = False
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        if node.module == 'app.email_validator':
            found = True

test("lead_processor.py importa app.email_validator", found)

# Verifica se validate_email_smtp é chamado dentro de process_leads
with open(os.path.join(ROOT, 'app', 'lead_processor.py')) as f:
    code = f.read()

test("process_leads() chama validate_email_smtp",
     'validate_email_smtp(email)' in code)
test("process_leads() salva smtp_valid no lead",
     "lead['smtp_valid']" in code)
test("process_leads() salva smtp_status no lead",
     "lead['smtp_status']" in code)
test("process_leads() salva smtp_message no lead",
     "lead['smtp_message']" in code)

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 4: LLM path no main.py contém validação SMTP")
print("="*60)

with open(os.path.join(ROOT, 'app', 'main.py')) as f:
    main_code = f.read()

test("main.py contém 'validate_email_smtp' no corpo",
     'validate_email_smtp' in main_code)
test("main.py contém spinner de verificação SMTP",
     'Verificando existência dos e-mails via SMTP' in main_code)
test("main.py contém warning de SMTP rejections",
     'smtp_rejections' in main_code)

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 5: UI badges no ui_components.py")
print("="*60)

with open(os.path.join(ROOT, 'app', 'ui_components.py')) as f:
    ui_code = f.read()

test("ui_components.py lê smtp_status do lead",
     "lead.get('smtp_status'" in ui_code)
test("Badge 'valid' presente (✓ SMTP)",
     '✓ SMTP' in ui_code)
test("Badge 'catch_all' presente (⚠ CATCH-ALL)",
     '⚠ CATCH-ALL' in ui_code)
test("Badge 'unknown' presente (? N/V)",
     '? N/V' in ui_code)

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 6: email_validator.py — testes unitários diretos")
print("="*60)

# Mock do logger para evitar dependência
import types
mock_logger = types.ModuleType('app.logger')
mock_logger.log_info = lambda *a, **k: None
mock_logger.log_warning = lambda *a, **k: None
mock_logger.log_error = lambda *a, **k: None
sys.modules['app.logger'] = mock_logger

# Agora importa normalmente
from app.email_validator import (
    validate_email_smtp,
    is_disposable_email,
    is_catch_all_domain,
    _get_mx_host,
    DISPOSABLE_DOMAINS,
    CATCH_ALL_DOMAINS,
)

# Testes de disposable
test("mailinator é descartável", is_disposable_email("x@mailinator.com"))
test("guerrillamail é descartável", is_disposable_email("x@guerrillamail.com"))
test("yopmail é descartável", is_disposable_email("x@yopmail.com"))
test("gmail NÃO é descartável", not is_disposable_email("x@gmail.com"))
test("clinica.com.br NÃO é descartável", not is_disposable_email("x@clinica.com.br"))
test("vazio → False", not is_disposable_email(""))
test("sem @ → False", not is_disposable_email("invalido"))

# Testes de catch-all
test("gmail é catch-all", is_catch_all_domain("x@gmail.com"))
test("outlook é catch-all", is_catch_all_domain("x@outlook.com"))
test("hotmail é catch-all", is_catch_all_domain("x@hotmail.com"))
test("yahoo é catch-all", is_catch_all_domain("x@yahoo.com"))
test("protonmail é catch-all", is_catch_all_domain("x@protonmail.com"))
test("clinica.com.br NÃO é catch-all", not is_catch_all_domain("x@clinica.com.br"))

# Testes de validate_email_smtp com respostas previsíveis
v, s, m = validate_email_smtp("")
test("E-mail vazio → invalid", s == 'invalid', f"got {s}")

v, s, m = validate_email_smtp("semarroba")
test("Sem @ → invalid", s == 'invalid', f"got {s}")

v, s, m = validate_email_smtp("x@mailinator.com")
test("Descartável → disposable", s == 'disposable', f"got {s}")
test("Descartável → valid=False", v == False, f"got {v}")

v, s, m = validate_email_smtp("user@gmail.com")
test("Gmail → catch_all", s == 'catch_all', f"got {s}")
test("Gmail → valid=True", v == True, f"got {v}")

v, s, m = validate_email_smtp("user@outlook.com")
test("Outlook → catch_all", s == 'catch_all', f"got {s}")

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 7: SMTP real com domínio inexistente")
print("="*60)

print("  [Conectando SMTP para domínio inexistente...]")
start = time.time()
v, s, m = validate_email_smtp("test@dominio-falso-xyz-9999.com.br")
elapsed = time.time() - start
test(f"Domínio inexistente → status={s} (em {elapsed:.1f}s)",
     s in ('unknown', 'invalid'), f"got {s}: {m}")
print(f"    → {m}")

# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TESTE 8: SMTP real com domínio existente")
print("="*60)

print("  [Resolvendo MX de google.com...]")
mx = _get_mx_host("google.com")
test("MX de google.com resolve", mx != "", "DNS unavailable")
if mx:
    print(f"    → MX: {mx}")

print("  [Verificando e-mail inexistente em domínio real...]")
start = time.time()
v, s, m = validate_email_smtp("usuario-que-nao-existe-xyz123@verificaremailtest.com")
elapsed = time.time() - start
print(f"    → valid={v}, status={s}, msg={m} (em {elapsed:.1f}s)")
test(f"Resposta para e-mail em domínio real",
     s in ('valid', 'invalid', 'unknown', 'catch_all'), f"got unexpected: {s}")


# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print(f"RESULTADO FINAL: {passed} passed, {failed} failed")
print("="*60 + "\n")

sys.exit(0 if failed == 0 else 1)

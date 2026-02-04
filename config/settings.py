"""
Configurações centralizadas do sistema de automação de emails ABAplay
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# === API Configuration ===
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_NAME = os.getenv("SENDER_NAME", "ABAplay")

# === Email Limits ===
DAILY_EMAIL_LIMIT = 10  # Limite inicial para warmup
MAX_ATTEMPTS_PER_LEAD = 2  # Máximo de tentativas por lead

# === Schedule ===
WORK_HOURS_START = 9   # 09:00
WORK_HOURS_END = 18    # 18:00
WORK_DAYS = [0, 1, 2, 3, 4]  # Segunda a Sexta (0=Monday)

# === Delay Configuration (seconds) ===
DELAY_MEAN = 90        # Média do delay gaussiano
DELAY_STD = 30         # Desvio padrão
DELAY_MIN = 45         # Delay mínimo
DELAY_BATCH_PAUSE = 5  # Pausa maior a cada N emails
DELAY_BATCH_EXTRA_MIN = 300   # 5 min extras a cada batch
DELAY_BATCH_EXTRA_MAX = 600   # 10 min extras a cada batch

# === Paths ===
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "email_automation.db"
DESKTOP_PATH = Path(os.getenv("DESKTOP_PATH", Path.home() / "Área de Trabalho"))

# === Lead Scoring Weights ===
SCORE_EMAIL_EXISTS = 30
SCORE_EMAIL_TYPE = {
    'nominal': 25,    # secretariadraflaviana@gmail.com
    'cargo': 20,      # diretoria@clinica.com
    'generico': 10,   # contato@clinica.com
    'form_only': 0    # Sem email
}
SCORE_CONFIDENCE = {
    'alta': 25,
    'media': 15,
    'baixa': 5
}
SCORE_DECISOR_IDENTIFIED = 10
SCORE_HAS_WEBSITE = 10

# === Email Templates ===
TEMPLATES = {
    'decisor_identificado': {
        'assunto': '{nome_decisor}, como {nome_clinica} pode economizar 15h/semana em PEI',
        'corpo': '''
Olá {nome_decisor},

Vi que você lidera a {nome_clinica} em {cidade}. 

Sei que relatórios de evolução e PEI consomem tempo precioso da sua equipe. O ABAplay automatiza essa documentação:

✅ PEI escolar gerado em 5 minutos (100% LBI/BNCC)
✅ Relatórios de evolução com 1 clique
✅ Documentação "blindada" contra glosas de convênio

Clínicas ABA perdem em média 5-8% da receita por glosas. Posso mostrar como evitar isso em 15 minutos?

Ofereço 7 dias grátis para você testar com sua equipe.

---
Gabriel Gomes
Engenheiro de Software | ABAplay
(11) 98854-3437
https://abaplay.app.br/info

Se não deseja receber mais emails, responda com "REMOVER".
        '''
    },
    'sem_decisor': {
        'assunto': '{nome_clinica}: reduzir glosas em até 8% com documentação padronizada',
        'corpo': '''
Olá equipe {nome_clinica},

Clínicas ABA perdem em média 5-8% da receita por glosas de convênio. Documentação inadequada é a principal causa.

O ABAplay resolve isso com:

✅ +2.400 programas ABA baseados em evidências
✅ PEI escolar gerado em 5 minutos
✅ Relatórios padronizados que auditores adoram
✅ Portal para pais acompanharem em tempo real

Podemos agendar 15 minutos para eu mostrar como funciona?

Oferecemos 7 dias grátis, sem cartão de crédito.

---
Gabriel Gomes
Engenheiro de Software | ABAplay
(11) 98854-3437
https://abaplay.app.br/info

Se não deseja receber mais emails, responda com "REMOVER".
        '''
    }
}

# === Unsubscribe ===
UNSUBSCRIBE_KEYWORDS = ['remover', 'unsubscribe', 'descadastrar', 'não quero', 'pare']

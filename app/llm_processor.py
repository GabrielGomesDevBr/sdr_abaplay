"""
Processador de leads usando LLM (OpenAI) via LangChain
Versão 3.0 - Suporte a Leads Enriquecidos (contexto_abordagem)

Responsável por:
- Processar e enriquecer dados de leads
- Gerar emails hiperpersonalizados baseados em contexto
- Calcular scores contextuais
"""
import os
import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração do modelo (suporta Streamlit secrets e .env)
def _get_secret(key: str, default: str = "") -> str:
    """Busca secret do Streamlit ou .env"""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)

OPENAI_API_KEY = _get_secret("OPENAI_API_KEY", "")
OPENAI_MODEL = _get_secret("OPENAI_MODEL", "gpt-5-mini")


def get_llm():
    """Retorna instância do LLM configurado"""
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0.7,
        request_timeout=90
    )


# === Prompt para processamento de leads ===
LEAD_PROCESSING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um especialista em vendas B2B para clínicas de terapia ABA (Análise do Comportamento Aplicada).

Sua tarefa é processar uma lista de leads e para cada um:
1. Calcular um score de 0-100 baseado em qualidade e potencial de conversão
2. Identificar a melhor abordagem de vendas
3. Extrair insights relevantes

O produto vendido é o ABAplay, uma plataforma de gestão para clínicas ABA com:
- +2.400 programas de intervenção baseados em evidências
- Geração automática de PEI escolar (5 minutos)
- Relatórios de evolução com 1 clique
- Documentação padronizada anti-glosas de convênio
- Portal para pais acompanharem progresso

Critérios para scoring:
- Email válido e personalizado (nominal/cargo): +20-30 pontos
- Decisor identificado com nome: +15 pontos
- Site funcional: +10 pontos
- Confiança alta: +15 pontos, média: +8, baixa: +3
- Email genérico (contato@): +10 pontos
- Sem email: 0 pontos (descartar)

Responda APENAS com JSON válido, sem markdown."""),
    ("user", """Processe os seguintes leads da região {regiao}:

{leads_json}

Retorne um JSON com esta estrutura exata:
{{
    "leads_processados": [
        {{
            "nome_clinica": "nome original",
            "email": "email do lead",
            "score": 85,
            "score_justificativa": "explicação breve do score",
            "abordagem": "personalizada" ou "generica",
            "insights": "observações úteis para o vendedor",
            "deve_enviar": true ou false
        }}
    ],
    "leads_descartados": [
        {{
            "nome_clinica": "nome",
            "motivo": "sem email válido"
        }}
    ],
    "resumo": {{
        "total_processados": 5,
        "total_validos": 4,
        "total_descartados": 1
    }}
}}""")
])


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT PARA GERAÇÃO DE EMAIL v3.0 - SUPORTE A LEADS ENRIQUECIDOS
# ═══════════════════════════════════════════════════════════════════════════════

EMAIL_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é o Gabriel Gomes, co-fundador do ABAplay — uma plataforma de gestão
para clínicas ABA criada por analistas do comportamento.

Sua tarefa é escrever emails de prospecção que CONVERSEM COM A DOR REAL do lead,
como se você fosse um colega que entende a rotina dele — não um vendedor listando funcionalidades.

═══════════════════════════════════════════════════════════════════════════════
FILOSOFIA: FALE DA DOR, NÃO DA FERRAMENTA
═══════════════════════════════════════════════════════════════════════════════

Você NÃO está vendendo software.
Você está oferecendo a volta de noites livres, fins de semana sem PEI,
pais que confiam na clínica, e a tranquilidade de saber que a documentação
não vai causar glosa.

REGRA #1: Nunca liste funcionalidades. Sempre descreva transformações.
REGRA #2: O lead precisa ler e pensar "essa pessoa entende minha vida".
REGRA #3: Escreva como um colega analista do comportamento, não como vendedor de software.

═══════════════════════════════════════════════════════════════════════════════
AS DORES REAIS (use conforme o contexto do lead)
═══════════════════════════════════════════════════════════════════════════════

Estas são situações reais que clínicas ABA vivem. Use como matéria-prima:

O TERAPEUTA ÀS 22H:
Dor: Termina relatórios em casa porque não deu tempo no expediente. Todo dia.
Transformação: Registra a sessão no celular em 1 minuto, enquanto ainda está com a criança. Relatório sai pronto.
Frase que conecta: "Você se tornou profissional para ajudar crianças, não para ser escravo de burocracia."

15 ABAS ABERTAS:
Dor: WhatsApp, Excel, email do convênio, agenda de papel, Google Drive... e a sensação de que tudo pode dar errado.
Transformação: Tudo num lugar só. O que o terapeuta registra aparece no gráfico do pai, no relatório do supervisor e no dashboard do dono.
Frase que conecta: "Chega de 5 ferramentas que não conversam entre si."

A MÃE SEM RESPOSTAS:
Dor: Sai da clínica sem saber o que o filho trabalhou. Pergunta "como foi?" no WhatsApp e ninguém responde.
Transformação: Pais abrem o celular e veem, em linguagem simples, o que o filho aprendeu. Gráficos atualizados a cada sessão.
Frase que conecta: "Isso muda a relação da família com a clínica."

O SUPERVISOR PERDIDO:
Dor: Precisa compilar dados de 20 pacientes para a reunião de amanhã. Vai virar a noite juntando planilhas.
Transformação: Abre o dashboard e está tudo lá, atualizado em tempo real.
Frase que conecta: "Suas noites e fins de semana de volta."

O PEI DE FIM DE SEMANA:
Dor: A escola pediu PEI e o terapeuta perde um fim de semana inteiro montando no Word.
Transformação: PEI gerado em 5 minutos com dados reais do paciente, 100% conforme LBI e BNCC.
Frase que conecta: "Enquanto outros terapeutas perdem um fim de semana no PEI, sua equipe gera em 5 minutos."

A GLOSA QUE SANGRA:
Dor: Clínicas perdem de R$ 3.000 a R$ 8.000/mês com glosas por documentação inadequada. 5-8% do faturamento evaporando.
Transformação: Documentação automática, consistente, com gráficos quantificados — aceita por auditores.
Frase que conecta: "Cada R$ 1 investido no ABAplay economiza R$ 10-15 em glosas evitadas."

A EQUIPE FRAGMENTADA:
Dor: Fono, TO e psicólogo cada um no seu sistema. Ninguém vê o quadro completo do paciente.
Transformação: Todas as especialidades registram na mesma linha do tempo. A evolução fica completa, não fragmentada.
Frase que conecta: "Equipe integrada precisa de dados integrados."

═══════════════════════════════════════════════════════════════════════════════
MAPEAMENTO: TOM_SUGERIDO → ESTILO DE ESCRITA
═══════════════════════════════════════════════════════════════════════════════

IMPORTANTE: Em TODOS os tons, o email deve ser humano e conectado à dor.
A diferença é apenas o grau de formalidade e profundidade.

"consultivo" →
  • Colega especialista que compartilha uma solução
  • Pode usar dados e evidências, mas sempre conectados à dor real
  • Mostre que o ABAplay foi feito por quem aplica sessão no chão
  • Ex: "Quem supervisiona sabe que juntar dados de 20 pacientes em planilhas não é supervisão — é trabalho braçal."

"formal" →
  • Respeitoso e institucional, mas ainda humano
  • Use "Prezada" mas evite ser robótico
  • Foque em impacto social, prestação de contas, credibilidade
  • Ex: "Prezada Sra. Mariza, sabemos que instituições como a ATEAL prestam contas à sociedade — e que relatórios consistentes não deveriam custar noites da equipe."

"direto" →
  • Vá ao ponto. Sem floreios.
  • Cenário + transformação em poucas palavras
  • Ex: "3 unidades sem sistema unificado = supervisão no escuro. O ABAplay centraliza tudo."

"acolhedor" →
  • Tom caloroso, quase de amigo que entende a luta
  • Reconheça a jornada pessoal (fundadores com história familiar)
  • Foque na experiência da família e no cuidado
  • Ex: "Quem fundou uma clínica pensando no próprio filho sabe o quanto os pais precisam ver o progresso com os próprios olhos."

"neutro" (ou ausente) →
  • Profissional, cordial, brasileiro
  • Use a estrutura: cenário reconhecível → transformação → convite

═══════════════════════════════════════════════════════════════════════════════
MAPEAMENTO: PERFIL DE CLÍNICA → DOR PRIORITÁRIA
═══════════════════════════════════════════════════════════════════════════════

Use o "resumo_clinica" para escolher QUAL DOR ressoa mais:

CLÍNICA DE GRANDE PORTE / REFERÊNCIA:
• Dor principal: Supervisores perdidos compilando dados, padronização difícil com equipe grande
• Ângulo: "Quanto tempo sua equipe gasta juntando planilhas em vez de supervisionando?"

REDE COM MÚLTIPLAS UNIDADES:
• Dor principal: Fragmentação entre unidades, supervisão remota impossível
• Ângulo: "X unidades sem um sistema unificado = supervisão no escuro."

ONG / INSTITUIÇÃO FILANTRÓPICA:
• Dor principal: Volume alto, prestação de contas, relatórios que consomem a equipe
• Ângulo: "Fazer mais com menos — sem que a equipe pague o preço."

CLÍNICA MULTIDISCIPLINAR:
• Dor principal: Dados fragmentados entre fono, TO, psico — ninguém vê o quadro completo
• Ângulo: "Se a equipe é integrada, por que os dados ficam separados?"

CLÍNICA FAMILIAR / FUNDADA POR PAIS:
• Dor principal: Pais sem acesso ao progresso, WhatsApp caótico
• Ângulo: "Você sabe como é estar do outro lado — esperando notícias do progresso do seu filho."

CLÍNICA COM BRAÇO EDUCACIONAL (cursos, academy):
• Dor principal: Supervisão de estagiários sem dados objetivos
• Ângulo: "Supervisão baseada em achismo ou em dados?"

═══════════════════════════════════════════════════════════════════════════════
MAPEAMENTO: PERFIL DO DECISOR → ABORDAGEM
═══════════════════════════════════════════════════════════════════════════════

PESQUISADOR / AUTORIDADE TÉCNICA (Dr., PhD, publicações):
• Fale de como o ABAplay nasceu de dentro da ABA, não de uma empresa de TI
• Conecte com a frustração de "softwares que não entendem prompt fading"
• "Construímos a ferramenta que gostaríamos de ter tido"

GESTOR / DIRETOR EXECUTIVO:
• Fale do dinheiro sangrando em glosas e do tempo desperdiçado
• "Sua clínica pode estar perdendo R$ 3.000-8.000/mês com documentação inadequada"

FUNDADOR COM HISTÓRIA PESSOAL (mãe/pai de autista):
• Reconheça a jornada — é pessoal, não apenas profissional
• "Quem fundou uma clínica pensando no próprio filho..."

SUPERINTENDENTE / LÍDER INSTITUCIONAL:
• Fale de impacto em escala, transparência, sustentabilidade
• "Relatórios consistentes para 200 pacientes sem virar noite"

COORDENADOR / SUPERVISOR CLÍNICO:
• Fale das noites compilando dados, da supervisão feita no achismo
• "E se você pudesse abrir um dashboard antes da reunião em vez de virar a noite juntando planilhas?"

═══════════════════════════════════════════════════════════════════════════════
USANDO OS CAMPOS DO LEAD ENRIQUECIDO
═══════════════════════════════════════════════════════════════════════════════

1. "resumo_clinica" → Identifique o TIPO e escolha a DOR que mais ressoa
2. "perfil_decisor" → Calibre o ÂNGULO emocional e nível de formalidade
3. "gancho_personalizacao" → USE ESTE GANCHO! É ouro. Incorpore naturalmente.
4. "dor_provavel" → Esta é a DOR central — construa o email ao redor dela
5. "tom_sugerido" → Define o ESTILO de escrita

REGRA DE OURO: O email inteiro gira ao redor da DOR + TRANSFORMAÇÃO.
Funcionalidades só aparecem como prova da transformação, nunca como protagonistas.

═══════════════════════════════════════════════════════════════════════════════
ESTRUTURA DO EMAIL
═══════════════════════════════════════════════════════════════════════════════

1. ASSUNTO (30-50 caracteres)
   • Provoque reconhecimento ou curiosidade — NUNCA anuncie funcionalidades
   • BOM: "Relatórios às 22h?" / "[Clínica], noites livres de volta"
   • RUIM: "Conheça o ABAplay" / "Software de gestão ABA"
   • Use o nome da clínica quando couber

2. SAUDAÇÃO (adapte ao tom_sugerido)
   • consultivo/formal: "Prezado(a) [Nome]" ou "Estimada [Nome]"
   • direto: "Oi, [Nome]!" ou "Olá, equipe [Clínica]!"
   • acolhedor: "Oi, [Nome]! Tudo bem por aí?"

3. CENÁRIO RECONHECÍVEL (1-2 frases)
   • USE o "gancho_personalizacao" como base
   • Pinte uma situação que o lead VIVE (não que ele "poderia viver")
   • O lead deve ler e pensar "é exatamente isso"

4. A TRANSFORMAÇÃO (1-2 frases)
   • Mostre o "depois" — como a vida muda, não como o software funciona
   • Conecte com o "dor_provavel" para construir dor → transformação
   • Pode incluir 1 métrica de impacto (ex: "5h → 5min", "90% menos glosas")

5. PROVA DE CREDIBILIDADE (1 frase curta)
   • "Construímos o ABAplay porque somos analistas do comportamento — não empresa de TI."
   • Ou um dado: "2.402 programas em português", "100% conforme LBI/BNCC"
   • Ou um resultado: "Clínicas nos dizem que recuperaram as noites."

6. CTA (1 frase)
   • consultivo: "Posso te mostrar em 15 minutos como funciona na prática?"
   • formal: "Seria um prazer apresentar a plataforma à sua equipe."
   • direto: "15 min essa semana?"
   • acolhedor: "Que tal uma conversa rápida?"

7. ASSINATURA (FIXA):
---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

═══════════════════════════════════════════════════════════════════════════════
REGRAS ABSOLUTAS
═══════════════════════════════════════════════════════════════════════════════

FAÇA:
• Corpo com no máximo 80 palavras (sem contar assinatura) — menos é mais
• Comece pela DOR ou cenário, nunca pelo produto
• Use linguagem do dia a dia ("virar noite juntando planilha", não "otimizar fluxo de dados")
• O lead deve sentir que você ENTENDE a rotina dele
• Adapte o tom conforme tom_sugerido
• Inclua no máximo 1 número/métrica como prova

NÃO FAÇA:
• NUNCA liste funcionalidades com bullets ou checkmarks
• NUNCA use jargão de software ("sistema", "plataforma", "ferramenta", "solução tecnológica", "funcionalidades", "recursos", "módulos")
• NUNCA comece o email falando do ABAplay — comece falando da DOR do lead
• Não mencione preços
• Não seja genérico quando tem dados ricos sobre o lead
• Não misture tons (ex: formal + "15 minutinhos")

═══════════════════════════════════════════════════════════════════════════════
EXEMPLOS COM A NOVA ABORDAGEM
═══════════════════════════════════════════════════════════════════════════════

EXEMPLO 1: Tom Consultivo (Autoridade Técnica)
---
Lead: Grupo Conduzir | Dr. Fábio Coelho (Fundador/Pesquisador)
Tom: consultivo | Dor: Supervisão de estagiários sem dados objetivos
Gancho: Conduzir Academy forma profissionais

Assunto: Conduzir: supervisão com dados ou no achismo?

Prezado Dr. Fábio,

Quem forma profissionais em ABA sabe que supervisão sem dados objetivos é achismo com diploma. Compilar evolução de estagiários em planilhas separadas consome tempo que deveria ir para a formação.

Construímos o ABAplay justamente por isso — somos analistas do comportamento cansados de softwares feitos por quem nunca aplicou sessão no chão.

Posso te mostrar em 20 minutos como funciona na prática?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

EXEMPLO 2: Tom Formal (Instituição/ONG)
---
Lead: ATEAL | Mariza Cavenaghi (Superintendente)
Tom: formal | Dor: Alto volume + relatórios que consomem a equipe
Gancho: Transparência e prestação de contas

Assunto: ATEAL: relatórios sem virar noite

Prezada Sra. Mariza,

Instituições como a ATEAL atendem volume alto e precisam prestar contas — mas isso não deveria custar as noites e fins de semana da equipe compilando relatórios manualmente.

Somos analistas do comportamento que construíram o ABAplay para que relatórios profissionais saiam em segundos, não em horas.

Seria um prazer apresentar à sua equipe.

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

EXEMPLO 3: Tom Direto (Rede em Expansão)
---
Lead: CompletaMente ABA | Decisor desconhecido
Tom: direto | Dor: 3 unidades sem sistema unificado
Gancho: Coordenar Jundiaí, Caieiras e Taipas

Assunto: CompletaMente: 3 unidades, supervisão no escuro?

Olá, equipe CompletaMente!

3 unidades sem um sistema unificado significa supervisores ligando para cada unidade pedindo atualização. Prontuários que não conversam. Padrão de qualidade que depende de quem está na sala.

O ABAplay nasceu pra resolver isso — tudo em nuvem, acesso de qualquer unidade, em tempo real.

15 min para mostrar?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

EXEMPLO 4: Tom Acolhedor (Fundada por Mãe)
---
Lead: Evoluir Brincando | Sócias-Fundadoras (mãe de autista)
Tom: acolhedor | Dor: Pais sem acesso ao progresso
Gancho: Fundadora sabe como é estar do outro lado

Assunto: Evoluir Brincando: o que os pais realmente querem saber

Oi, equipe Evoluir Brincando! Tudo bem?

Quem fundou uma clínica pensando no próprio filho sabe a angústia de perguntar "como foi hoje?" e não ter resposta concreta. É por isso que construímos algo diferente: os pais abrem o celular e veem, em linguagem simples, exatamente o que o filho aprendeu.

Menos cobrança no WhatsApp, mais confiança na clínica.

Que tal uma conversa essa semana?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

EXEMPLO 5: Tom Neutro (Glosas — Dor Financeira)
---
Lead: Clínica Integrar | Diretora Clínica
Tom: neutro | Dor: Glosas consumindo receita
Gancho: Clínica atende convênios

Assunto: Integrar: quanto está perdendo em glosas?

Oi, equipe da Integrar!

Clínicas ABA que atendem convênios perdem entre 5% e 8% do faturamento com glosas — R$ 3.000 a R$ 8.000 por mês evaporando por documentação inconsistente.

A maioria nem percebe quanto está deixando na mesa. Construímos o ABAplay para que a documentação saia certa desde o registro da sessão — sem retrabalho.

Posso mostrar em 15 minutos?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Responda APENAS com JSON válido:
{{"assunto": "...", "corpo": "..."}}

O campo "corpo" deve incluir o email completo com saudação e assinatura.
"""),
    ("user", """LEAD ENRIQUECIDO:

Clínica: {nome_clinica}
Cidade/UF: {cidade_uf}
Site: {site}

DECISOR:
Nome: {decisor_nome}
Cargo: {decisor_cargo}

CONTATO:
Email: {email_principal}
Tipo de email: {email_tipo}

CONTEXTO DE ABORDAGEM:
Resumo da clínica: {resumo_clinica}
Perfil do decisor: {perfil_decisor}
Gancho de personalização: {gancho_personalizacao}
Dor provável: {dor_provavel}
Tom sugerido: {tom_sugerido}

Confiança do lead: {confianca}

---
Gere o email hiperpersonalizado:
{{"assunto": "...", "corpo": "..."}}""")
])


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT DE FOLLOW-UP (adaptado para dados enriquecidos)
# ═══════════════════════════════════════════════════════════════════════════════

EMAIL_FOLLOWUP_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é o Gabriel Gomes do ABAplay. Gera emails de FOLLOW-UP curtos e humanos
para leads que não responderam ao primeiro contato.

FILOSOFIA: Você é um colega que entende a rotina deles, não um vendedor insistente.

PRINCÍPIOS:
• Seja breve e respeitoso — a pessoa é ocupada
• Traga um CENÁRIO DIFERENTE do primeiro email (outra dor do dia a dia)
• Máximo 50 palavras no corpo (sem assinatura)
• Mantenha o tom_sugerido do lead original
• NUNCA liste funcionalidades — descreva uma situação reconhecível

ESTRUTURA:
1. "[Nome], passando rapidinho..."
2. Pinte um cenário diferente que eles vivem (1-2 frases)
3. CTA super curto
4. Assinatura

ROTAÇÃO DE CENÁRIOS (se a dor do primeiro email foi X, use Y):
• Glosas → "A escola pediu PEI e o terapeuta vai perder o fim de semana no Word?"
• PEI → "Os pais perguntam 'como foi?' no WhatsApp e ninguém tem tempo de responder?"
• Registro manual → "Sua equipe ainda termina relatórios em casa às 22h?"
• WhatsApp bagunçado → "Quanto do faturamento está evaporando em glosas por documentação inconsistente?"
• Supervisão → "Fono, TO e psicólogo cada um no seu canto — ninguém vê o quadro completo?"

Responda APENAS com JSON: {{"assunto": "...", "corpo": "..."}}
"""),
    ("user", """FOLLOW-UP PARA:

Clínica: {nome_clinica}
Decisor: {decisor_nome}
Tom sugerido: {tom_sugerido}
Dor usada no primeiro email: {dor_primeiro_email}
Dias desde contato: {dias_desde_contato}

{{"assunto": "...", "corpo": "..."}}""")
])


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT PARA PROCESSAR BATCH DE LEADS
# ═══════════════════════════════════════════════════════════════════════════════

BATCH_PRIORITIZATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você analisa um batch de leads e prioriza a ordem de contato.

CRITÉRIOS DE PRIORIZAÇÃO:
1. Confiança "alta" > "media" > "baixa"
2. Decisor identificado > decisor desconhecido
3. Email direto > email departamento > form_only
4. Clínicas maiores/redes > clínicas pequenas
5. Dor clara identificada > dor vaga

Para cada lead, atribua:
- prioridade: 1 (alta), 2 (média), 3 (baixa)
- motivo: razão da priorização
- sequencia_sugerida: ordem de contato

Responda em JSON:
{{
  "leads_priorizados": [
    {{"nome_clinica": "...", "prioridade": 1, "motivo": "...", "sequencia": 1}},
    ...
  ],
  "observacoes": "..."
}}
"""),
    ("user", """BATCH DE LEADS:
{leads_json}

Priorize para contato:""")
])


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO AUXILIAR PARA EXTRAIR DADOS DO NOVO FORMATO
# ═══════════════════════════════════════════════════════════════════════════════

def extract_lead_data_for_prompt(lead: dict) -> dict:
    """
    Extrai e formata os dados do lead enriquecido para o prompt.
    
    Args:
        lead: Dicionário do lead no novo formato
        
    Returns:
        Dicionário formatado para o prompt
    """
    decisor = lead.get('decisor', {})
    contatos = lead.get('contatos', {})
    contexto = lead.get('contexto_abordagem', {})
    
    return {
        "nome_clinica": lead.get('nome_clinica', 'Clínica'),
        "cidade_uf": lead.get('cidade_uf', ''),
        "site": lead.get('site', ''),
        
        # Decisor
        "decisor_nome": decisor.get('nome') or 'Equipe',
        "decisor_cargo": decisor.get('cargo') or '',
        
        # Contato
        "email_principal": contatos.get('email_principal') or '',
        "email_tipo": contatos.get('email_tipo') or 'generico',
        
        # Contexto (os campos novos!)
        "resumo_clinica": contexto.get('resumo_clinica') or '',
        "perfil_decisor": contexto.get('perfil_decisor') or '',
        "gancho_personalizacao": contexto.get('gancho_personalizacao') or '',
        "dor_provavel": contexto.get('dor_provavel') or '',
        "tom_sugerido": contexto.get('tom_sugerido') or 'neutro',
        
        # Metadata
        "confianca": lead.get('confianca', 'media')
    }


def _get_fallback_email_body(nome_clinica: str) -> str:
    """Retorna corpo de email fallback quando LLM falha ou timeout"""
    return f"""Oi, equipe {nome_clinica}!

Sua equipe se formou para ajudar crianças — mas quanto do dia vai embora em relatórios, PEI e documentação?

Somos analistas do comportamento que construíram o ABAplay para devolver esse tempo. Clínicas nos dizem que recuperaram as noites e fins de semana.

Posso mostrar em 15 minutos?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---"""


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE PROCESSAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

async def process_leads_with_llm(leads_json: str, regiao: str, timeout: int = 240) -> Dict:
    """
    Processa leads usando LLM para análise contextual

    Args:
        leads_json: JSON string com os leads
        regiao: Região buscada
        timeout: Timeout em segundos (default: 60)

    Returns:
        Dict com leads processados, descartados e resumo
    """
    import asyncio

    try:
        llm = get_llm()
        parser = JsonOutputParser()

        chain = LEAD_PROCESSING_PROMPT | llm | parser

        # Executa com timeout
        result = await asyncio.wait_for(
            chain.ainvoke({
                "regiao": regiao,
                "leads_json": leads_json
            }),
            timeout=timeout
        )

        return result

    except asyncio.TimeoutError:
        return {
            "error": f"Timeout: LLM não respondeu em {timeout} segundos",
            "leads_processados": [],
            "leads_descartados": [],
            "resumo": {"total_processados": 0, "total_validos": 0, "total_descartados": 0}
        }
    except Exception as e:
        # Fallback: retorna erro para tratamento
        return {
            "error": str(e),
            "leads_processados": [],
            "leads_descartados": [],
            "resumo": {"total_processados": 0, "total_validos": 0, "total_descartados": 0}
        }


def process_leads_with_llm_sync(leads_json: str, regiao: str) -> Dict:
    """Versão síncrona do processamento de leads (compatível com Streamlit)"""
    import asyncio
    import concurrent.futures

    def _run():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(process_leads_with_llm(leads_json, regiao))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=270)  # margem sobre o timeout interno de 240s


async def generate_email_for_enriched_lead(lead: dict, timeout: int = 30) -> dict:
    """
    Gera email personalizado para lead enriquecido (v3.0).

    Args:
        lead: Lead no novo formato com contexto_abordagem
        timeout: Timeout em segundos (default: 30)

    Returns:
        Dict com assunto e corpo do email
    """
    import asyncio

    try:
        llm = get_llm()
        parser = JsonOutputParser()
        chain = EMAIL_GENERATION_PROMPT | llm | parser

        # Extrai dados formatados
        prompt_data = extract_lead_data_for_prompt(lead)

        # Executa com timeout
        result = await asyncio.wait_for(
            chain.ainvoke(prompt_data),
            timeout=timeout
        )
        return result

    except asyncio.TimeoutError:
        # Fallback em caso de timeout
        nome = lead.get('nome_clinica', 'Clínica')
        return {
            "assunto": f"{nome}: gestão ABA profissional",
            "corpo": _get_fallback_email_body(nome),
            "error": f"Timeout: LLM não respondeu em {timeout} segundos"
        }
    except Exception as e:
        # Fallback
        nome = lead.get('nome_clinica', 'Clínica')
        return {
            "assunto": f"{nome}: gestão ABA profissional",
            "corpo": _get_fallback_email_body(nome),
            "error": str(e)
        }


async def generate_email_with_llm(lead: Dict, insights: str = "", timeout: int = 30) -> Dict:
    """
    Gera email personalizado usando LLM (compatibilidade com v2.0 e v3.0).

    Detecta automaticamente se o lead possui contexto_abordagem e usa
    o prompt apropriado.

    Args:
        lead: Dados do lead
        insights: Insights sobre o lead (usado se não houver contexto_abordagem)
        timeout: Timeout em segundos (default: 30)

    Returns:
        Dict com assunto e corpo do email
    """
    import asyncio

    # Se tem contexto_abordagem, usa o novo sistema v3.0
    if lead.get('contexto_abordagem'):
        return await generate_email_for_enriched_lead(lead, timeout=timeout)

    # Fallback para leads sem enriquecimento (compatibilidade)
    try:
        llm = get_llm()
        parser = JsonOutputParser()

        chain = EMAIL_GENERATION_PROMPT | llm | parser

        # Extrai dados do lead (formato legado)
        decisor = lead.get('decisor', {})
        contatos = lead.get('contatos', {})

        # Monta dados no formato esperado pelo novo prompt
        prompt_data = {
            "nome_clinica": lead.get('nome_clinica', 'Clínica'),
            "cidade_uf": lead.get('cidade_uf', '').split(' - ')[0] if lead.get('cidade_uf') else '',
            "site": lead.get('site', ''),
            "decisor_nome": decisor.get('nome') or lead.get('decisor_nome', 'Equipe'),
            "decisor_cargo": decisor.get('cargo') or lead.get('decisor_cargo', ''),
            "email_principal": contatos.get('email_principal') or lead.get('email_principal', ''),
            "email_tipo": contatos.get('email_tipo') or lead.get('email_tipo', 'generico'),
            # Campos de contexto vazios (lead não enriquecido)
            "resumo_clinica": insights or '',
            "perfil_decisor": '',
            "gancho_personalizacao": '',
            "dor_provavel": '',
            "tom_sugerido": 'neutro',
            "confianca": lead.get('confianca', 'media')
        }

        # Executa com timeout
        result = await asyncio.wait_for(
            chain.ainvoke(prompt_data),
            timeout=timeout
        )
        return result

    except asyncio.TimeoutError:
        nome_clinica = lead.get('nome_clinica', 'Clínica')
        return {
            "assunto": f"{nome_clinica}: gestão ABA profissional",
            "corpo": _get_fallback_email_body(nome_clinica),
            "error": f"Timeout: LLM não respondeu em {timeout} segundos"
        }
    except Exception as e:
        # Fallback: retorna template básico
        nome_clinica = lead.get('nome_clinica', 'Clínica')
        return {
            "assunto": f"{nome_clinica}: gestão ABA profissional",
            "corpo": _get_fallback_email_body(nome_clinica),
            "error": str(e)
        }


def generate_email_with_llm_sync(lead: Dict, insights: str = "") -> Dict:
    """Versão síncrona da geração de email (compatível com Streamlit)"""
    import asyncio
    import concurrent.futures

    def _run():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(generate_email_with_llm(lead, insights))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=60)  # margem sobre o timeout interno de 30s


async def generate_followup_email(lead: Dict, dor_primeiro_email: str, dias_desde_contato: int) -> Dict:
    """
    Gera email de follow-up para lead que não respondeu.
    
    Args:
        lead: Dados do lead
        dor_primeiro_email: A dor usada no primeiro email
        dias_desde_contato: Dias desde o último contato
        
    Returns:
        Dict com assunto e corpo do email
    """
    try:
        llm = get_llm()
        parser = JsonOutputParser()
        chain = EMAIL_FOLLOWUP_PROMPT | llm | parser
        
        decisor = lead.get('decisor', {})
        contexto = lead.get('contexto_abordagem', {})
        
        result = await chain.ainvoke({
            "nome_clinica": lead.get('nome_clinica', 'Clínica'),
            "decisor_nome": decisor.get('nome') or 'Equipe',
            "tom_sugerido": contexto.get('tom_sugerido', 'neutro'),
            "dor_primeiro_email": dor_primeiro_email,
            "dias_desde_contato": dias_desde_contato
        })
        
        return result
        
    except Exception as e:
        nome = lead.get('nome_clinica', 'Clínica')
        return {
            "assunto": f"{nome}, passando rapidinho",
            "corpo": f"""Oi, equipe {nome}!

Sei que a rotina é corrida — por isso mesmo: quanto do dia da equipe vai embora em burocracia que poderia ser automática?

Se tiver 15 minutos essa semana, posso mostrar como clínicas estão recuperando esse tempo.

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---""",
            "error": str(e)
        }


def generate_followup_email_sync(lead: Dict, dor_primeiro_email: str, dias_desde_contato: int) -> Dict:
    """Versão síncrona da geração de follow-up (compatível com Streamlit)"""
    import asyncio
    import concurrent.futures

    def _run():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(generate_followup_email(lead, dor_primeiro_email, dias_desde_contato))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=60)


def test_llm_connection() -> Tuple[bool, str]:
    """
    Testa conexão com a API da OpenAI
    
    Returns:
        Tuple[success, message]
    """
    if not OPENAI_API_KEY:
        return False, "OPENAI_API_KEY não configurada no .env"
    
    try:
        llm = get_llm()
        # Teste simples
        response = llm.invoke("Responda apenas 'OK'")
        return True, f"Conexão OK. Modelo: {OPENAI_MODEL}"
    except Exception as e:
        return False, f"Erro na conexão: {str(e)}"

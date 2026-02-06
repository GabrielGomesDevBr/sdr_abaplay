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
        temperature=0.7
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
    ("system", """Você é um especialista em copywriting B2B para o mercado de saúde brasileiro,
especificamente para clínicas de terapia ABA (Análise do Comportamento Aplicada).

Sua tarefa é gerar emails de prospecção HIPERPERSONALIZADOS usando os dados enriquecidos do lead.

═══════════════════════════════════════════════════════════════════════════════
SOBRE O ABAPLAY
═══════════════════════════════════════════════════════════════════════════════

Plataforma SaaS de gestão para clínicas ABA, desenvolvida por profissionais ABA.

ARSENAL DE BENEFÍCIOS (use conforme o contexto do lead):

📊 DADOS E GRÁFICOS:
• Gráficos de evolução automáticos por área de intervenção
• Dashboard de métricas e performance da equipe
• Verificador de progresso que detecta programas dominados
• Dados consistentes para pesquisa e publicações científicas

📝 DOCUMENTAÇÃO:
• PEI escolar automático (5h → 5min, 92% de redução)
• 100% conforme LBI e BNCC
• Relatórios profissionais com 1 clique
• Documentação aceita por auditores de convênio
• Elimina até 90% das glosas

📱 REGISTRO E OPERAÇÃO:
• Registro de sessões pelo celular (6 níveis de prompt coloridos)
• 2.402+ programas baseados em evidências (ABA, Fono, TO, Psico)
• Criação de programas personalizados da clínica
• Sistema em nuvem — acesse de qualquer lugar

👨‍👩‍👧 COMUNICAÇÃO:
• Portal dos Pais com evolução em tempo real
• Chat profissional por paciente (substitui WhatsApp)
• Canal de discussão de casos para equipe
• Histórico completo documentado

🏢 GESTÃO MULTI-UNIDADE:
• Prontuários centralizados para redes de clínicas
• Padrão de qualidade unificado entre unidades
• Supervisão remota com dados em tempo real
• Relatórios consolidados

🎓 FORMAÇÃO E SUPERVISÃO:
• Gráficos de desempenho para supervisão de estagiários/ATs
• Padronização de procedimentos entre terapeutas
• Biblioteca compartilhada de programas
• Rastreabilidade de intervenções

═══════════════════════════════════════════════════════════════════════════════
MAPEAMENTO: TOM_SUGERIDO → ESTILO DE ESCRITA
═══════════════════════════════════════════════════════════════════════════════

O campo "tom_sugerido" indica como calibrar a comunicação:

"consultivo" → 
  • Abordagem de especialista para especialista
  • Mencione dados, evidências, métricas complexas
  • Mostre profundidade técnica
  • Evite simplificações — o decisor é sofisticado
  • Ex: "Os gráficos de linha de base múltipla do ABAplay permitem análise de tendência em tempo real..."

"formal" →
  • Tom institucional e respeitoso
  • Use tratamento mais cerimonioso ("Prezada Sra.", "Estimada equipe")
  • Foque em credibilidade, transparência, prestação de contas
  • Ideal para ONGs, associações, instituições públicas
  • Ex: "Prezada Sra. Mariza, sabemos da responsabilidade de uma instituição como a ATEAL..."

"direto" →
  • Vá ao ponto rapidamente
  • Menos floreios, mais benefício concreto
  • Ideal para redes em expansão, gestores práticos
  • Ex: "3 unidades, 1 sistema. Prontuários centralizados, supervisão em tempo real."

"acolhedor" →
  • Tom caloroso, empático, humano
  • Reconheça a jornada pessoal (especialmente se há fundadores com história familiar)
  • Foque em experiência da família, comunicação com pais
  • Ex: "Quem fundou uma clínica pensando no próprio filho sabe o quanto os pais precisam de transparência..."

"neutro" (ou ausente) →
  • Use tom padrão: profissional, cordial, brasileiro
  • Estrutura PAS clássica

═══════════════════════════════════════════════════════════════════════════════
MAPEAMENTO: PERFIL DE CLÍNICA → BENEFÍCIOS PRIORITÁRIOS
═══════════════════════════════════════════════════════════════════════════════

Use o "resumo_clinica" para identificar o tipo e priorizar benefícios:

CLÍNICA DE GRANDE PORTE / REFERÊNCIA:
• Priorize: Gráficos avançados, dados para pesquisa, padronização de equipe grande
• Evite: Benefícios básicos que pareçam triviais

REDE COM MÚLTIPLAS UNIDADES:
• Priorize: Centralização de prontuários, supervisão remota, padrão de qualidade unificado
• Gancho: "X unidades, 1 sistema"

ONG / INSTITUIÇÃO FILANTRÓPICA:
• Priorize: Transparência em relatórios, prestação de contas, volume de atendimento
• Mencione: Eficiência operacional (fazer mais com menos)

CLÍNICA MULTIDISCIPLINAR:
• Priorize: Integração entre especialidades (Fono, TO, Psico na mesma linha do tempo)
• Gancho: "Equipe integrada precisa de dados integrados"

CLÍNICA FAMILIAR / FUNDADA POR PAIS:
• Priorize: Portal dos Pais, comunicação transparente, experiência da família
• Tom: Mais emocional e empático

CLÍNICA COM BRAÇO EDUCACIONAL (cursos, academy):
• Priorize: Supervisão de estagiários, gráficos de desempenho, formação
• Gancho: Facilita a supervisão clínica de alunos em formação

═══════════════════════════════════════════════════════════════════════════════
MAPEAMENTO: PERFIL DO DECISOR → ABORDAGEM
═══════════════════════════════════════════════════════════════════════════════

Use o "perfil_decisor" para calibrar a mensagem:

PESQUISADOR / AUTORIDADE TÉCNICA (Dr., PhD, publicações):
• Fale de dados, evidências, gráficos complexos
• Evite simplificações — ele detecta superficialidade
• Mostre que o ABAplay foi feito por quem entende ABA

GESTOR / DIRETOR EXECUTIVO:
• Foque em ROI, eficiência, escala
• Mencione redução de custos, tempo economizado
• Números concretos: "90% menos glosas", "92% menos tempo em PEI"

FUNDADOR COM HISTÓRIA PESSOAL (mãe/pai de autista):
• Reconheça a jornada
• Foque em experiência da família, cuidado, transparência
• Tom mais humano e menos corporativo

SUPERINTENDENTE / LÍDER INSTITUCIONAL:
• Foque em sustentabilidade, prestação de contas, parcerias
• Tom mais formal e institucional

COORDENADOR / SUPERVISOR CLÍNICO:
• Foque em operação do dia a dia
• Tempo economizado, padronização, facilidade de supervisão

═══════════════════════════════════════════════════════════════════════════════
USANDO OS CAMPOS DO LEAD ENRIQUECIDO
═══════════════════════════════════════════════════════════════════════════════

Você receberá estes campos — use-os estrategicamente:

1. "resumo_clinica" → Entenda o TIPO de clínica para escolher benefícios
2. "perfil_decisor" → Calibre a ABORDAGEM e profundidade técnica
3. "gancho_personalizacao" → USE ESTE GANCHO! É ouro. Incorpore no email.
4. "dor_provavel" → Esta é a DOR para usar na estrutura PAS
5. "tom_sugerido" → Define o ESTILO de escrita (consultivo/formal/direto/acolhedor)

REGRA DE OURO: O "gancho_personalizacao" já foi pensado para aquele lead específico.
Não ignore — use como base da personalização.

═══════════════════════════════════════════════════════════════════════════════
ESTRUTURA DO EMAIL
═══════════════════════════════════════════════════════════════════════════════

1. ASSUNTO (30-50 caracteres)
   • Personalize com nome da clínica quando possível
   • Mencione a dor ou benefício específico do lead
   • Use o gancho se couber

2. SAUDAÇÃO (adapte ao tom_sugerido)
   • consultivo/formal: "Prezado Dr. [Nome]" ou "Estimada [Nome]"
   • direto: "Oi, [Nome]!" ou "Olá, equipe [Clínica]!"
   • acolhedor: "Oi, [Nome]! Tudo bem por aí?"

3. GANCHO PERSONALIZADO (1-2 frases)
   • USE o campo "gancho_personalizacao" como base
   • Mostre que você pesquisou sobre eles
   • Conecte algo específico deles ao ABAplay

4. DOR + IMPACTO (1-2 frases)
   • USE o campo "dor_provavel"
   • Amplifique brevemente o impacto

5. SOLUÇÃO ESPECÍFICA (1-2 frases)
   • Conecte o benefício do ABAplay à dor identificada
   • Inclua métrica quando possível

6. CTA (1 frase)
   • Adapte ao tom:
     - consultivo: "Posso apresentar os recursos de análise em uma conversa de 15 minutos?"
     - formal: "Seria um prazer agendar uma apresentação com sua equipe."
     - direto: "15 min para mostrar como funciona?"
     - acolhedor: "Que tal uma conversa rápida essa semana?"

7. ASSINATURA (FIXA):
---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

═══════════════════════════════════════════════════════════════════════════════
REGRAS
═══════════════════════════════════════════════════════════════════════════════

✓ FAÇA:
• Corpo com no máximo 100 palavras (sem contar assinatura)
• Use o gancho_personalizacao — é o diferencial
• Adapte o tom conforme tom_sugerido
• Inclua pelo menos 1 número/métrica
• Seja específico para aquele lead

✗ NÃO FAÇA:
• Não mencione preços
• Não use o mesmo email genérico para todos
• Não ignore os campos de contexto
• Não seja genérico quando tem dados ricos
• Não misture tons (ex: formal + "15 minutinhos")

═══════════════════════════════════════════════════════════════════════════════
EXEMPLOS COM DADOS ENRIQUECIDOS
═══════════════════════════════════════════════════════════════════════════════

EXEMPLO 1: Tom Consultivo (Autoridade Técnica)
---
Lead: Grupo Conduzir | Dr. Fábio Coelho (Fundador/Pesquisador)
Tom: consultivo
Gancho: Conduzir Academy + supervisão de estagiários
Dor: Gráficos ABA complexos que sistemas genéricos não entregam

Assunto: Conduzir: gráficos de linha de base no ABAplay

Prezado Dr. Fábio,

A Conduzir Academy forma profissionais que precisam de supervisão baseada em dados — e sistemas genéricos raramente entregam os gráficos de evolução que a análise ABA exige.

O ABAplay foi desenvolvido por analistas do comportamento. Oferece gráficos de linha de base, tendência automática e exportação de dados brutos para pesquisa.

Posso apresentar os recursos de análise em 20 minutos?

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
Tom: formal
Gancho: Transparência em relatórios para prestação de contas
Dor: Alto volume de pacientes gera gargalo em relatórios

Assunto: ATEAL: relatórios de evolução em escala

Prezada Sra. Mariza,

Instituições como a ATEAL, que prestam contas à sociedade, precisam de relatórios de evolução consistentes — mesmo com alto volume de pacientes.

O ABAplay gera relatórios profissionais em segundos, com gráficos padronizados e rastreabilidade completa. Ideal para auditorias e prestação de contas.

Seria um prazer apresentar a plataforma à sua equipe.

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
Tom: direto
Gancho: 3 unidades precisam de prontuários centralizados
Dor: Supervisão difícil sem sistema unificado

Assunto: CompletaMente: 3 unidades, 1 sistema

Olá, equipe CompletaMente!

Coordenar terapeutas em Jundiaí, Caieiras e Taipas sem um sistema centralizado é um desafio. Prontuários fragmentados dificultam supervisão e padrão de qualidade.

O ABAplay centraliza tudo em nuvem: prontuários, gráficos e comunicação — acesso em tempo real de qualquer unidade.

15 minutos para mostrar como funciona?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

EXEMPLO 4: Tom Acolhedor (Fundada por Mãe)
---
Lead: Evoluir Brincando | Sócias-Fundadoras (inclui mãe de autista)
Tom: acolhedor
Gancho: Mãe fundadora valoriza portal dos pais
Dor: WhatsApp bagunçado, sobrecarga administrativa

Assunto: Evoluir Brincando: pais conectados

Oi, equipe Evoluir Brincando! Tudo bem?

Quem fundou uma clínica pensando no próprio filho sabe o quanto os pais precisam acompanhar a evolução de perto — sem depender de mensagens no WhatsApp.

O ABAplay tem um Portal dos Pais onde eles veem gráficos e sessões em tempo real. Menos cobrança, mais confiança.

Que tal uma conversa essa semana?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
---

EXEMPLO 5: Tom Acolhedor (Multidisciplinar)
---
Lead: Clínica Vivere | Decisor desconhecido
Tom: acolhedor
Gancho: Equipe multidisciplinar integrada
Dor: Dados fragmentados entre especialidades

Assunto: Vivere: equipe integrada, dados integrados

Oi, equipe da Vivere! Tudo bem?

Vocês destacam a integração da equipe multidisciplinar — e sabemos que, na prática, integrar dados de fono, TO e psicólogo costuma ser o desafio.

No ABAplay, todas as especialidades registram na mesma linha do tempo. A evolução do paciente fica completa, não fragmentada.

Posso mostrar como funciona em 15 minutinhos?

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
    ("system", """Você gera emails de FOLLOW-UP para leads que não responderam.

PRINCÍPIOS:
• Reconheça que a pessoa é ocupada
• Traga um NOVO ângulo (não repita a dor do primeiro email)
• Máximo 60 palavras
• Mantenha o tom_sugerido do lead original
• Pode mencionar uma novidade ou caso de sucesso

ESTRUTURA:
1. "[Nome], passando rapidinho..."
2. Novo gancho ou benefício diferente
3. CTA super curto
4. Assinatura

Use o campo "dor_alternativa" para variar a abordagem.

DORES ALTERNATIVAS (se a primeira foi X, use Y):
• Glosas → PEI automático
• PEI → Portal dos Pais
• Registro manual → Gráficos automáticos
• WhatsApp bagunçado → Integração multidisciplinar
• Supervisão → Biblioteca de programas

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
    return f"""Olá, equipe {nome_clinica}!

Clínicas ABA perdem tempo com burocracia que poderia ser automatizada.

O ABAplay resolve isso com registro de sessões pelo celular, gráficos automáticos e relatórios em 1 clique.

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

async def process_leads_with_llm(leads_json: str, regiao: str, timeout: int = 60) -> Dict:
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
    """Versão síncrona do processamento de leads"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(process_leads_with_llm(leads_json, regiao))


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
    """Versão síncrona da geração de email"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(generate_email_with_llm(lead, insights))


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
            "assunto": f"Re: {nome}",
            "corpo": f"""Oi, equipe {nome}!

Passando rapidinho — vi que ainda não conseguimos conversar.

Posso mostrar o ABAplay em 15 minutinhos essa semana?

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
    """Versão síncrona da geração de follow-up"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(generate_followup_email(lead, dor_primeiro_email, dias_desde_contato))


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

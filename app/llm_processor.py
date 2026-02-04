"""
Processador de leads usando LLM (OpenAI) via LangChain
Responsável por:
- Processar e enriquecer dados de leads
- Gerar emails personalizados
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


# === Prompt para geração de email personalizado v2.0 ===
# Sistema completo com contexto profundo do mercado ABA brasileiro
# Inclui: personas, dores específicas, framework PAS + cultura BR
EMAIL_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um especialista em copywriting B2B para o mercado de saúde brasileiro, 
especificamente para clínicas de terapia ABA (Análise do Comportamento Aplicada) que atendem 
crianças com TEA (Transtorno do Espectro Autista) e outros transtornos do neurodesenvolvimento.

═══════════════════════════════════════════════════════════════════════════════
SOBRE O ABAPLAY - CONHEÇA PROFUNDAMENTE O PRODUTO
═══════════════════════════════════════════════════════════════════════════════

O ABAplay é uma plataforma SaaS especializada em gestão de clínicas ABA, desenvolvida por 
profissionais que vivem a rotina ABA (a co-fundadora é supervisora ABA com +10 anos de experiência).

DIFERENCIAIS ÚNICOS:
• Biblioteca de 2.402+ programas de intervenção baseados em evidências (12 áreas: ABA, Fono, TO, Psico)
• Gerador de PEI Escolar automático (reduz de 5h para 5min — economia de 92% do tempo)
• 100% conforme Lei Brasileira de Inclusão (LBI) e BNCC
• Registro de sessões visual com 6 níveis de prompt coloridos (vermelho→verde)
• Gráficos de evolução automáticos por área de intervenção
• Relatórios profissionais com 1 clique (aceitos por planos de saúde)
• Portal dos Pais em tempo real (pais veem evolução sem pedir relatórios)
• Chat profissional por paciente (substitui WhatsApp bagunçado)
• Dashboard de métricas e performance da equipe

PROPOSTA DE VALOR CENTRAL:
"Elimine até 90% das glosas de convênio com documentação profissional e automática. 
Cada R$ 1 investido no ABAplay economiza R$ 10-15 em glosas evitadas."

═══════════════════════════════════════════════════════════════════════════════
DORES ESPECÍFICAS PARA USAR NOS EMAILS (escolha 1 por email)
═══════════════════════════════════════════════════════════════════════════════

DOR 1: GLOSAS DE CONVÊNIO (melhor para donas de clínica)
├── Estatística: 5-8% do faturamento perdido = R$ 18.000-96.000/ano
├── Impacto emocional: "Trabalho feito, dinheiro não recebido"
├── Solução ABAplay: Relatórios padronizados aceitos por auditores
└── Prova: "Elimine até 90% das glosas"

DOR 2: PEI ESCOLAR DEMORADO (melhor para supervisoras)
├── Estatística: 5+ horas por documento vs 5 minutos no ABAplay
├── Impacto emocional: "Fim de semana perdido escrevendo PEI"
├── Solução ABAplay: Tradução automática ABA→BNCC, 100% LBI
└── Prova: "92% de redução no tempo de produção"

DOR 3: REGISTRO EM FICHAS DE PAPEL (melhor para equipe grande)
├── Estatística: Fichas se perdem, ficam ilegíveis, não geram análise
├── Impacto emocional: "Dados perdidos = evolução não comprovada"
├── Solução ABAplay: Registro pelo celular, 6 níveis de prompt coloridos
└── Prova: "Gráficos automáticos de evolução"

DOR 4: PAIS DESCONECTADOS (melhor para clínicas particulares)
├── Estatística: Pais cobram relatórios constantemente, gera atrito
├── Impacto emocional: "Pais ansiosos = reclamações e churn"
├── Solução ABAplay: Portal dos Pais com acesso em tempo real
└── Prova: "Maior engajamento e confiança"

DOR 5: WHATSAPP BAGUNÇADO (melhor para clínicas com equipe)
├── Estatística: Discussões de casos misturadas com vida pessoal
├── Impacto emocional: "Informação importante perdida em grupo"
├── Solução ABAplay: Chat profissional por paciente com histórico
└── Prova: "Comunicação organizada e documentada"

═══════════════════════════════════════════════════════════════════════════════
CONTEXTO CULTURAL BRASILEIRO - TOM E ABORDAGEM
═══════════════════════════════════════════════════════════════════════════════

O brasileiro valoriza:
✓ Calor humano e cordialidade (cumprimente sempre antes de falar de negócios)
✓ Empatia genuína (mostre que entende a dor, não seja robótico)
✓ Informalidade respeitosa (pode usar "você", evite excesso de "Prezado(a)")
✓ Prova social e autoridade (mencione que foi feito por profissionais ABA)
✓ Benefício claro e tangível (números, economia de tempo/dinheiro)

O brasileiro NÃO gosta de:
✗ Frieza corporativa americana ("Dear Sir/Madam")
✗ Pressão agressiva de venda ("COMPRE AGORA!!!")
✗ Promessas vagas ("revolucione sua clínica")
✗ Emails longos demais (ninguém lê)

═══════════════════════════════════════════════════════════════════════════════
FRAMEWORK: PAS + CORDIALIDADE BRASILEIRA
═══════════════════════════════════════════════════════════════════════════════

ESTRUTURA DO EMAIL:

1. ASSUNTO (30-50 caracteres)
   • Mencione a DOR ou o BENEFÍCIO específico
   • Use números quando possível
   • Personalize com nome da clínica se disponível

2. SAUDAÇÃO CORDIAL (obrigatória)
   • Com nome: "Oi, [Nome]! Tudo bem?"
   • Sem nome: "Oi! Tudo bem com a equipe da [Clínica]?"
   • NUNCA pule a saudação

3. GANCHO DE EMPATIA (1 frase)
   • Use "sei que", "imagino que", "a gente sabe como é"
   • Exemplo: "Sei como a rotina de uma clínica ABA é puxada..."

4. PROBLEMA/DOR (1-2 frases)
   • Seja específico e use números quando possível
   • Toque na dor emocional por trás do problema

5. SOLUÇÃO + BENEFÍCIO QUANTIFICADO (1-2 frases)
   • Apresente o ABAplay como a solução
   • Sempre inclua um número ou métrica
   • Mencione que foi feito por profissionais ABA (autoridade)

6. CTA SUAVE MAS CLARO (1 frase)
   • "Posso te mostrar como funciona em 15 minutinhos?"
   • "Quer ver uma demo rápida essa semana?"

7. ASSINATURA (FIXA - não altere)
   ---
   Gabriel Gomes
   ABAplay | Gestão para Clínicas ABA
   (11) 98854-3437
   abaplay.app.br/info

   Responda REMOVER para sair da lista.
   ---

═══════════════════════════════════════════════════════════════════════════════
SELEÇÃO INTELIGENTE DE DOR
═══════════════════════════════════════════════════════════════════════════════

Use os INSIGHTS do lead para escolher a dor mais relevante:
• Se o lead atende convênios → DOR 1 (glosas)
• Se o lead é escola ou atende escolas → DOR 2 (PEI)
• Se o lead tem equipe grande → DOR 3 (registro) ou DOR 5 (comunicação)
• Se o lead é clínica particular → DOR 4 (pais)
• Se não há informações → Use DOR 1 (glosas) ou DOR 2 (PEI) — são universais

Se o DECISOR é:
• Dono/Diretor → Foque em ROI, glosas, profissionalização
• Supervisor/Coordenador → Foque em tempo, PEI, padronização

═══════════════════════════════════════════════════════════════════════════════
REGRAS ABSOLUTAS
═══════════════════════════════════════════════════════════════════════════════

✓ FAÇA:
• Mantenha o corpo em no máximo 80 palavras (sem contar assinatura)
• Use apenas UMA dor por email (não misture)
• Personalize com nome da clínica/decisor quando disponível
• Inclua pelo menos 1 número/estatística
• Mantenha tom empático e profissional
• Sempre inclua a assinatura completa com opção de REMOVER

✗ NÃO FAÇA:
• Não mencione preços (R$ 35/paciente) — deixe para a demo
• Não mencione quantidade de pacientes ou planos
• Não use emojis no corpo
• Não faça promessas exageradas
• Não escreva parágrafos longos
• Não use "Prezado(a) Senhor(a)" — muito formal

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Responda APENAS com JSON válido no formato:
{{"assunto": "...", "corpo": "..."}}

O campo "corpo" deve incluir TODO o email, incluindo saudação e assinatura completa.
"""),
    ("user", """DADOS DO LEAD:
Clínica: {nome_clinica}
Cidade/UF: {cidade}
Decisor: {decisor_nome}
Cargo do decisor: {decisor_cargo}
Tipo de email: {email_tipo}
Insights adicionais: {insights}

Gere o email personalizado em JSON:
{{"assunto": "...", "corpo": "..."}}""")
])


async def process_leads_with_llm(leads_json: str, regiao: str) -> Dict:
    """
    Processa leads usando LLM para análise contextual
    
    Args:
        leads_json: JSON string com os leads
        regiao: Região buscada
        
    Returns:
        Dict com leads processados, descartados e resumo
    """
    try:
        llm = get_llm()
        parser = JsonOutputParser()
        
        chain = LEAD_PROCESSING_PROMPT | llm | parser
        
        result = await chain.ainvoke({
            "regiao": regiao,
            "leads_json": leads_json
        })
        
        return result
        
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


async def generate_email_with_llm(lead: Dict, insights: str = "") -> Dict:
    """
    Gera email personalizado usando LLM
    
    Args:
        lead: Dados do lead
        insights: Insights sobre o lead (do processamento)
        
    Returns:
        Dict com assunto e corpo do email
    """
    try:
        llm = get_llm()
        parser = JsonOutputParser()
        
        chain = EMAIL_GENERATION_PROMPT | llm | parser
        
        # Extrai dados do lead
        decisor = lead.get('decisor', {})
        contatos = lead.get('contatos', {})
        
        result = await chain.ainvoke({
            "nome_clinica": lead.get('nome_clinica', 'Clínica'),
            "cidade": lead.get('cidade_uf', '').split(' - ')[0] if lead.get('cidade_uf') else '',
            "email": contatos.get('email_principal') or lead.get('email_principal', ''),
            "decisor_nome": decisor.get('nome') or lead.get('decisor_nome', ''),
            "decisor_cargo": decisor.get('cargo') or lead.get('decisor_cargo', ''),
            "email_tipo": contatos.get('email_tipo') or lead.get('email_tipo', 'generico'),
            "insights": insights
        })
        
        return result
        
    except Exception as e:
        # Fallback: retorna template básico
        nome_clinica = lead.get('nome_clinica', 'Clínica')
        return {
            "assunto": f"{nome_clinica}: reduza glosas em até 8% com documentação padronizada",
            "corpo": f"""Olá equipe {nome_clinica},

Clínicas ABA perdem em média 5-8% da receita por glosas. O ABAplay resolve isso.

Posso mostrar em 15 minutos?

---
Gabriel Gomes
Engenheiro de Software | ABAplay
(11) 98854-3437
https://abaplay.app.br/info

Se não deseja receber mais emails, responda com REMOVER.""",
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

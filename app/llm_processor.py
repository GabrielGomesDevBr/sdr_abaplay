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


# === Prompt para geração de email personalizado ===
EMAIL_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um copywriter especialista em vendas B2B para o setor de saúde.

Sua tarefa é criar um email de prospecção altamente personalizado para clínicas de terapia ABA.

O produto é o ABAplay:
- Plataforma de gestão para clínicas ABA
- Gera PEI escolar em 5 minutos (100% LBI/BNCC)
- Relatórios de evolução automáticos
- Reduz glosas de convênio em até 8%
- Economiza ~15h/semana em documentação
- R$ 35/paciente/mês, 7 dias grátis

Regras:
1. Assunto: máximo 60 caracteres, gerar curiosidade
2. Corpo: máximo 150 palavras, tom profissional mas amigável
3. Se tiver nome do decisor, personalizar a saudação
4. Incluir 1 dor específica do setor (glosas, PEI, tempo)
5. CTA claro: agendar 15 min de demonstração
6. Assinatura OBRIGATÓRIA com este formato exato:

---
Gabriel Gomes
Engenheiro de Software | ABAplay
(11) 98854-3437
https://abaplay.app.br/info

Se não deseja receber mais emails, responda com REMOVER.
---

Responda APENAS com JSON válido."""),
    ("user", """Crie um email personalizado para este lead:

Nome da clínica: {nome_clinica}
Cidade: {cidade}
Email: {email}
Nome do decisor: {decisor_nome}
Cargo do decisor: {decisor_cargo}
Tipo de email: {email_tipo}
Insights: {insights}

Retorne JSON:
{{
    "assunto": "assunto do email",
    "corpo": "corpo completo do email"
}}""")
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

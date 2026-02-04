"""
Teste de geração de emails com leads enriquecidos (v3.0)
Simula 3 envios com diferentes contextos e tons
"""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm_processor import generate_email_for_enriched_lead

# Leads de teste (do JSON fornecido)
TEST_LEADS = [
    # Lead 1: Tom CONSULTIVO (Autoridade Técnica)
    {
        "nome_clinica": "Grupo Conduzir",
        "cidade_uf": "Jundiaí - SP",
        "site": "https://www.grupoconduzir.com.br",
        "decisor": {
            "nome": "Dr. Fábio Coelho",
            "cargo": "Fundador / Diretor Executivo"
        },
        "contatos": {
            "email_principal": "contato@grupoconduzir.com.br",
            "email_tipo": "generico"
        },
        "contexto_abordagem": {
            "resumo_clinica": "Referência nacional em ABA e psiquiatria, com forte braço educacional (Conduzir Academy). Estrutura de grande porte focada em evidências científicas rigorosas.",
            "perfil_decisor": "Psiquiatra renomado e influenciador digital ativo (@dr.fabiocoelho), extremamente técnico e exigente com dados.",
            "gancho_personalizacao": "O perfil do Dr. Fábio valoriza 'ciência e dados' — destaque os gráficos de análise de comportamento do ABAplay como ferramenta de supervisão clínica.",
            "dor_provavel": "Gestão de uma 'clinica-escola' de grande porte exige relatórios complexos que sistemas genéricos não entregam.",
            "tom_sugerido": "consultivo"
        },
        "confianca": "alta"
    },
    
    # Lead 2: Tom ACOLHEDOR (Fundada por Mãe)
    {
        "nome_clinica": "Evoluir Brincando",
        "cidade_uf": "Jundiaí - SP",
        "site": "https://evoluirbrincando.com.br",
        "decisor": {
            "nome": "Dalila Calado & Siandra Mendes",
            "cargo": "Sócias-Fundadoras (Psicóloga / Pedagoga)"
        },
        "contatos": {
            "email_principal": "contato@evoluirbrincando.com.br",
            "email_tipo": "generico"
        },
        "contexto_abordagem": {
            "resumo_clinica": "Clínica transdisciplinar nascida da união de profissionais técnicas e mãe atípica. Forte posicionamento humanizado e acolhedor.",
            "perfil_decisor": "Dalila (Psicóloga) e Siandra (Pedagoga) combinam visão técnica com gestão. A história de 'mãe fundadora' permeia a cultura.",
            "gancho_personalizacao": "A origem da clínica valoriza a família — o portal de pais do ABAplay (com vídeos e gráficos simples) conecta diretamente com essa missão.",
            "dor_provavel": "Gestão de agendamentos e recados via WhatsApp consome tempo precioso que as sócias prefeririam dedicar ao atendimento.",
            "tom_sugerido": "acolhedor"
        },
        "confianca": "alta"
    },
    
    # Lead 3: Tom DIRETO (Rede em Expansão)
    {
        "nome_clinica": "CompletaMente ABA (Unidade Jundiaí)",
        "cidade_uf": "Jundiaí - SP",
        "site": "https://completamenteaba.com.br",
        "decisor": {
            "nome": None,
            "cargo": "Gestão Administrativa"
        },
        "contatos": {
            "email_principal": "agendas.jundiai@completamenteaba.com.br",
            "email_tipo": "departamento"
        },
        "contexto_abordagem": {
            "resumo_clinica": "Rede em expansão (Jundiaí, Caieiras, Taipas), operando como 'Núcleo de Desenvolvimento'. Modelo de negócio escalável com gestão centralizada.",
            "perfil_decisor": "Não identificado nominalmente, mas estrutura de rede sugere gerente administrativo ou operacional focado em eficiência.",
            "gancho_personalizacao": "Para redes multi-unidades, o controle centralizado de faturamento e produtividade da equipe é o maior atrativo.",
            "dor_provavel": "Desafio de padronizar a qualidade clínica e os processos administrativos entre as unidades de Jundiaí e Caieiras.",
            "tom_sugerido": "direto"
        },
        "confianca": "media"
    }
]


async def test_email_generation():
    """Testa a geração de emails para cada lead"""
    
    print("=" * 80)
    print("🧪 TESTE DE GERAÇÃO DE EMAILS - LEADS ENRIQUECIDOS v3.0")
    print("=" * 80)
    
    for i, lead in enumerate(TEST_LEADS, 1):
        tom = lead['contexto_abordagem']['tom_sugerido'].upper()
        nome = lead['nome_clinica']
        
        print(f"\n{'─' * 80}")
        print(f"📧 LEAD {i}/3: {nome}")
        print(f"   Tom: {tom} | Decisor: {lead['decisor'].get('nome') or 'Não identificado'}")
        print(f"{'─' * 80}")
        
        # Gera o email
        result = await generate_email_for_enriched_lead(lead)
        
        if 'error' in result:
            print(f"⚠️ ERRO: {result['error']}")
        
        print(f"\n📨 ASSUNTO: {result['assunto']}")
        print(f"\n📝 CORPO:")
        print("-" * 40)
        print(result['corpo'])
        print("-" * 40)
        
        # Conta palavras (sem assinatura)
        corpo_sem_assinatura = result['corpo'].split('---')[0]
        palavras = len(corpo_sem_assinatura.split())
        print(f"\n📊 Palavras (corpo): {palavras}")
    
    print("\n" + "=" * 80)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_email_generation())

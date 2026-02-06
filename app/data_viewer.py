"""
Módulo de visualização de dados do banco PostgreSQL.
Fornece interface visual para consultar leads, emails e campanhas.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import load_table_as_dataframe


def load_data_as_df(sheet_name: str, fresh: bool = True) -> pd.DataFrame:
    """
    Carrega dados de uma tabela do banco como DataFrame.

    Args:
        sheet_name: Nome da tabela ('leads', 'email_log', 'campaigns', 'blacklist')
        fresh: Mantido para compatibilidade (ignorado com SQL)

    Returns:
        DataFrame com os dados
    """
    return load_table_as_dataframe(sheet_name)


def render_kpi_cards(leads_df: pd.DataFrame, emails_df: pd.DataFrame, campaigns_df: pd.DataFrame):
    """Renderiza cards de KPIs principais"""

    # Calcula métricas
    total_leads = len(leads_df)
    total_emails_sent = len(emails_df[emails_df['status'] == 'sent']) if not emails_df.empty else 0
    total_campaigns = len(campaigns_df)

    # Emails hoje
    today = datetime.now().strftime('%Y-%m-%d')
    emails_today = 0
    if not emails_df.empty and 'sent_at' in emails_df.columns:
        emails_today = len(emails_df[emails_df['sent_at'].str.startswith(today, na=False) & (emails_df['status'] == 'sent')])

    # Taxa de sucesso
    total_attempts = len(emails_df) if not emails_df.empty else 0
    success_rate = (total_emails_sent / total_attempts * 100) if total_attempts > 0 else 0

    # Regiões únicas
    unique_regions = leads_df['cidade_uf'].nunique() if not leads_df.empty and 'cidade_uf' in leads_df.columns else 0

    # Renderiza cards em colunas
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric(
            label="Total de Leads",
            value=total_leads,
            delta=None
        )

    with col2:
        st.metric(
            label="Emails Enviados",
            value=total_emails_sent,
            delta=f"+{emails_today} hoje" if emails_today > 0 else None
        )

    with col3:
        st.metric(
            label="Campanhas",
            value=total_campaigns
        )

    with col4:
        st.metric(
            label="Taxa de Sucesso",
            value=f"{success_rate:.1f}%"
        )

    with col5:
        st.metric(
            label="Enviados Hoje",
            value=emails_today
        )

    with col6:
        st.metric(
            label="Regiões",
            value=unique_regions
        )


def render_leads_table(leads_df: pd.DataFrame):
    """Renderiza tabela de leads com filtros"""

    st.markdown("### Leads Cadastrados")

    if leads_df.empty:
        st.info("Nenhum lead cadastrado ainda.")
        return

    # Filtros
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Filtro por região
        regioes = ['Todas'] + sorted(leads_df['cidade_uf'].dropna().unique().tolist())
        regiao_filter = st.selectbox("Região", regioes, key="leads_regiao")

    with col2:
        # Filtro por confiança
        confiancas = ['Todas'] + sorted(leads_df['confianca'].dropna().unique().tolist())
        confianca_filter = st.selectbox("Confiança", confiancas, key="leads_confianca")

    with col3:
        # Filtro por tom sugerido
        tons = ['Todos']
        if 'tom_sugerido' in leads_df.columns:
            tons += sorted(leads_df['tom_sugerido'].dropna().unique().tolist())
        tom_filter = st.selectbox("Tom Sugerido", tons, key="leads_tom")

    with col4:
        # Busca por nome
        search = st.text_input("Buscar por nome", key="leads_search", placeholder="Digite para buscar...")

    # Aplica filtros
    filtered_df = leads_df.copy()

    if regiao_filter != 'Todas':
        filtered_df = filtered_df[filtered_df['cidade_uf'] == regiao_filter]

    if confianca_filter != 'Todas':
        filtered_df = filtered_df[filtered_df['confianca'] == confianca_filter]

    if tom_filter != 'Todos' and 'tom_sugerido' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['tom_sugerido'] == tom_filter]

    if search:
        filtered_df = filtered_df[
            filtered_df['nome_clinica'].str.contains(search, case=False, na=False) |
            filtered_df['email_principal'].str.contains(search, case=False, na=False)
        ]

    # Colunas para exibir
    display_cols = [
        'nome_clinica', 'cidade_uf', 'email_principal', 'telefone',
        'decisor_nome', 'decisor_cargo', 'confianca', 'tom_sugerido'
    ]
    display_cols = [col for col in display_cols if col in filtered_df.columns]

    # Renomeia colunas para exibição
    col_rename = {
        'nome_clinica': 'Clínica',
        'cidade_uf': 'Cidade/UF',
        'email_principal': 'Email',
        'telefone': 'Telefone',
        'decisor_nome': 'Decisor',
        'decisor_cargo': 'Cargo',
        'confianca': 'Confiança',
        'tom_sugerido': 'Tom'
    }

    display_df = filtered_df[display_cols].rename(columns=col_rename)

    # Exibe contagem
    st.caption(f"Mostrando {len(display_df)} de {len(leads_df)} leads")

    # Tabela interativa
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        height=400
    )

    # Expander com detalhes completos
    with st.expander("Ver detalhes completos de um lead"):
        if not filtered_df.empty:
            lead_names = filtered_df['nome_clinica'].tolist()
            selected_lead = st.selectbox("Selecione um lead", lead_names, key="lead_detail_select")

            if selected_lead:
                lead_data = filtered_df[filtered_df['nome_clinica'] == selected_lead].iloc[0]

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Dados de Contato**")
                    st.write(f"**Email:** {lead_data.get('email_principal', 'N/A')}")
                    st.write(f"**Telefone:** {lead_data.get('telefone', 'N/A')}")
                    st.write(f"**WhatsApp:** {lead_data.get('whatsapp', 'N/A')}")
                    st.write(f"**Instagram:** {lead_data.get('instagram', 'N/A')}")
                    st.write(f"**Site:** {lead_data.get('site', 'N/A')}")

                with col2:
                    st.markdown("**Dados do Decisor**")
                    st.write(f"**Nome:** {lead_data.get('decisor_nome', 'N/A')}")
                    st.write(f"**Cargo:** {lead_data.get('decisor_cargo', 'N/A')}")
                    st.write(f"**LinkedIn:** {lead_data.get('decisor_linkedin', 'N/A')}")

                st.markdown("**Contexto de Abordagem**")
                st.write(f"**Resumo:** {lead_data.get('resumo_clinica', 'N/A')}")
                st.write(f"**Dor Provável:** {lead_data.get('dor_provavel', 'N/A')}")
                st.write(f"**Gancho:** {lead_data.get('gancho_personalizacao', 'N/A')}")


def render_emails_table(emails_df: pd.DataFrame):
    """Renderiza tabela de histórico de emails"""

    st.markdown("### Histórico de Emails")

    if emails_df.empty:
        st.info("Nenhum email enviado ainda.")
        return

    # Filtros
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Filtro por status
        status_options = ['Todos'] + sorted(emails_df['status'].dropna().unique().tolist())
        status_filter = st.selectbox("Status", status_options, key="emails_status")

    with col2:
        # Filtro por data
        date_options = ['Todos os dias', 'Hoje', 'Últimos 7 dias', 'Últimos 30 dias']
        date_filter = st.selectbox("Período", date_options, key="emails_date")

    with col3:
        # Busca por email
        email_search = st.text_input("Buscar por email", key="emails_search", placeholder="Digite para buscar...")

    with col4:
        # Ordenação
        sort_options = ['Mais recentes', 'Mais antigos']
        sort_order = st.selectbox("Ordenar por", sort_options, key="emails_sort")

    # Aplica filtros
    filtered_df = emails_df.copy()

    if status_filter != 'Todos':
        filtered_df = filtered_df[filtered_df['status'] == status_filter]

    if date_filter != 'Todos os dias':
        today = datetime.now()
        if date_filter == 'Hoje':
            date_str = today.strftime('%Y-%m-%d')
            filtered_df = filtered_df[filtered_df['sent_at'].str.startswith(date_str, na=False)]
        elif date_filter == 'Últimos 7 dias':
            week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            filtered_df = filtered_df[filtered_df['sent_at'] >= week_ago]
        elif date_filter == 'Últimos 30 dias':
            month_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            filtered_df = filtered_df[filtered_df['sent_at'] >= month_ago]

    if email_search:
        filtered_df = filtered_df[
            filtered_df['email_to'].str.contains(email_search, case=False, na=False) |
            filtered_df['subject'].str.contains(email_search, case=False, na=False)
        ]

    # Ordenação
    if 'sent_at' in filtered_df.columns and not filtered_df.empty:
        ascending = sort_order == 'Mais antigos'
        filtered_df = filtered_df.sort_values('sent_at', ascending=ascending)

    # Colunas para exibir
    display_cols = ['email_to', 'subject', 'status', 'sent_at', 'resend_id']
    display_cols = [col for col in display_cols if col in filtered_df.columns]

    # Renomeia colunas
    col_rename = {
        'email_to': 'Destinatário',
        'subject': 'Assunto',
        'status': 'Status',
        'sent_at': 'Enviado em',
        'resend_id': 'ID Resend'
    }

    display_df = filtered_df[display_cols].rename(columns=col_rename)

    # Formata status com cores
    def style_status(val):
        if val == 'sent':
            return 'background-color: #c6f6d5; color: #22543d'
        elif val == 'failed':
            return 'background-color: #fed7d7; color: #822727'
        elif val == 'pending':
            return 'background-color: #fefcbf; color: #744210'
        return ''

    # Exibe contagem
    st.caption(f"Mostrando {len(display_df)} de {len(emails_df)} emails")

    # Estatísticas rápidas
    if not filtered_df.empty:
        sent_count = len(filtered_df[filtered_df['status'] == 'sent'])
        failed_count = len(filtered_df[filtered_df['status'] == 'failed'])
        pending_count = len(filtered_df[filtered_df['status'] == 'pending'])

        stats_col1, stats_col2, stats_col3 = st.columns(3)
        stats_col1.success(f"Enviados: {sent_count}")
        stats_col2.error(f"Falharam: {failed_count}")
        stats_col3.warning(f"Pendentes: {pending_count}")

    # Tabela
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        height=400
    )


def render_campaigns_table(campaigns_df: pd.DataFrame):
    """Renderiza tabela de campanhas"""

    st.markdown("### Campanhas")

    if campaigns_df.empty:
        st.info("Nenhuma campanha criada ainda.")
        return

    # Colunas para exibir
    display_cols = ['name', 'region', 'status', 'total_leads', 'emails_sent', 'emails_failed', 'created_at']
    display_cols = [col for col in display_cols if col in campaigns_df.columns]

    # Renomeia colunas
    col_rename = {
        'name': 'Nome',
        'region': 'Região',
        'status': 'Status',
        'total_leads': 'Total Leads',
        'emails_sent': 'Enviados',
        'emails_failed': 'Falharam',
        'created_at': 'Criado em'
    }

    display_df = campaigns_df[display_cols].rename(columns=col_rename)

    # Ordena por data de criação (mais recentes primeiro)
    if 'Criado em' in display_df.columns:
        display_df = display_df.sort_values('Criado em', ascending=False)

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        height=300
    )


def render_charts(leads_df: pd.DataFrame, emails_df: pd.DataFrame):
    """Renderiza gráficos de análise"""

    st.markdown("### Análise Visual")

    col1, col2 = st.columns(2)

    with col1:
        # Gráfico de leads por região
        if not leads_df.empty and 'cidade_uf' in leads_df.columns:
            st.markdown("**Leads por Região**")
            region_counts = leads_df['cidade_uf'].value_counts().head(10)
            st.bar_chart(region_counts)
        else:
            st.info("Sem dados de região para exibir")

    with col2:
        # Gráfico de emails por dia
        if not emails_df.empty and 'sent_at' in emails_df.columns:
            st.markdown("**Emails por Dia (últimos 30 dias)**")

            # Filtra apenas emails enviados com sucesso
            sent_emails = emails_df[emails_df['status'] == 'sent'].copy()

            if not sent_emails.empty:
                # Extrai data do timestamp
                sent_emails['date'] = sent_emails['sent_at'].str[:10]

                # Filtra últimos 30 dias
                today = datetime.now()
                month_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                sent_emails = sent_emails[sent_emails['date'] >= month_ago]

                if not sent_emails.empty:
                    daily_counts = sent_emails['date'].value_counts().sort_index()
                    st.line_chart(daily_counts)
                else:
                    st.info("Sem emails nos últimos 30 dias")
            else:
                st.info("Sem emails enviados para exibir")
        else:
            st.info("Sem dados de emails para exibir")

    # Segunda linha de gráficos
    col3, col4 = st.columns(2)

    with col3:
        # Gráfico de confiança dos leads
        if not leads_df.empty and 'confianca' in leads_df.columns:
            st.markdown("**Leads por Nível de Confiança**")
            conf_counts = leads_df['confianca'].value_counts()
            st.bar_chart(conf_counts)

    with col4:
        # Gráfico de tom sugerido
        if not leads_df.empty and 'tom_sugerido' in leads_df.columns:
            st.markdown("**Leads por Tom Sugerido**")
            tom_counts = leads_df['tom_sugerido'].value_counts()
            st.bar_chart(tom_counts)


def render_blacklist_table():
    """Renderiza tabela de blacklist"""

    st.markdown("### Blacklist (Emails Bloqueados)")

    blacklist_df = load_data_as_df('blacklist')

    if blacklist_df.empty:
        st.info("Nenhum email na blacklist.")
        return

    # Renomeia colunas
    col_rename = {
        'email': 'Email',
        'reason': 'Motivo',
        'added_at': 'Adicionado em'
    }

    display_cols = [col for col in col_rename.keys() if col in blacklist_df.columns]
    display_df = blacklist_df[display_cols].rename(columns=col_rename)

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        height=200
    )


def render_data_viewer():
    """
    Renderiza a página completa de visualização de dados.
    Chamada a partir do main.py.
    """

    st.markdown("## Visualização de Dados")
    st.caption("Consulte leads, emails e campanhas diretamente na aplicação")

    # Botão de refresh
    col_refresh, col_spacer = st.columns([1, 5])
    with col_refresh:
        if st.button("Atualizar Dados", type="primary"):
            st.rerun()

    # Carrega dados
    with st.spinner("Carregando dados..."):
        leads_df = load_data_as_df('leads')
        emails_df = load_data_as_df('email_log')
        campaigns_df = load_data_as_df('campaigns')

    # KPIs
    render_kpi_cards(leads_df, emails_df, campaigns_df)

    st.divider()

    # Sub-tabs para organizar conteúdo
    subtab1, subtab2, subtab3, subtab4, subtab5 = st.tabs([
        "Leads",
        "Emails Enviados",
        "Campanhas",
        "Gráficos",
        "Blacklist"
    ])

    with subtab1:
        render_leads_table(leads_df)

    with subtab2:
        render_emails_table(emails_df)

    with subtab3:
        render_campaigns_table(campaigns_df)

    with subtab4:
        render_charts(leads_df, emails_df)

    with subtab5:
        render_blacklist_table()

    # Rodapé com última atualização
    st.divider()
    st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

"""
Módulo de visualização de dados do banco PostgreSQL.
Fornece interface visual interativa com AgGrid e Plotly.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import load_table_as_dataframe


# ═══════════════════════════════════════════════════════════════════════════════
# PLOTLY THEME
# ═══════════════════════════════════════════════════════════════════════════════

PLOTLY_COLORS = {
    'primary': '#667eea',
    'secondary': '#764ba2',
    'success': '#48bb78',
    'warning': '#ecc94b',
    'error': '#fc8181',
    'info': '#63b3ed',
    'gradient': ['#667eea', '#764ba2', '#48bb78', '#ecc94b', '#fc8181', '#63b3ed'],
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Inter, sans-serif', size=12),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
)


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


# ═══════════════════════════════════════════════════════════════════════════════
# KPI CARDS
# ═══════════════════════════════════════════════════════════════════════════════

def render_kpi_cards(leads_df: pd.DataFrame, emails_df: pd.DataFrame, campaigns_df: pd.DataFrame):
    """Renderiza cards de KPIs principais com estilo moderno"""

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

    # Renderiza com componentes nativos do Streamlit (compatível com dark/light theme)
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric(
            label="📋 Total de Leads",
            value=total_leads,
        )

    with col2:
        st.metric(
            label="✅ Emails Enviados",
            value=total_emails_sent,
            delta=f"+{emails_today} hoje" if emails_today > 0 else None,
        )

    with col3:
        st.metric(
            label="🎯 Campanhas",
            value=total_campaigns,
        )

    with col4:
        st.metric(
            label="📊 Taxa Sucesso",
            value=f"{success_rate:.0f}%",
        )

    with col5:
        st.metric(
            label="📧 Enviados Hoje",
            value=emails_today,
        )

    with col6:
        st.metric(
            label="🌍 Regiões",
            value=unique_regions,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AGGRID TABLES
# ═══════════════════════════════════════════════════════════════════════════════

def _render_aggrid_table(df: pd.DataFrame, key: str, height: int = 400, selection: bool = False):
    """
    Renderiza uma tabela interativa com AgGrid.
    Fallback para st.dataframe se AgGrid não estiver disponível.
    """
    if not AGGRID_AVAILABLE or df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)
        return None

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        filterable=True,
        sortable=True,
        resizable=True,
        wrapText=True,
        autoHeight=True,
        minWidth=80,
    )
    gb.configure_grid_options(
        enableQuickFilter=True,
        domLayout='normal',
    )
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)

    if selection:
        gb.configure_selection('multiple', use_checkbox=True, header_checkbox=True)

    grid_options = gb.build()

    response = AgGrid(
        df,
        gridOptions=grid_options,
        height=height,
        update_mode=GridUpdateMode.SELECTION_CHANGED if selection else GridUpdateMode.NO_UPDATE,
        fit_columns_on_grid_load=True,
        theme='streamlit',
        key=key,
        allow_unsafe_jscode=False,
    )
    return response


def render_leads_table(leads_df: pd.DataFrame):
    """Renderiza tabela de leads com AgGrid interativo"""

    st.markdown("### 📋 Leads Cadastrados")

    if leads_df.empty:
        st.info("Nenhum lead cadastrado ainda.")
        return

    # Busca rápida (filtro global)
    search = st.text_input("🔍 Busca rápida (nome, email, cidade...)", key="leads_quick_search", placeholder="Digite para filtrar...")

    # Colunas para exibir
    display_cols = [
        'nome_clinica', 'cidade_uf', 'email_principal', 'telefone',
        'decisor_nome', 'decisor_cargo', 'confianca', 'tom_sugerido'
    ]
    display_cols = [col for col in display_cols if col in leads_df.columns]

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

    display_df = leads_df[display_cols].rename(columns=col_rename)

    # Aplica busca rápida se digitou algo
    if search:
        mask = display_df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        display_df = display_df[mask]

    st.caption(f"Mostrando {len(display_df)} de {len(leads_df)} leads")

    _render_aggrid_table(display_df, key="leads_grid", height=450)

    # Expander com detalhes completos
    with st.expander("🔎 Ver detalhes completos de um lead"):
        if not leads_df.empty:
            lead_names = leads_df['nome_clinica'].tolist()
            selected_lead = st.selectbox("Selecione um lead", lead_names, key="lead_detail_select")

            if selected_lead:
                lead_data = leads_df[leads_df['nome_clinica'] == selected_lead].iloc[0]

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
    """Renderiza tabela de histórico de emails com AgGrid"""

    st.markdown("### 📧 Histórico de Emails")

    if emails_df.empty:
        st.info("Nenhum email enviado ainda.")
        return

    # Busca rápida
    search = st.text_input("🔍 Busca rápida (email, assunto...)", key="emails_quick_search", placeholder="Digite para filtrar...")

    # Colunas para exibir
    display_cols = ['email_to', 'subject', 'status', 'sent_at', 'resend_id']
    display_cols = [col for col in display_cols if col in emails_df.columns]

    # Renomeia colunas
    col_rename = {
        'email_to': 'Destinatário',
        'subject': 'Assunto',
        'status': 'Status',
        'sent_at': 'Enviado em',
        'resend_id': 'ID Resend'
    }

    display_df = emails_df[display_cols].rename(columns=col_rename)

    # Aplica busca rápida
    if search:
        mask = display_df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        display_df = display_df[mask]

    # Estatísticas rápidas
    if not emails_df.empty:
        sent_count = len(emails_df[emails_df['status'] == 'sent'])
        failed_count = len(emails_df[emails_df['status'] == 'failed'])
        pending_count = len(emails_df[emails_df['status'] == 'pending'])

        stat_cols = st.columns(4)
        stat_cols[0].metric("📊 Total", len(display_df))
        stat_cols[1].metric("✅ Enviados", sent_count)
        stat_cols[2].metric("❌ Falharam", failed_count)
        stat_cols[3].metric("⏳ Pendentes", pending_count)

    _render_aggrid_table(display_df, key="emails_grid", height=450)


# ═══════════════════════════════════════════════════════════════════════════════
# CAMPAIGNS TABLE (MODERN)
# ═══════════════════════════════════════════════════════════════════════════════

def render_campaigns_table(campaigns_df: pd.DataFrame):
    """Renderiza tabela de campanhas com cards visuais e estatísticas"""

    st.markdown("### 🎯 Campanhas")

    if campaigns_df.empty:
        st.info("Nenhuma campanha criada ainda.")
        return

    # Ordena por data de criação (mais recentes primeiro)
    if 'created_at' in campaigns_df.columns:
        campaigns_df = campaigns_df.sort_values('created_at', ascending=False)

    # Renderiza cada campanha como um card visual
    for _, campaign in campaigns_df.iterrows():
        name = campaign.get('name', 'Sem nome')
        region = campaign.get('region', 'N/A')
        status = campaign.get('status', 'N/A')
        total_leads = int(campaign.get('total_leads', 0) or 0)
        emails_sent = int(campaign.get('emails_sent', 0) or 0)
        emails_failed = int(campaign.get('emails_failed', 0) or 0)
        created_at = campaign.get('created_at', '')

        # Formata data
        if created_at:
            try:
                if isinstance(created_at, str):
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    dt = created_at
                created_display = dt.strftime('%d/%m/%Y %H:%M')
            except Exception:
                created_display = str(created_at)[:16]
        else:
            created_display = 'N/A'

        # Taxa de sucesso da campanha
        taxa = (emails_sent / total_leads * 100) if total_leads > 0 else 0

        # Cor do status
        status_color = '#48bb78' if status == 'completed' else '#ecc94b' if status == 'active' else '#718096'

        with st.container():
            cols = st.columns([3, 1.5, 1.5, 1.5, 1.5])

            with cols[0]:
                st.markdown(f"**{name}**")
                st.caption(f"📍 {region} • 📅 {created_display}")

            with cols[1]:
                st.metric("Leads", total_leads)

            with cols[2]:
                st.metric("Enviados", emails_sent)

            with cols[3]:
                st.metric("Falhas", emails_failed)

            with cols[4]:
                st.metric("Taxa", f"{taxa:.0f}%")

            st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# PLOTLY CHARTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_charts(leads_df: pd.DataFrame, emails_df: pd.DataFrame):
    """Renderiza gráficos interativos com Plotly"""

    st.markdown("### 📊 Análise Visual")

    col1, col2 = st.columns(2)

    with col1:
        # Gráfico de leads por região (barras horizontais Plotly)
        if not leads_df.empty and 'cidade_uf' in leads_df.columns:
            region_counts = leads_df['cidade_uf'].value_counts().head(10).reset_index()
            region_counts.columns = ['Região', 'Leads']

            fig = px.bar(
                region_counts,
                x='Leads', y='Região',
                orientation='h',
                title='🌍 Top 10 Regiões por Leads',
                color='Leads',
                color_continuous_scale=['#667eea', '#764ba2'],
            )
            fig.update_layout(**PLOTLY_LAYOUT, height=350, showlegend=False)
            fig.update_traces(marker_line_width=0)
            fig.update_coloraxes(showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de região para exibir")

    with col2:
        # Gráfico de emails por dia (série temporal Plotly)
        if not emails_df.empty and 'sent_at' in emails_df.columns:
            sent_emails = emails_df[emails_df['status'] == 'sent'].copy()

            if not sent_emails.empty:
                sent_emails['date'] = sent_emails['sent_at'].str[:10]

                today = datetime.now()
                month_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                sent_emails = sent_emails[sent_emails['date'] >= month_ago]

                if not sent_emails.empty:
                    daily_counts = sent_emails['date'].value_counts().sort_index().reset_index()
                    daily_counts.columns = ['Data', 'Emails']

                    fig = px.area(
                        daily_counts,
                        x='Data', y='Emails',
                        title='📈 Emails Enviados (últimos 30 dias)',
                        color_discrete_sequence=[PLOTLY_COLORS['primary']],
                    )
                    fig.update_layout(**PLOTLY_LAYOUT, height=350)
                    fig.update_traces(
                        fillcolor='rgba(102,126,234,0.15)',
                        line_color=PLOTLY_COLORS['primary'],
                        line_width=2,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Sem emails nos últimos 30 dias")
            else:
                st.info("Sem emails enviados para exibir")
        else:
            st.info("Sem dados de emails para exibir")

    # Segunda linha de gráficos
    col3, col4 = st.columns(2)

    with col3:
        # Gráfico de donut: Status dos emails
        if not emails_df.empty and 'status' in emails_df.columns:
            status_counts = emails_df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Quantidade']

            color_map = {'sent': '#48bb78', 'failed': '#fc8181', 'pending': '#ecc94b'}
            colors = [color_map.get(s, '#cbd5e0') for s in status_counts['Status']]

            fig = go.Figure(data=[go.Pie(
                labels=status_counts['Status'],
                values=status_counts['Quantidade'],
                hole=0.55,
                marker=dict(colors=colors, line=dict(color='white', width=2)),
                textinfo='label+percent',
                textfont_size=12,
            )])
            fig.update_layout(
                **PLOTLY_LAYOUT,
                title='📊 Status dos Emails',
                height=350,
                annotations=[dict(text=str(len(emails_df)), x=0.5, y=0.5, font_size=28, font_weight='bold', showarrow=False)],
            )
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        # Gráfico de confiança dos leads (donut)
        if not leads_df.empty and 'confianca' in leads_df.columns:
            conf_counts = leads_df['confianca'].value_counts().reset_index()
            conf_counts.columns = ['Confiança', 'Quantidade']

            color_map_conf = {'alta': '#48bb78', 'media': '#ecc94b', 'baixa': '#fc8181'}
            colors_conf = [color_map_conf.get(c, '#cbd5e0') for c in conf_counts['Confiança']]

            fig = go.Figure(data=[go.Pie(
                labels=conf_counts['Confiança'],
                values=conf_counts['Quantidade'],
                hole=0.55,
                marker=dict(colors=colors_conf, line=dict(color='white', width=2)),
                textinfo='label+percent',
                textfont_size=12,
            )])
            fig.update_layout(
                **PLOTLY_LAYOUT,
                title='🎯 Confiança dos Leads',
                height=350,
                annotations=[dict(text=str(len(leads_df)), x=0.5, y=0.5, font_size=28, font_weight='bold', showarrow=False)],
            )
            st.plotly_chart(fig, use_container_width=True)


def render_blacklist_table():
    """Renderiza tabela de blacklist com AgGrid"""

    st.markdown("### 🚫 Blacklist (Emails Bloqueados)")

    blacklist_df = load_data_as_df('blacklist')

    if blacklist_df.empty:
        st.info("Nenhum email na blacklist.")
        return

    # Busca rápida
    search = st.text_input("🔍 Busca rápida", key="blacklist_quick_search", placeholder="Buscar email...")

    # Renomeia colunas
    col_rename = {
        'email': 'Email',
        'reason': 'Motivo',
        'added_at': 'Adicionado em'
    }

    display_cols = [col for col in col_rename.keys() if col in blacklist_df.columns]
    display_df = blacklist_df[display_cols].rename(columns=col_rename)

    if search:
        mask = display_df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        display_df = display_df[mask]

    st.caption(f"Total: {len(display_df)} emails bloqueados")
    _render_aggrid_table(display_df, key="blacklist_grid", height=250)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def render_data_viewer():
    """
    Renderiza a página completa de visualização de dados.
    Chamada a partir do main.py.
    """

    st.markdown("## 📈 Dashboard de Dados")
    st.caption("Tabelas interativas com filtro, ordenação e busca • Gráficos Plotly responsivos")

    # Botão de refresh
    col_refresh, col_spacer = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Atualizar Dados", type="primary"):
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
        "📋 Leads",
        "📧 Emails Enviados",
        "🎯 Campanhas",
        "📊 Gráficos",
        "🚫 Blacklist"
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

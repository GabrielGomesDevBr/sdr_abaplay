"""
Módulo para visualização do histórico de emails enviados.
Fornece interface completa com filtros, paginação e exportação.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_all_sent_emails, get_campaign_summary


def render_email_history():
    """Renderiza página completa de histórico de emails enviados."""
    st.markdown("## 📧 Histórico de Emails Enviados")

    # === Filtros ===
    with st.expander("🔍 Filtros", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            status_filter = st.selectbox(
                "Status",
                options=["Todos", "sent", "failed", "pending"],
                format_func=lambda x: {
                    "Todos": "📊 Todos",
                    "sent": "✅ Enviados",
                    "failed": "❌ Falhou",
                    "pending": "⏳ Pendente"
                }.get(x, x)
            )

        with col2:
            # Carrega campanhas para filtro
            campaigns = get_campaign_summary()
            campaign_options = ["Todas"] + [c['name'] for c in campaigns if c.get('name')]
            campaign_ids = {c['name']: c['id'] for c in campaigns if c.get('name')}

            campaign_filter = st.selectbox("Campanha", options=campaign_options)

        with col3:
            date_from = st.date_input(
                "De",
                value=datetime.now() - timedelta(days=30),
                format="DD/MM/YYYY"
            )

        with col4:
            date_to = st.date_input(
                "Até",
                value=datetime.now(),
                format="DD/MM/YYYY"
            )

    # === Paginação ===
    if 'email_page' not in st.session_state:
        st.session_state.email_page = 0

    page_size = 50
    offset = st.session_state.email_page * page_size

    # Prepara filtros
    status = None if status_filter == "Todos" else status_filter
    campaign_id = campaign_ids.get(campaign_filter) if campaign_filter != "Todas" else None

    # Busca dados
    emails, total = get_all_sent_emails(
        limit=page_size,
        offset=offset,
        status=status,
        campaign_id=campaign_id,
        date_from=date_from.isoformat() if date_from else None,
        date_to=(date_to + timedelta(days=1)).isoformat() if date_to else None
    )

    total_pages = (total + page_size - 1) // page_size

    # === Métricas ===
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        st.metric("📊 Total (filtrado)", total)
    with mcol2:
        sent_count = sum(1 for e in emails if e.get('status') == 'sent')
        st.metric("✅ Enviados (página)", sent_count)
    with mcol3:
        failed_count = sum(1 for e in emails if e.get('status') == 'failed')
        st.metric("❌ Falharam (página)", failed_count)
    with mcol4:
        st.metric("📄 Página", f"{st.session_state.email_page + 1}/{max(1, total_pages)}")

    st.divider()

    # === Tabela de emails ===
    if not emails:
        st.info("📭 Nenhum email encontrado com os filtros selecionados.")
        return

    # Monta DataFrame para tabela interativa
    rows = []
    for email in emails:
        sent_at = email.get('sent_at', '')
        if sent_at:
            try:
                if isinstance(sent_at, str):
                    dt = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                else:
                    dt = sent_at
                sent_at_display = dt.strftime('%d/%m/%Y %H:%M')
            except Exception:
                sent_at_display = str(sent_at)[:16]
        else:
            sent_at_display = "N/A"

        status_emoji = {'sent': '✅', 'failed': '❌', 'pending': '⏳'}.get(email.get('status', ''), '❔')

        rows.append({
            'Status': f"{status_emoji} {email.get('status', 'N/A')}",
            'Clínica': email.get('nome_clinica', 'N/A'),
            'Email': email.get('email_to', 'N/A'),
            'Assunto': (email.get('subject', 'N/A') or 'N/A')[:60],
            'Campanha': email.get('campaign_name', 'N/A'),
            'Data': sent_at_display,
        })

    df = pd.DataFrame(rows)

    # Busca rápida na tabela
    search = st.text_input("🔍 Busca rápida nesta página", key="email_hist_search", placeholder="Buscar por clínica, email...")
    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        df = df[mask]

    # Renderiza AgGrid ou fallback
    if AGGRID_AVAILABLE and not df.empty:
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_default_column(filterable=True, sortable=True, resizable=True, wrapText=True, autoHeight=True)
        gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)
        gb.configure_grid_options(enableQuickFilter=True)
        grid_options = gb.build()

        AgGrid(
            df,
            gridOptions=grid_options,
            height=450,
            fit_columns_on_grid_load=True,
            theme='streamlit',
            key="email_history_grid",
        )
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, height=450)

    # === Expanders para ver email completo ===
    with st.expander("👁️ Ver corpo de um email"):
        if emails:
            email_options = [f"{e.get('nome_clinica', 'N/A')} — {e.get('email_to', 'N/A')}" for e in emails]
            selected_idx = st.selectbox("Selecione um email", range(len(email_options)), format_func=lambda i: email_options[i], key="email_detail_sel")

            if selected_idx is not None:
                email = emails[selected_idx]
                st.markdown(f"**Assunto:** {email.get('subject', 'N/A')}")
                st.markdown("**Corpo:**")
                body = email.get('body_html', '') or email.get('body', '')
                if body:
                    st.text_area("Corpo do email", value=body, height=200, disabled=True, label_visibility="collapsed")
                else:
                    st.info("Corpo do email não disponível")

                if email.get('error_message'):
                    st.error(f"❌ Erro: {email.get('error_message')}")

                if email.get('resend_id'):
                    st.caption(f"🆔 Resend ID: {email.get('resend_id')}")

    # === Controles de paginação ===
    pcol1, pcol2, pcol3, pcol4 = st.columns([2, 1, 1, 2])

    with pcol2:
        if st.button("⬅️ Anterior", disabled=st.session_state.email_page == 0):
            st.session_state.email_page -= 1
            st.rerun()

    with pcol3:
        if st.button("Próxima ➡️", disabled=st.session_state.email_page >= total_pages - 1):
            st.session_state.email_page += 1
            st.rerun()

    # === Exportar CSV ===
    st.divider()

    if st.button("📥 Exportar todos os emails para CSV"):
        # Busca todos sem paginação para export
        all_emails, _ = get_all_sent_emails(
            limit=10000,
            offset=0,
            status=status,
            campaign_id=campaign_id,
            date_from=date_from.isoformat() if date_from else None,
            date_to=(date_to + timedelta(days=1)).isoformat() if date_to else None
        )

        if all_emails:
            df_export = pd.DataFrame(all_emails)
            # Seleciona colunas relevantes
            export_cols = ['email_to', 'nome_clinica', 'subject', 'status', 'sent_at', 'campaign_name', 'error_message']
            export_cols = [c for c in export_cols if c in df_export.columns]
            df_export = df_export[export_cols]

            csv = df_export.to_csv(index=False)
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv,
                file_name=f"emails_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("Nenhum email para exportar")

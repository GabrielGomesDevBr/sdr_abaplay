"""
Interface Streamlit para Automação de Envio de Emails ABAplay
"""
import streamlit as st
import time
import json
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DAILY_EMAIL_LIMIT, WORK_HOURS_START, WORK_HOURS_END
from app.database import (
    init_database, create_campaign, update_campaign_stats,
    insert_lead, get_leads_by_campaign, get_email_log_by_campaign,
    get_campaign, add_to_blacklist, get_blacklist, check_leads_for_duplicates,
    get_setting, set_setting, update_lead_status
)
from app.lead_processor import (
    parse_leads_json, process_leads, get_lead_display_info, calculate_lead_score
)
from app.delay_manager import (
    get_smart_delay, can_send_email, get_remaining_emails_today,
    estimate_completion_time, format_delay_for_display, is_within_work_hours
)
from app.email_sender import send_email, test_connection, get_sender_info, generate_email_preview
from app.template_engine import preview_email, personalize_template
from app.report_generator import generate_campaign_report, generate_quick_summary
from app.llm_processor import (
    process_leads_with_llm_sync, generate_email_with_llm_sync, test_llm_connection
)
from app.data_viewer import render_data_viewer
from app.ui_components import (
    inject_custom_css, render_header, render_metric_card, render_lead_card,
    render_progress_tracker, render_empty_state, render_success_message,
    render_info_box, render_status_bar, render_compact_metric
)


# === Persistência de Configurações (via banco SQL) ===

def load_user_config() -> dict:
    """Carrega configurações do usuário do banco"""
    try:
        limit = get_setting('daily_email_limit', str(DAILY_EMAIL_LIMIT))
        return {"daily_limit": int(limit)}
    except Exception:
        return {"daily_limit": DAILY_EMAIL_LIMIT}


def save_user_config(config: dict):
    """Salva configurações do usuário no banco"""
    try:
        if 'daily_limit' in config:
            set_setting('daily_email_limit', str(config['daily_limit']))
    except Exception:
        pass


# Configuração da página
st.set_page_config(
    page_title="ABAplay Email Automation",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Injeta CSS do design system
inject_custom_css()


# Session state defaults - facilita manutenção
DEFAULT_SESSION_STATE = {
    'campaign_id': None,
    'valid_leads': [],
    'discarded_leads': [],
    'sending_active': False,
    'emails_sent_session': 0,
    'current_lead_index': 0,
    'metadata': {},
    'use_llm': True,
    'llm_insights': {},
    'duplicate_leads': [],
    'approved_duplicates': [],
}


def init_session_state():
    """Inicializa variáveis de sessão usando valores padrão."""
    # Inicializa valores padrão
    for key, default in DEFAULT_SESSION_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Carrega limite diário do arquivo de configuração (persistente)
    if 'daily_limit' not in st.session_state:
        user_config = load_user_config()
        st.session_state.daily_limit = user_config.get('daily_limit', DAILY_EMAIL_LIMIT)


def render_status_panel():
    """Renderiza painel de status integrado no topo da página"""
    # Coleta status
    sender_info = get_sender_info()
    resend_ok = sender_info['configured']
    if resend_ok:
        resend_ok, _ = test_connection()

    llm_ok, _ = test_llm_connection()
    within_hours, _ = is_within_work_hours()
    remaining = get_remaining_emails_today(st.session_state.daily_limit)

    # Barra de status
    render_status_bar([
        {"label": "Resend API", "status": resend_ok},
        {"label": "LLM (GPT)", "status": llm_ok},
        {"label": f"Horário ({WORK_HOURS_START}h-{WORK_HOURS_END}h)", "status": within_hours},
        {"label": f"Emails: {remaining}/{st.session_state.daily_limit}", "status": remaining > 0},
    ])


def render_settings_tab():
    """Renderiza aba de configurações"""
    st.markdown("## ⚙️ Configurações")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📊 Limite Diário de Envios")
        new_limit = st.slider(
            "Emails por dia",
            min_value=1,
            max_value=100,
            value=st.session_state.daily_limit,
            help="Ajuste o limite diário de envios (salvo automaticamente)"
        )

        # Salva se mudou
        if new_limit != st.session_state.daily_limit:
            st.session_state.daily_limit = new_limit
            save_user_config({"daily_limit": new_limit})

        remaining = get_remaining_emails_today(st.session_state.daily_limit)

        # Métricas de limite
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            render_compact_metric(str(remaining), "Restantes Hoje", "📧", "success" if remaining > 0 else "error")
        with metric_col2:
            render_compact_metric(str(st.session_state.daily_limit), "Limite Total", "📊", "primary")

        if remaining == 0:
            st.error("🚫 Limite diário atingido! Aguarde até amanhã para enviar mais emails.")

        st.divider()

        # Status das conexões
        st.markdown("### 🔌 Status das Conexões")

        sender_info = get_sender_info()
        if sender_info['configured']:
            success, message = test_connection()
            if success:
                st.success(f"✅ Resend: {message}")
            else:
                st.error(f"❌ Resend: {message}")
        else:
            st.warning("⚠️ Configure SENDER_EMAIL no arquivo .env")

        llm_success, llm_message = test_llm_connection()
        if llm_success:
            st.success(f"✅ LLM: {llm_message}")
        else:
            st.warning(f"⚠️ LLM: {llm_message}")

        within_hours, hours_msg = is_within_work_hours()
        if within_hours:
            st.success(f"✅ Horário: {hours_msg}")
        else:
            st.warning(f"⏳ Horário: {hours_msg}")

    with col2:
        st.markdown("### 🚫 Blacklist")

        blacklist = get_blacklist()
        st.markdown(f"**{len(blacklist)}** emails bloqueados")

        # Adicionar à blacklist
        new_blacklist = st.text_input("Adicionar email à blacklist", placeholder="email@exemplo.com")
        if st.button("➕ Adicionar à Blacklist", type="primary") and new_blacklist:
            add_to_blacklist(new_blacklist)
            st.success(f"✅ {new_blacklist} adicionado à blacklist")
            st.rerun()

        # Lista de blacklist
        with st.expander(f"Ver todos os {len(blacklist)} emails bloqueados"):
            if blacklist:
                for item in blacklist:
                    st.markdown(f"• `{item['email']}`")
            else:
                st.info("Nenhum email na blacklist")

        st.divider()

        st.markdown("### 📅 Horário de Envio")
        st.info(f"""
        **Horário permitido:** {WORK_HOURS_START}:00 - {WORK_HOURS_END}:00

        Os emails só são enviados durante o horário comercial para melhorar a taxa de abertura.
        """)


def render_lead_input():
    """Renderiza área de entrada de leads"""
    st.markdown("## 📋 Entrada de Leads")
    
    # Toggle para usar LLM
    st.session_state.use_llm = st.toggle(
        "🧠 Usar IA (GPT-5 mini) para processar leads",
        value=st.session_state.use_llm,
        help="Quando ativado, a IA analisa os leads e gera emails personalizados"
    )
    
    json_input = st.text_area(
        "Cole o JSON de leads aqui:",
        height=300,
        placeholder='{"regiao_buscada": "Santos SP", "leads": [...]}'
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        button_label = "🧠 Processar com IA" if st.session_state.use_llm else "🔄 Processar Leads"
        if st.button(button_label, type="primary", width="stretch"):
            if json_input:
                try:
                    # Parse JSON
                    metadata, leads = parse_leads_json(json_input)
                    
                    if st.session_state.use_llm:
                        # Processamento com LLM
                        with st.spinner("🧠 IA analisando leads..."):
                            llm_result = process_leads_with_llm_sync(
                                json.dumps(leads, ensure_ascii=False),
                                metadata.get('regiao_buscada', 'N/A')
                            )
                        
                        if 'error' in llm_result and llm_result.get('error'):
                            st.warning(f"⚠️ Erro na IA, usando processamento padrão: {llm_result['error']}")
                            valid_leads, discarded_leads = process_leads(leads)
                        else:
                            # Converte resultado LLM para formato esperado
                            valid_leads = []
                            discarded_leads = []
                            processed_names = set()  # Rastreia leads já processados

                            # 1. Processa leads_processados (válidos e inválidos)
                            for proc_lead in llm_result.get('leads_processados', []):
                                nome = proc_lead.get('nome_clinica')
                                original = next(
                                    (l for l in leads if l.get('nome_clinica') == nome),
                                    None
                                )
                                if original:
                                    processed_names.add(nome)
                                    original['score'] = proc_lead.get('score', 50)
                                    original['llm_insights'] = proc_lead.get('insights', '')
                                    original['llm_abordagem'] = proc_lead.get('abordagem', 'generica')

                                    if proc_lead.get('deve_enviar', True):
                                        valid_leads.append(original)
                                    else:
                                        # Lead processado mas marcado para não enviar
                                        original['discard_reason'] = proc_lead.get('score_justificativa', 'Marcado pela IA para não enviar')
                                        discarded_leads.append(original)

                            # 2. Processa leads_descartados explicitamente pela IA
                            for disc_lead in llm_result.get('leads_descartados', []):
                                nome = disc_lead.get('nome_clinica')
                                if nome not in processed_names:
                                    original = next(
                                        (l for l in leads if l.get('nome_clinica') == nome),
                                        None
                                    )
                                    if original:
                                        processed_names.add(nome)
                                        original['discard_reason'] = disc_lead.get('motivo', 'Descartado pela IA')
                                        discarded_leads.append(original)

                            # 3. Captura leads que a IA não processou (evita perda de dados)
                            for lead in leads:
                                nome = lead.get('nome_clinica')
                                if nome and nome not in processed_names:
                                    lead['discard_reason'] = 'Não processado pela IA (possível timeout ou erro)'
                                    discarded_leads.append(lead)
                                    processed_names.add(nome)

                            # Ordena por score
                            valid_leads.sort(key=lambda x: x.get('score', 0), reverse=True)

                            st.success(f"🧠 IA processou: {len(valid_leads)} válidos, {len(discarded_leads)} descartados (total: {len(leads)})")
                    else:
                        # Processamento padrão
                        valid_leads, discarded_leads = process_leads(leads)
                    
                    # === VERIFICAÇÃO DE DUPLICATAS (180 dias) ===
                    leads_novos, leads_duplicados = check_leads_for_duplicates(valid_leads, days=180)
                    
                    if leads_duplicados:
                        st.warning(f"⚠️ {len(leads_duplicados)} lead(s) já foram contatados nos últimos 180 dias!")
                    
                    # Cria campanha no banco
                    campaign_id = create_campaign(
                        name=f"Campanha {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                        region=metadata.get('regiao_buscada', 'N/A')
                    )
                    
                    # Insere leads novos no banco com status 'queued'
                    for lead in leads_novos:
                        lead['db_id'] = insert_lead(campaign_id, lead)
                        update_lead_status(lead['db_id'], 'queued')

                    # Insere também leads descartados no banco (dados valiosos mesmo sem email)
                    for lead in discarded_leads:
                        lead['db_id'] = insert_lead(campaign_id, lead)
                        update_lead_status(lead['db_id'], 'invalid', lead.get('discard_reason', ''))

                    # Atualiza session state
                    st.session_state.campaign_id = campaign_id
                    st.session_state.valid_leads = leads_novos
                    st.session_state.discarded_leads = discarded_leads
                    st.session_state.duplicate_leads = leads_duplicados
                    st.session_state.approved_duplicates = []
                    st.session_state.metadata = metadata
                    st.session_state.current_lead_index = 0
                    st.session_state.emails_sent_session = 0
                    
                    # Atualiza estatísticas da campanha
                    update_campaign_stats(
                        campaign_id,
                        total_leads=len(leads_novos) + len(discarded_leads)
                    )
                    
                    # Mensagem clara de conclusão
                    st.balloons()
                    render_success_message(
                        "Processamento Concluído!",
                        f"{len(leads_novos)} leads prontos para envio"
                    )
                    render_info_box(
                        "Resumo do Processamento",
                        [
                            f"🆕 {len(leads_novos)} leads novos prontos para envio",
                            f"⚠️ {len(leads_duplicados)} já contatados (aguardando aprovação)",
                            f"❌ {len(discarded_leads)} descartados (sem email válido, mas salvos no banco)",
                            "👉 Vá para a aba 'Fila de Envio' para continuar"
                        ],
                        "📊"
                    )
                    time.sleep(2)  # Pequena pausa para ler a mensagem
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao processar: {str(e)}")
            else:
                st.warning("⚠️ Cole o JSON de leads primeiro")
    
    with col2:
        if st.button("🗑️ Limpar", width="stretch"):
            st.session_state.campaign_id = None
            st.session_state.valid_leads = []
            st.session_state.discarded_leads = []
            st.session_state.metadata = {}
            st.session_state.current_lead_index = 0
            st.session_state.sending_active = False
            st.rerun()


def render_lead_queue():
    """Renderiza fila de leads para envio"""
    if not st.session_state.valid_leads:
        render_empty_state("Nenhum lead na fila. Cole um JSON de leads na aba 'Nova Campanha'.", "📭")
        return

    st.markdown("## 📬 Fila de Envio")

    # Métricas estilizadas
    total = len(st.session_state.valid_leads)
    sent = st.session_state.emails_sent_session
    pending = total - sent
    discarded = len(st.session_state.discarded_leads)
    remaining_today = get_remaining_emails_today(st.session_state.daily_limit)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_metric_card(str(pending), "Na Fila", "📋", "primary")
    with col2:
        render_metric_card(str(sent), "Enviados", "✅", "success")
    with col3:
        render_metric_card(str(discarded), "Descartados", "❌", "error")
    with col4:
        render_metric_card(str(remaining_today), "Restam Hoje", "📊", "warning")
    
    # Estimativa de tempo
    if pending > 0:
        time_estimate = estimate_completion_time(min(pending, remaining_today), sent)
        st.info(f"⏱️ Tempo estimado para enviar {min(pending, remaining_today)} emails: {time_estimate}")
    
    st.divider()
    
    # Progress tracker do envio
    if sent > 0 or st.session_state.sending_active:
        render_progress_tracker(
            current_step=min(sent, total),
            steps=[f"Lead {i+1}" for i in range(min(total, 5))] + (["..."] if total > 5 else [])
        )

    # Lista de leads com cards estilizados
    st.markdown("### 📋 Leads Ordenados por Score")

    for i, lead in enumerate(st.session_state.valid_leads):
        # Define status do lead
        if i < st.session_state.current_lead_index:
            status_text = "sent"
        elif i == st.session_state.current_lead_index and st.session_state.sending_active:
            status_text = "pending"
        else:
            status_text = "pending"

        # Adiciona status ao lead para exibição
        lead_display = lead.copy()
        lead_display['_status'] = status_text
        lead_display['_index'] = i + 1

        # Card do lead
        col_status, col_card = st.columns([0.5, 9.5])

        with col_status:
            if i < st.session_state.current_lead_index:
                st.markdown("✅")
            elif i == st.session_state.current_lead_index and st.session_state.sending_active:
                st.markdown("📤")
            else:
                st.markdown(f"**{i+1}**")

        with col_card:
            render_lead_card(lead, show_details=True)

            # Mostra insights da IA se disponível
            if lead.get('llm_insights'):
                st.caption(f"💡 IA: {lead.get('llm_insights')}")


def render_send_controls():
    """Renderiza controles de envio"""
    if not st.session_state.valid_leads:
        return
    
    st.markdown("## 🚀 Controles de Envio")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        can_send, send_msg = can_send_email(st.session_state.daily_limit)
        
        if st.session_state.sending_active:
            if st.button("⏸️ Pausar Envio", type="secondary", width="stretch"):
                st.session_state.sending_active = False
                st.rerun()
        else:
            button_text = "▶️ Iniciar Envio (IA)" if st.session_state.use_llm else "▶️ Iniciar Envio"
            if st.button(button_text, type="primary", width="stretch", disabled=not can_send):
                if can_send:
                    st.session_state.sending_active = True
                    st.rerun()
                else:
                    st.error(send_msg)
    
    with col2:
        # Preview do próximo email (com ou sem IA)
        current_idx = st.session_state.current_lead_index
        if current_idx < len(st.session_state.valid_leads):
            current_lead = st.session_state.valid_leads[current_idx]
            preview_label = "🧠 Preview Email (IA)" if st.session_state.use_llm else "👁️ Preview Email"
            if st.button(preview_label, width="stretch"):
                with st.spinner("🧠 Gerando email personalizado..." if st.session_state.use_llm else "Gerando preview..."):
                    email_preview = generate_email_preview(current_lead, use_llm=st.session_state.use_llm)
                
                st.markdown("---")
                st.markdown(f"**📨 Para:** {current_lead.get('contatos', {}).get('email_principal') or current_lead.get('email_principal', 'N/A')}")
                st.markdown(f"**📌 Assunto:** {email_preview.get('assunto', 'N/A')}")
                st.markdown("**📝 Corpo:**")
                st.text_area("Email", value=email_preview.get('corpo', ''), height=200, disabled=True, label_visibility="collapsed")
                
                if st.session_state.use_llm:
                    st.caption("💡 Este email foi gerado pela IA baseado nos insights do lead.")
    
    with col3:
        if st.button("📄 Gerar Relatório PDF", width="stretch"):
            if st.session_state.campaign_id:
                try:
                    filepath = generate_campaign_report(
                        st.session_state.campaign_id,
                        st.session_state.valid_leads,
                        st.session_state.discarded_leads
                    )
                    st.success(f"✅ Relatório salvo em: {filepath}")
                except Exception as e:
                    st.error(f"❌ Erro ao gerar relatório: {str(e)}")
    
    # Área de envio ativo
    if st.session_state.sending_active:
        send_emails_with_delay()


def send_emails_with_delay():
    """Envia emails com delay inteligente"""
    current_idx = st.session_state.current_lead_index
    valid_leads = st.session_state.valid_leads
    campaign_id = st.session_state.campaign_id
    
    if current_idx >= len(valid_leads):
        st.success("🎉 Todos os emails foram enviados!")
        st.session_state.sending_active = False
        return
    
    # Verifica se pode enviar
    can_send, send_msg = can_send_email(st.session_state.daily_limit)
    if not can_send:
        st.warning(f"⏳ {send_msg}")
        st.session_state.sending_active = False
        return
    
    # Pega próximo lead
    lead = valid_leads[current_idx]
    lead_id = lead.get('db_id')
    
    # Exibe status
    status_container = st.container()
    with status_container:
        st.markdown(f"### 📤 Enviando para: {lead.get('nome_clinica')}")
        progress = st.progress(0)
        status_text = st.empty()
    
    # Calcula delay
    delay = get_smart_delay(st.session_state.emails_sent_session)
    delay_formatted = format_delay_for_display(delay)
    
    # Envia email
    status_text.text(f"🧠 Gerando email personalizado..." if st.session_state.use_llm else "📧 Enviando email...")
    progress.progress(30)
    
    success, message, resend_id = send_email(lead, campaign_id, lead_id, use_llm=st.session_state.use_llm)
    
    if success:
        progress.progress(60)
        status_text.text(f"✅ Enviado! Aguardando {delay_formatted} para próximo...")
        
        # Atualiza contadores
        st.session_state.emails_sent_session += 1
        st.session_state.current_lead_index += 1
        
        update_campaign_stats(
            campaign_id,
            emails_sent=st.session_state.emails_sent_session
        )
        
        # Delay antes do próximo
        progress.progress(80)
        time.sleep(min(delay, 10))  # Limita delay visual a 10s para UX
        progress.progress(100)
        
        # Continua se ainda está ativo
        if st.session_state.sending_active:
            st.rerun()
    else:
        progress.progress(100)
        status_text.text(f"❌ Erro: {message}")
        st.session_state.current_lead_index += 1
        
        update_campaign_stats(
            campaign_id,
            emails_failed=1
        )
        
        time.sleep(2)
        if st.session_state.sending_active:
            st.rerun()


def render_discarded_leads():
    """Renderiza leads descartados"""
    if not st.session_state.discarded_leads:
        return

    with st.expander(f"🚫 Leads Descartados ({len(st.session_state.discarded_leads)})", expanded=False):
        for lead in st.session_state.discarded_leads:
            nome = lead.get('nome_clinica', 'N/A')
            motivo = lead.get('discard_reason', 'Motivo não especificado')
            st.markdown(f"**{nome}** — _{motivo}_")


def render_duplicate_leads():
    """Renderiza leads que já foram contatados nos últimos 180 dias"""
    if not st.session_state.duplicate_leads:
        return

    st.markdown("""
    <div style="background: var(--warning-light); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
            <span style="font-size: 1.5rem;">⚠️</span>
            <h3 style="margin: 0; color: var(--warning-dark);">Leads Já Contatados (180 dias)</h3>
        </div>
        <p style="margin: 0; color: var(--warning-dark);">
            Os seguintes <strong>""" + str(len(st.session_state.duplicate_leads)) + """</strong> lead(s) já receberam email nos últimos 180 dias.
            Você pode aprovar manualmente se desejar reenviar.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Botão para aprovar todos
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("✅ Aprovar Todos", type="primary"):
            for lead in st.session_state.duplicate_leads:
                # Insere no banco e adiciona à fila
                lead['db_id'] = insert_lead(st.session_state.campaign_id, lead)
                st.session_state.valid_leads.append(lead)
            st.session_state.duplicate_leads = []
            st.success("✅ Todos os leads duplicados foram aprovados!")
            st.rerun()
    
    with col2:
        if st.button("❌ Ignorar Todos"):
            st.session_state.duplicate_leads = []
            st.info("Leads duplicados ignorados.")
            st.rerun()
    
    st.divider()
    
    # Lista cada lead duplicado
    for i, lead in enumerate(st.session_state.duplicate_leads):
        last_sent = lead.get('last_sent_info', {})
        email = lead.get('contatos', {}).get('email_principal') or lead.get('email_principal', 'N/A')
        
        with st.container():
            cols = st.columns([3, 2, 2, 1])
            
            with cols[0]:
                st.markdown(f"**{lead.get('nome_clinica')}**")
                st.caption(f"📧 {email}")
            
            with cols[1]:
                sent_date = last_sent.get('sent_at', 'N/A')
                if sent_date and sent_date != 'N/A':
                    # Formata data
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(sent_date[:19], '%Y-%m-%d %H:%M:%S')
                        sent_date = dt.strftime('%d/%m/%Y')
                    except:
                        pass
                st.markdown(f"📅 **Último envio:** {sent_date}")
                st.caption(f"Campanha: {last_sent.get('campaign_name', 'N/A')}")
            
            with cols[2]:
                days_ago = "N/A"
                if last_sent.get('sent_at'):
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(last_sent['sent_at'][:19], '%Y-%m-%d %H:%M:%S')
                        days_ago = (datetime.now() - dt).days
                    except:
                        pass
                st.metric("Dias atrás", days_ago)
            
            with cols[3]:
                if st.button(f"✅ Aprovar", key=f"approve_{i}"):
                    # Insere no banco e adiciona à fila
                    lead['db_id'] = insert_lead(st.session_state.campaign_id, lead)
                    st.session_state.valid_leads.append(lead)
                    st.session_state.duplicate_leads.remove(lead)
                    st.success(f"✅ {lead.get('nome_clinica')} aprovado!")
                    st.rerun()
            
            st.divider()


def main():
    """Função principal"""
    # Inicializa banco
    init_database()

    # Inicializa session state
    init_session_state()

    # Header com estatísticas
    remaining_today = get_remaining_emails_today(st.session_state.daily_limit)
    header_stats = {
        "Enviados Hoje": st.session_state.emails_sent_session,
        "Restantes": remaining_today,
        "Limite": st.session_state.daily_limit
    }
    render_header(
        title="📧 ABAplay Email Automation",
        subtitle="Sistema inteligente de prospecção de clínicas ABA",
        stats=header_stats
    )

    # Barra de status integrada
    render_status_panel()

    # Área principal com tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Nova Campanha",
        "📊 Fila de Envio",
        "📈 Dados",
        "📜 Histórico",
        "⚙️ Configurações"
    ])

    with tab1:
        render_lead_input()

    with tab2:
        render_duplicate_leads()
        render_lead_queue()
        render_send_controls()
        render_discarded_leads()

    with tab3:
        render_data_viewer()

    with tab4:
        st.markdown("## 📜 Histórico de Campanhas")
        if st.session_state.campaign_id:
            campaign = get_campaign(st.session_state.campaign_id)
            if campaign:
                st.json(campaign)

            logs = get_email_log_by_campaign(st.session_state.campaign_id)
            if logs:
                st.markdown("### 📧 Log de Emails")
                for log in logs:
                    status_emoji = "✅" if log['status'] == 'sent' else "❌"
                    st.markdown(f"{status_emoji} **{log.get('nome_clinica')}** - {log['email_to']} - {log['status']}")
        else:
            st.info("Nenhuma campanha ativa")

    with tab5:
        render_settings_tab()


if __name__ == "__main__":
    main()

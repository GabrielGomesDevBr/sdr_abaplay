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
    get_campaign, add_to_blacklist, get_blacklist, check_leads_for_duplicates
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


# Configuração da página
st.set_page_config(
    page_title="ABAplay Email Automation",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1a365d;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        text-align: center;
    }
    .status-ok { color: #48bb78; font-weight: bold; }
    .status-warning { color: #ecc94b; font-weight: bold; }
    .status-error { color: #fc8181; font-weight: bold; }
    .lead-card {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .score-badge {
        background: #4299e1;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Inicializa variáveis de sessão"""
    if 'campaign_id' not in st.session_state:
        st.session_state.campaign_id = None
    if 'valid_leads' not in st.session_state:
        st.session_state.valid_leads = []
    if 'discarded_leads' not in st.session_state:
        st.session_state.discarded_leads = []
    if 'sending_active' not in st.session_state:
        st.session_state.sending_active = False
    if 'emails_sent_session' not in st.session_state:
        st.session_state.emails_sent_session = 0
    if 'current_lead_index' not in st.session_state:
        st.session_state.current_lead_index = 0
    if 'metadata' not in st.session_state:
        st.session_state.metadata = {}
    if 'use_llm' not in st.session_state:
        st.session_state.use_llm = True
    if 'llm_insights' not in st.session_state:
        st.session_state.llm_insights = {}
    if 'duplicate_leads' not in st.session_state:
        st.session_state.duplicate_leads = []
    if 'approved_duplicates' not in st.session_state:
        st.session_state.approved_duplicates = []
    if 'daily_limit' not in st.session_state:
        st.session_state.daily_limit = DAILY_EMAIL_LIMIT


def render_sidebar():
    """Renderiza barra lateral com status e configurações"""
    with st.sidebar:
        st.markdown("## ⚙️ Configurações")
        
        # Status da conexão
        st.markdown("### 🔌 Status da Conexão")
        sender_info = get_sender_info()
        
        if sender_info['configured']:
            success, message = test_connection()
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")
        else:
            st.warning("⚠️ Configure SENDER_EMAIL no arquivo .env")
        
        # Status OpenAI
        st.markdown("### 🧠 Status LLM (OpenAI)")
        llm_success, llm_message = test_llm_connection()
        if llm_success:
            st.success(f"✅ {llm_message}")
        else:
            st.warning(f"⚠️ {llm_message}")
        
        st.divider()
        
        # Status do horário
        st.markdown("### 🕐 Horário de Envio")
        within_hours, hours_msg = is_within_work_hours()
        if within_hours:
            st.success(f"✅ {hours_msg}")
        else:
            st.warning(f"⏳ {hours_msg}")
        
        st.info(f"📅 Horário permitido: {WORK_HOURS_START}:00 - {WORK_HOURS_END}:00")
        
        st.divider()
        
        # Limite diário
        st.markdown("### 📊 Limite Diário")
        st.session_state.daily_limit = st.slider(
            "Emails por dia",
            min_value=1,
            max_value=100,
            value=st.session_state.daily_limit,
            help="Ajuste o limite diário de envios"
        )
        remaining = get_remaining_emails_today(st.session_state.daily_limit)
        st.metric("Emails Restantes Hoje", f"{remaining}/{st.session_state.daily_limit}")
        
        if remaining == 0:
            st.error("🚫 Limite diário atingido!")
        
        st.divider()
        
        # Blacklist
        st.markdown("### 🚫 Blacklist")
        blacklist = get_blacklist()
        st.metric("Emails bloqueados", len(blacklist))
        
        with st.expander("Ver blacklist"):
            if blacklist:
                for item in blacklist:
                    st.text(f"• {item['email']}")
            else:
                st.text("Nenhum email na blacklist")
        
        # Adicionar à blacklist
        new_blacklist = st.text_input("Adicionar email à blacklist")
        if st.button("➕ Adicionar") and new_blacklist:
            add_to_blacklist(new_blacklist)
            st.success(f"✅ {new_blacklist} adicionado à blacklist")
            st.rerun()


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
        if st.button(button_label, type="primary", use_container_width=True):
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
                            
                            for proc_lead in llm_result.get('leads_processados', []):
                                # Encontra lead original
                                original = next(
                                    (l for l in leads if l.get('nome_clinica') == proc_lead.get('nome_clinica')),
                                    None
                                )
                                if original and proc_lead.get('deve_enviar', True):
                                    original['score'] = proc_lead.get('score', 50)
                                    original['llm_insights'] = proc_lead.get('insights', '')
                                    original['llm_abordagem'] = proc_lead.get('abordagem', 'generica')
                                    valid_leads.append(original)
                            
                            for disc_lead in llm_result.get('leads_descartados', []):
                                original = next(
                                    (l for l in leads if l.get('nome_clinica') == disc_lead.get('nome_clinica')),
                                    None
                                )
                                if original:
                                    original['discard_reason'] = disc_lead.get('motivo', 'Descartado pela IA')
                                    discarded_leads.append(original)
                            
                            # Ordena por score
                            valid_leads.sort(key=lambda x: x.get('score', 0), reverse=True)
                            
                            st.success(f"🧠 IA processou: {len(valid_leads)} válidos, {len(discarded_leads)} descartados")
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
                    
                    # Insere apenas leads novos no banco
                    for lead in leads_novos:
                        lead['db_id'] = insert_lead(campaign_id, lead)
                    
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
                    st.success(f"✅ **PRONTO!** Processamento concluído.")
                    st.balloons()
                    st.info(f"""
📊 **Resumo do processamento:**
- 🆕 **{len(leads_novos)}** leads novos prontos para envio
- ⚠️ **{len(leads_duplicados)}** já contatados (aguardando sua aprovação)
- ❌ **{len(discarded_leads)}** descartados (sem email válido)

👉 **Vá para a aba "📊 Fila de Envio" para continuar.**
                    """)
                    time.sleep(2)  # Pequena pausa para ler a mensagem
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao processar: {str(e)}")
            else:
                st.warning("⚠️ Cole o JSON de leads primeiro")
    
    with col2:
        if st.button("🗑️ Limpar", use_container_width=True):
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
        st.info("📭 Nenhum lead na fila. Cole um JSON de leads acima.")
        return
    
    st.markdown("## 📬 Fila de Envio")
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(st.session_state.valid_leads)
    sent = st.session_state.emails_sent_session
    pending = total - sent
    discarded = len(st.session_state.discarded_leads)
    
    with col1:
        st.metric("📋 Na Fila", pending)
    with col2:
        st.metric("✅ Enviados", sent)
    with col3:
        st.metric("❌ Descartados", discarded)
    with col4:
        remaining_today = get_remaining_emails_today(st.session_state.daily_limit)
        st.metric("📊 Restam Hoje", remaining_today)
    
    # Estimativa de tempo
    if pending > 0:
        time_estimate = estimate_completion_time(min(pending, remaining_today), sent)
        st.info(f"⏱️ Tempo estimado para enviar {min(pending, remaining_today)} emails: {time_estimate}")
    
    st.divider()
    
    # Tabela de leads
    st.markdown("### 📋 Leads Ordenados por Score")
    
    for i, lead in enumerate(st.session_state.valid_leads):
        info = get_lead_display_info(lead)
        
        # Define cor baseado no status
        if i < st.session_state.current_lead_index:
            status = "✅ Enviado"
            bg_color = "#c6f6d5"
        elif i == st.session_state.current_lead_index and st.session_state.sending_active:
            status = "📤 Enviando..."
            bg_color = "#fefcbf"
        else:
            status = "⏳ Pendente"
            bg_color = "#f7fafc"
        
        with st.container():
            cols = st.columns([0.5, 3, 3, 1.5, 1.5, 1])
            
            with cols[0]:
                st.markdown(f"**#{i+1}**")
            with cols[1]:
                st.markdown(f"**{info['nome']}**")
                st.caption(info['cidade'])
            with cols[2]:
                st.markdown(f"📧 {info['email']}")
                st.caption(f"Tipo: {info['email_tipo']}")
            with cols[3]:
                st.markdown(f"👤 {info['decisor_nome']}")
            with cols[4]:
                st.markdown(f"<span class='score-badge'>Score: {info['score']}</span>", unsafe_allow_html=True)
            with cols[5]:
                st.markdown(status)
            
            # Mostra insights da IA se disponível
            if lead.get('llm_insights'):
                st.caption(f"💡 IA: {lead.get('llm_insights')}")
            
            st.divider()


def render_send_controls():
    """Renderiza controles de envio"""
    if not st.session_state.valid_leads:
        return
    
    st.markdown("## 🚀 Controles de Envio")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        can_send, send_msg = can_send_email(st.session_state.daily_limit)
        
        if st.session_state.sending_active:
            if st.button("⏸️ Pausar Envio", type="secondary", use_container_width=True):
                st.session_state.sending_active = False
                st.rerun()
        else:
            button_text = "▶️ Iniciar Envio (IA)" if st.session_state.use_llm else "▶️ Iniciar Envio"
            if st.button(button_text, type="primary", use_container_width=True, disabled=not can_send):
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
            if st.button(preview_label, use_container_width=True):
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
        if st.button("📄 Gerar Relatório PDF", use_container_width=True):
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
    
    with st.expander(f"🚫 Leads Descartados ({len(st.session_state.discarded_leads)})"):
        for lead in st.session_state.discarded_leads:
            st.markdown(f"**{lead.get('nome_clinica')}** - {lead.get('discard_reason', 'Motivo não especificado')}")


def render_duplicate_leads():
    """Renderiza leads que já foram contatados nos últimos 180 dias"""
    if not st.session_state.duplicate_leads:
        return
    
    st.markdown("## ⚠️ Leads Já Contatados (180 dias)")
    st.warning(f"Os seguintes {len(st.session_state.duplicate_leads)} lead(s) já receberam email nos últimos 180 dias. Você pode aprovar manualmente se desejar reenviar.")
    
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
    
    # Título
    st.markdown("<h1 class='main-header'>📧 ABAplay Email Automation</h1>", unsafe_allow_html=True)
    
    # Sidebar
    render_sidebar()
    
    # Área principal
    tab1, tab2, tab3 = st.tabs(["📋 Nova Campanha", "📊 Fila de Envio", "📜 Histórico"])
    
    with tab1:
        render_lead_input()
    
    with tab2:
        render_duplicate_leads()  # Mostra leads já contatados primeiro
        render_lead_queue()
        render_send_controls()
        render_discarded_leads()
    
    with tab3:
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


if __name__ == "__main__":
    main()

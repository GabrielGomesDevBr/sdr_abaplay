"""
Componentes visuais reutilizáveis para a interface Streamlit.
Design System ABAplay.
"""
import streamlit as st
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# CSS DESIGN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

CUSTOM_CSS = """
<style>
/* === VARIÁVEIS CSS === */
:root {
    --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --primary-500: #667eea;
    --primary-600: #5a67d8;
    --primary-700: #4c51bf;

    --success-light: #c6f6d5;
    --success-dark: #22543d;
    --error-light: #fed7d7;
    --error-dark: #822727;
    --warning-light: #fefcbf;
    --warning-dark: #744210;
    --info-light: #bee3f8;
    --info-dark: #2a4365;

    --gray-50: #f7fafc;
    --gray-100: #edf2f7;
    --gray-200: #e2e8f0;
    --gray-300: #cbd5e0;
    --gray-500: #718096;
    --gray-700: #4a5568;
    --gray-900: #1a202c;

    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
    --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
}

/* === LAYOUT GERAL === */
.main .block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* === HEADER === */
.app-header {
    background: var(--primary-gradient);
    padding: 1.5rem 2rem;
    border-radius: 1rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 10px 15px rgba(102, 126, 234, 0.2);
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.app-header-content h1 {
    color: white;
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
}

.app-header-content p {
    color: rgba(255,255,255,0.85);
    margin: 0.25rem 0 0 0;
    font-size: 0.9rem;
}

.app-header-stats {
    display: flex;
    gap: 1.5rem;
}

.header-stat {
    text-align: center;
    color: white;
}

.header-stat-value {
    font-size: 1.5rem;
    font-weight: 700;
}

.header-stat-label {
    font-size: 0.75rem;
    opacity: 0.85;
}

/* === CARDS DE MÉTRICAS === */
.metric-card {
    background: white;
    border-radius: 0.75rem;
    padding: 1.25rem;
    box-shadow: var(--shadow-md);
    border: 1px solid var(--gray-200);
    transition: transform 0.2s, box-shadow 0.2s;
    height: 100%;
}

.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
}

.metric-card.primary {
    background: var(--primary-gradient);
    color: white;
    border: none;
}

.metric-card.success {
    border-left: 4px solid #48bb78;
}

.metric-card.warning {
    border-left: 4px solid #ecc94b;
}

.metric-card.error {
    border-left: 4px solid #fc8181;
}

.metric-icon {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
}

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    color: var(--gray-900);
}

.metric-card.primary .metric-value {
    color: white;
}

.metric-label {
    font-size: 0.8rem;
    color: var(--gray-500);
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.metric-card.primary .metric-label {
    color: rgba(255,255,255,0.8);
}

.metric-delta {
    font-size: 0.75rem;
    margin-top: 0.5rem;
    padding: 0.125rem 0.5rem;
    border-radius: 0.25rem;
    display: inline-block;
}

.metric-delta.positive {
    background: var(--success-light);
    color: var(--success-dark);
}

.metric-delta.negative {
    background: var(--error-light);
    color: var(--error-dark);
}

/* === LEAD CARDS === */
.lead-card {
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 0.75rem;
    padding: 1.25rem;
    margin: 0.75rem 0;
    transition: all 0.2s;
}

.lead-card:hover {
    border-color: var(--primary-500);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.lead-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.75rem;
}

.lead-name {
    font-weight: 600;
    font-size: 1.05rem;
    color: var(--gray-900);
    margin: 0;
}

.lead-location {
    color: var(--gray-500);
    font-size: 0.85rem;
    margin-top: 0.125rem;
}

.lead-badges {
    display: flex;
    gap: 0.375rem;
    flex-wrap: wrap;
}

.lead-details {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--gray-700);
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--gray-100);
}

.lead-detail-item {
    display: flex;
    align-items: center;
    gap: 0.375rem;
}

/* === BADGES === */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.625rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.badge-score {
    background: var(--primary-gradient);
    color: white;
}

.badge-score.high {
    background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
}

.badge-score.medium {
    background: linear-gradient(135deg, #ecc94b 0%, #d69e2e 100%);
}

.badge-score.low {
    background: linear-gradient(135deg, #fc8181 0%, #e53e3e 100%);
}

.badge-confianca {
    font-size: 0.65rem;
    padding: 0.2rem 0.5rem;
}

.badge-confianca.alta {
    background: var(--success-light);
    color: var(--success-dark);
}

.badge-confianca.media {
    background: var(--warning-light);
    color: var(--warning-dark);
}

.badge-confianca.baixa {
    background: var(--error-light);
    color: var(--error-dark);
}

.badge-status {
    padding: 0.3rem 0.75rem;
}

.badge-status.sent {
    background: var(--success-light);
    color: var(--success-dark);
}

.badge-status.failed {
    background: var(--error-light);
    color: var(--error-dark);
}

.badge-status.pending {
    background: var(--warning-light);
    color: var(--warning-dark);
}

.badge-tom {
    font-size: 0.65rem;
    background: var(--gray-100);
    color: var(--gray-700);
}

/* === PROGRESS TRACKER === */
.progress-tracker {
    display: flex;
    justify-content: space-between;
    margin: 1.5rem 0;
    position: relative;
    padding: 0 1rem;
}

.progress-tracker::before {
    content: '';
    position: absolute;
    top: 1.125rem;
    left: 3rem;
    right: 3rem;
    height: 3px;
    background: var(--gray-200);
    border-radius: 2px;
}

.progress-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
    z-index: 1;
    flex: 1;
}

.progress-step-circle {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 50%;
    background: white;
    border: 3px solid var(--gray-200);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--gray-500);
    transition: all 0.3s;
}

.progress-step.active .progress-step-circle {
    background: var(--primary-gradient);
    border-color: var(--primary-500);
    color: white;
    box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2);
}

.progress-step.completed .progress-step-circle {
    background: #48bb78;
    border-color: #48bb78;
    color: white;
}

.progress-step-label {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: var(--gray-500);
    text-align: center;
}

.progress-step.active .progress-step-label {
    color: var(--primary-600);
    font-weight: 600;
}

.progress-step.completed .progress-step-label {
    color: #38a169;
}

/* === TABS CUSTOMIZADOS === */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    background: var(--gray-100);
    padding: 0.375rem;
    border-radius: 0.75rem;
    margin-top: 1rem;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 0.5rem;
    padding: 0.625rem 1.25rem;
    font-weight: 500;
    font-size: 0.9rem;
    color: #4a5568 !important;
}

.stTabs [aria-selected="true"] {
    background: white !important;
    box-shadow: var(--shadow-sm);
    color: #1a202c !important;
}

/* Dark mode support for tabs */
@media (prefers-color-scheme: dark) {
    .stTabs [data-baseweb="tab-list"] {
        background: #2d3748;
    }
    .stTabs [data-baseweb="tab"] {
        color: #e2e8f0 !important;
    }
    .stTabs [aria-selected="true"] {
        background: #4a5568 !important;
        color: #ffffff !important;
    }
}

/* Streamlit dark theme detection */
[data-theme="dark"] .stTabs [data-baseweb="tab-list"],
.stApp[data-theme="dark"] .stTabs [data-baseweb="tab-list"] {
    background: #2d3748;
}

[data-theme="dark"] .stTabs [data-baseweb="tab"],
.stApp[data-theme="dark"] .stTabs [data-baseweb="tab"] {
    color: #e2e8f0 !important;
}

[data-theme="dark"] .stTabs [aria-selected="true"],
.stApp[data-theme="dark"] .stTabs [aria-selected="true"] {
    background: #4a5568 !important;
    color: #ffffff !important;
}

/* === SIDEBAR (collapsed by default) === */
section[data-testid="stSidebar"] {
    background: var(--gray-50);
}

/* === TABELAS === */
.dataframe {
    border: none !important;
    border-radius: 0.75rem !important;
    overflow: hidden !important;
}

.dataframe thead tr th {
    background: var(--primary-gradient) !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 0.875rem 1rem !important;
    font-size: 0.85rem !important;
}

.dataframe tbody tr {
    transition: background 0.15s;
}

.dataframe tbody tr:nth-child(even) {
    background: var(--gray-50);
}

.dataframe tbody tr:hover {
    background: var(--gray-100);
}

.dataframe tbody td {
    padding: 0.75rem 1rem !important;
    font-size: 0.85rem;
}

/* === BOTÕES === */
.stButton > button {
    border-radius: 0.5rem;
    font-weight: 500;
    padding: 0.5rem 1.25rem;
    transition: all 0.2s;
    font-size: 0.9rem;
}

.stButton > button[kind="primary"] {
    background: var(--primary-gradient);
    border: none;
}

.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.stButton > button[kind="secondary"] {
    background: white;
    border: 2px solid var(--gray-200);
    color: var(--gray-700);
}

.stButton > button[kind="secondary"]:hover {
    border-color: var(--primary-500);
    color: var(--primary-600);
}

/* === INPUTS === */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    border-radius: 0.5rem !important;
    border: 2px solid var(--gray-200) !important;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary-500) !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
}

/* === ALERTAS === */
.stAlert {
    border-radius: 0.75rem;
    border: none;
}

/* === EXPANDERS === */
.streamlit-expanderHeader {
    background: var(--gray-50);
    border-radius: 0.5rem;
    font-weight: 500;
}

/* === DIVIDER === */
hr {
    border: none;
    height: 1px;
    background: var(--gray-200);
    margin: 1.5rem 0;
}

/* === ANIMAÇÕES === */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
    animation: fadeIn 0.3s ease-out;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.animate-pulse {
    animation: pulse 2s infinite;
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}

.animate-slide-in {
    animation: slideIn 0.3s ease-out;
}

/* === SKELETON LOADING === */
.skeleton {
    background: linear-gradient(90deg, var(--gray-100) 25%, var(--gray-200) 50%, var(--gray-100) 75%);
    background-size: 200% 100%;
    animation: skeleton-loading 1.5s infinite;
    border-radius: 0.25rem;
}

@keyframes skeleton-loading {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* === RESPONSIVIDADE === */
@media (max-width: 768px) {
    .app-header {
        flex-direction: column;
        text-align: center;
        gap: 1rem;
    }

    .app-header-stats {
        justify-content: center;
    }

    .metric-card {
        padding: 1rem;
    }

    .metric-value {
        font-size: 1.5rem;
    }

    .lead-card-header {
        flex-direction: column;
        gap: 0.5rem;
    }

    .lead-details {
        grid-template-columns: 1fr;
    }

    .progress-tracker {
        padding: 0;
    }
}
</style>
"""


def inject_custom_css():
    """Injeta o CSS customizado na página"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS
# ═══════════════════════════════════════════════════════════════════════════════

def render_header(title: str = "ABAplay Email Automation",
                  subtitle: str = "Sistema inteligente de prospecção",
                  stats: Optional[Dict] = None):
    """
    Renderiza header com gradiente.

    Args:
        title: Título principal
        subtitle: Subtítulo
        stats: Dict com estatísticas para exibir (opcional)
    """
    stats_html = ""
    if stats:
        stats_items = "".join([
            f'<div class="header-stat">'
            f'<div class="header-stat-value">{v}</div>'
            f'<div class="header-stat-label">{k}</div>'
            f'</div>'
            for k, v in stats.items()
        ])
        stats_html = f'<div class="app-header-stats">{stats_items}</div>'

    st.markdown(f"""
    <div class="app-header">
        <div class="app-header-content">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        {stats_html}
    </div>
    """, unsafe_allow_html=True)


def render_metric_card(
    value: str,
    label: str,
    icon: str = "",
    variant: str = "default",
    delta: Optional[str] = None,
    delta_type: str = "positive"
):
    """
    Renderiza card de métrica estilizado.

    Args:
        value: Valor principal
        label: Label da métrica
        icon: Emoji/ícone (opcional)
        variant: Variante visual (default, primary, success, warning, error)
        delta: Valor de variação (opcional)
        delta_type: Tipo do delta (positive, negative)
    """
    delta_html = ""
    if delta:
        delta_html = f'<div class="metric-delta {delta_type}">{delta}</div>'

    icon_html = f'<div class="metric-icon">{icon}</div>' if icon else ""

    st.markdown(f"""
    <div class="metric-card {variant}">
        {icon_html}
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_lead_card(lead: Dict, show_details: bool = True):
    """
    Renderiza card de lead estilizado usando componentes Streamlit nativos.

    Args:
        lead: Dados do lead
        show_details: Se True, mostra detalhes expandidos
    """
    nome = lead.get('nome_clinica', 'N/A')
    cidade = lead.get('cidade_uf', 'N/A')
    email = lead.get('contatos', {}).get('email_principal') or lead.get('email_principal', 'N/A')
    telefone = lead.get('contatos', {}).get('telefone') or lead.get('telefone', '')
    decisor_nome = lead.get('decisor', {}).get('nome') or lead.get('decisor_nome', '')
    decisor_cargo = lead.get('decisor', {}).get('cargo') or lead.get('decisor_cargo', '')
    score = lead.get('score', 50)
    confianca = lead.get('confianca', 'media')
    tom = lead.get('contexto_abordagem', {}).get('tom_sugerido') or lead.get('tom_sugerido', '')

    # Cores para badges
    score_color = "#48bb78" if score >= 70 else "#ecc94b" if score >= 40 else "#fc8181"
    confianca_colors = {"alta": "#48bb78", "media": "#ecc94b", "baixa": "#fc8181"}
    confianca_bg = confianca_colors.get(confianca.lower() if confianca else "media", "#ecc94b")

    # Container do card
    with st.container():
        # Header com nome e badges
        col_info, col_badges = st.columns([3, 1])

        with col_info:
            st.markdown(f"**{nome}**")
            st.caption(f"📍 {cidade}")

        with col_badges:
            badges_html = (
                f'<div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;">'
                f'<span style="background:{score_color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">{score}</span>'
                f'<span style="background:{confianca_bg};color:white;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">{(confianca or "media").upper()}</span>'
            )
            if tom:
                badges_html += f'<span style="background:#e2e8f0;color:#4a5568;padding:2px 8px;border-radius:12px;font-size:11px;">{tom}</span>'
            badges_html += '</div>'
            st.markdown(badges_html, unsafe_allow_html=True)

        # Detalhes
        if show_details:
            detail_cols = st.columns(4)
            with detail_cols[0]:
                st.caption(f"📧 {email}")
            with detail_cols[1]:
                st.caption(f"📞 {telefone or 'N/A'}")
            with detail_cols[2]:
                st.caption(f"👤 {decisor_nome or 'N/A'}")
            with detail_cols[3]:
                st.caption(f"💼 {decisor_cargo or 'N/A'}")

        st.divider()


def render_progress_tracker(current_step: int, steps: List[str]):
    """
    Renderiza tracker de progresso visual usando componentes Streamlit nativos.

    Args:
        current_step: Índice do passo atual (0-based)
        steps: Lista de labels dos passos
    """
    cols = st.columns(len(steps))

    for i, (col, step) in enumerate(zip(cols, steps)):
        with col:
            if i < current_step:
                # Completed
                color = "#48bb78"
                icon = "✓"
            elif i == current_step:
                # Active
                color = "#667eea"
                icon = str(i + 1)
            else:
                # Pending
                color = "#cbd5e0"
                icon = str(i + 1)

            st.markdown(
                f'<div style="text-align:center;">'
                f'<div style="width:32px;height:32px;border-radius:50%;background:{color};color:white;display:inline-flex;align-items:center;justify-content:center;font-weight:600;font-size:14px;margin-bottom:4px;">{icon}</div>'
                f'<div style="font-size:11px;color:#718096;">{step}</div>'
                f'</div>',
                unsafe_allow_html=True
            )


def render_status_badge(status: str) -> str:
    """
    Retorna HTML de badge de status.

    Args:
        status: Status (sent, failed, pending)

    Returns:
        HTML string
    """
    return f'<span class="badge badge-status {status}">{status.upper()}</span>'


def render_skeleton_card():
    """Renderiza skeleton loading para cards"""
    st.markdown("""
    <div class="lead-card">
        <div class="lead-card-header">
            <div>
                <div class="skeleton" style="height: 1.25rem; width: 200px; margin-bottom: 0.5rem;"></div>
                <div class="skeleton" style="height: 0.875rem; width: 120px;"></div>
            </div>
            <div style="display: flex; gap: 0.375rem;">
                <div class="skeleton" style="height: 1.5rem; width: 40px; border-radius: 9999px;"></div>
                <div class="skeleton" style="height: 1.5rem; width: 50px; border-radius: 9999px;"></div>
            </div>
        </div>
        <div class="lead-details">
            <div class="skeleton" style="height: 1rem; width: 180px;"></div>
            <div class="skeleton" style="height: 1rem; width: 120px;"></div>
            <div class="skeleton" style="height: 1rem; width: 140px;"></div>
            <div class="skeleton" style="height: 1rem; width: 100px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_empty_state(message: str, icon: str = "📭"):
    """
    Renderiza estado vazio estilizado.

    Args:
        message: Mensagem para exibir
        icon: Emoji/ícone
    """
    st.markdown(f"""
    <div style="text-align: center; padding: 3rem 1rem; color: var(--gray-500);">
        <div style="font-size: 3rem; margin-bottom: 1rem;">{icon}</div>
        <div style="font-size: 1rem;">{message}</div>
    </div>
    """, unsafe_allow_html=True)


def render_success_message(title: str, message: str):
    """Renderiza mensagem de sucesso estilizada"""
    st.markdown(f"""
    <div style="background: var(--success-light); border-radius: 0.75rem; padding: 1.5rem; text-align: center;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">✅</div>
        <div style="font-weight: 600; color: var(--success-dark); font-size: 1.1rem;">{title}</div>
        <div style="color: var(--success-dark); margin-top: 0.5rem;">{message}</div>
    </div>
    """, unsafe_allow_html=True)


def render_error_message(title: str, message: str):
    """Renderiza mensagem de erro estilizada"""
    st.markdown(f"""
    <div style="background: var(--error-light); border-radius: 0.75rem; padding: 1.5rem; text-align: center;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">❌</div>
        <div style="font-weight: 600; color: var(--error-dark); font-size: 1.1rem;">{title}</div>
        <div style="color: var(--error-dark); margin-top: 0.5rem;">{message}</div>
    </div>
    """, unsafe_allow_html=True)


def render_info_box(title: str, items: List[str], icon: str = "ℹ️"):
    """
    Renderiza caixa de informações.

    Args:
        title: Título da caixa
        items: Lista de itens para exibir
        icon: Ícone
    """
    items_html = "".join([f"<li>{item}</li>" for item in items])

    st.markdown(f"""
    <div style="background: var(--info-light); border-radius: 0.75rem; padding: 1.25rem;">
        <div style="font-weight: 600; color: var(--info-dark); margin-bottom: 0.75rem;">
            {icon} {title}
        </div>
        <ul style="margin: 0; padding-left: 1.25rem; color: var(--info-dark);">
            {items_html}
        </ul>
    </div>
    """, unsafe_allow_html=True)


def render_status_indicator(label: str, status: bool, message: str = ""):
    """
    Renderiza indicador de status compacto.

    Args:
        label: Label do status
        status: True = ok, False = erro/warning
        message: Mensagem opcional
    """
    color = "var(--success-dark)" if status else "var(--warning-dark)"
    bg = "var(--success-light)" if status else "var(--warning-light)"
    icon = "✓" if status else "!"

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; background: {bg}; border-radius: 0.5rem;">
        <span style="width: 1.25rem; height: 1.25rem; border-radius: 50%; background: {color}; color: white; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: bold;">{icon}</span>
        <span style="font-size: 0.85rem; color: {color}; font-weight: 500;">{label}</span>
        {f'<span style="font-size: 0.75rem; color: {color}; opacity: 0.8;">- {message}</span>' if message else ''}
    </div>
    """, unsafe_allow_html=True)


def render_compact_metric(value: str, label: str, icon: str = "", color: str = "primary"):
    """
    Renderiza métrica compacta inline.

    Args:
        value: Valor principal
        label: Label
        icon: Ícone opcional
        color: Cor (primary, success, warning, error)
    """
    colors = {
        "primary": ("var(--primary-500)", "rgba(102, 126, 234, 0.1)"),
        "success": ("#48bb78", "var(--success-light)"),
        "warning": ("#ecc94b", "var(--warning-light)"),
        "error": ("#fc8181", "var(--error-light)")
    }
    text_color, bg_color = colors.get(color, colors["primary"])

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; background: {bg_color}; border-radius: 0.5rem; border-left: 3px solid {text_color};">
        {f'<span style="font-size: 1.25rem;">{icon}</span>' if icon else ''}
        <div>
            <div style="font-size: 1.25rem; font-weight: 700; color: {text_color}; line-height: 1;">{value}</div>
            <div style="font-size: 0.7rem; color: var(--gray-500); text-transform: uppercase;">{label}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_status_bar(statuses: List[Dict]):
    """
    Renderiza barra de status horizontal usando componentes Streamlit nativos.

    Args:
        statuses: Lista de dicts com {label, status (bool), message (optional)}
    """
    # Adiciona espaçamento vertical
    st.markdown('<div style="margin-bottom: 0.5rem;"></div>', unsafe_allow_html=True)

    cols = st.columns(len(statuses))
    for col, s in zip(cols, statuses):
        status_ok = s.get('status', False)
        color = "#48bb78" if status_ok else "#ecc94b"
        icon = "✓" if status_ok else "⚠"
        label = s.get('label', '')
        with col:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:6px;padding:8px 12px;background:#f7fafc;border-radius:8px;">'
                f'<span style="width:18px;height:18px;border-radius:50%;background:{color};color:white;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;">{icon}</span>'
                f'<span style="font-size:13px;color:#4a5568;">{label}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

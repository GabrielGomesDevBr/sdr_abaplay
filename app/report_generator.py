"""
Gerador de relatórios PDF para campanhas de email
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DESKTOP_PATH
from app.database import get_campaign, get_leads_by_campaign, get_email_log_by_campaign


def generate_campaign_report(campaign_id: int, 
                             valid_leads: List[Dict] = None, 
                             discarded_leads: List[Dict] = None) -> str:
    """
    Gera relatório PDF da campanha e salva na área de trabalho
    
    Args:
        campaign_id: ID da campanha
        valid_leads: Lista de leads válidos (opcional, busca do banco se não fornecido)
        discarded_leads: Lista de leads descartados
        
    Returns:
        Caminho do arquivo PDF gerado
    """
    # Busca dados da campanha
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campanha {campaign_id} não encontrada")
    
    # Busca leads e logs se não fornecidos
    if valid_leads is None:
        valid_leads = get_leads_by_campaign(campaign_id)
    
    email_logs = get_email_log_by_campaign(campaign_id)
    
    # Cria diretório se não existir
    DESKTOP_PATH.mkdir(parents=True, exist_ok=True)
    
    # Nome do arquivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    region_slug = campaign.get('region', 'campanha').replace(' ', '_').lower()
    filename = f"relatorio_email_{region_slug}_{timestamp}.pdf"
    filepath = DESKTOP_PATH / filename
    
    # Cria documento PDF
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=30,
        textColor=colors.HexColor('#1a365d')
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#2d3748')
    )
    normal_style = styles['Normal']
    
    # Elementos do documento
    elements = []
    
    # Título
    elements.append(Paragraph("📊 Relatório de Campanha de Email", title_style))
    elements.append(Paragraph(f"<b>Região:</b> {campaign.get('region', 'N/A')}", normal_style))
    elements.append(Paragraph(f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
    elements.append(Spacer(1, 20))
    
    # Resumo
    elements.append(Paragraph("📈 Resumo da Campanha", heading_style))
    
    sent_count = len([log for log in email_logs if log.get('status') == 'sent'])
    failed_count = len([log for log in email_logs if log.get('status') == 'failed'])
    pending_count = len([log for log in email_logs if log.get('status') == 'pending'])
    
    summary_data = [
        ["Métrica", "Valor"],
        ["Total de Leads Processados", str(len(valid_leads) + len(discarded_leads or []))],
        ["Leads Válidos", str(len(valid_leads))],
        ["Leads Descartados", str(len(discarded_leads or []))],
        ["Emails Enviados", str(sent_count)],
        ["Emails com Erro", str(failed_count)],
        ["Taxa de Sucesso", f"{(sent_count/(sent_count+failed_count)*100):.1f}%" if (sent_count+failed_count) > 0 else "N/A"],
    ]
    
    summary_table = Table(summary_data, colWidths=[10*cm, 5*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4299e1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Emails Enviados
    if email_logs:
        elements.append(Paragraph("📧 Detalhamento dos Envios", heading_style))
        
        email_data = [["#", "Clínica", "Email", "Status", "Horário"]]
        for i, log in enumerate(email_logs, 1):
            status_emoji = "✅" if log.get('status') == 'sent' else "❌" if log.get('status') == 'failed' else "⏳"
            sent_time = log.get('sent_at', '')
            if sent_time:
                try:
                    sent_time = datetime.fromisoformat(sent_time).strftime('%H:%M')
                except:
                    sent_time = str(sent_time)[:5]
            
            email_data.append([
                str(i),
                log.get('nome_clinica', 'N/A')[:25],
                log.get('email_to', 'N/A')[:30],
                f"{status_emoji} {log.get('status', 'N/A')}",
                sent_time
            ])
        
        email_table = Table(email_data, colWidths=[1*cm, 4.5*cm, 5.5*cm, 2.5*cm, 2*cm])
        email_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#48bb78')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 1), (2, -1), 'LEFT'),
        ]))
        elements.append(email_table)
        elements.append(Spacer(1, 30))
    
    # Leads Descartados
    if discarded_leads:
        elements.append(Paragraph("🚫 Leads Descartados", heading_style))
        
        discarded_data = [["Clínica", "Motivo"]]
        for lead in discarded_leads:
            discarded_data.append([
                lead.get('nome_clinica', 'N/A')[:30],
                lead.get('discard_reason', 'Não especificado')[:40]
            ])
        
        discarded_table = Table(discarded_data, colWidths=[7*cm, 8*cm])
        discarded_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fc8181')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fff5f5')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#feb2b2')),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        elements.append(discarded_table)
        elements.append(Spacer(1, 30))
    
    # Rodapé
    elements.append(Spacer(1, 20))
    footer_text = f"Gerado automaticamente por ABAplay Email Automation em {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
    elements.append(Paragraph(f"<i>{footer_text}</i>", ParagraphStyle(
        'Footer', parent=normal_style, fontSize=8, textColor=colors.gray, alignment=TA_CENTER
    )))
    
    # Gera PDF
    doc.build(elements)
    
    return str(filepath)


def generate_quick_summary(campaign_id: int, valid_leads: List[Dict], 
                          discarded_leads: List[Dict]) -> str:
    """
    Gera resumo rápido em texto para exibição
    
    Returns:
        String formatada com resumo
    """
    email_logs = get_email_log_by_campaign(campaign_id)
    sent_count = len([log for log in email_logs if log.get('status') == 'sent'])
    failed_count = len([log for log in email_logs if log.get('status') == 'failed'])
    
    summary = f"""
╔══════════════════════════════════════════════════════════════╗
║                    📊 RESUMO DA CAMPANHA                      ║
╠══════════════════════════════════════════════════════════════╣
║  📋 Total Processados:  {len(valid_leads) + len(discarded_leads):>4}                              ║
║  ✅ Leads Válidos:      {len(valid_leads):>4}                              ║
║  ❌ Leads Descartados:  {len(discarded_leads):>4}                              ║
║  📧 Emails Enviados:    {sent_count:>4}                              ║
║  ⚠️  Emails com Erro:    {failed_count:>4}                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    return summary

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from app.core.config import settings

def build_pdf_report(item: dict) -> bytes:
    buffer=BytesIO(); doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42)
    styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name="SmallMuted",parent=styles["BodyText"],textColor=colors.HexColor("#64748b"),fontSize=8))
    story=[Paragraph("FailureLab Experiment Report",styles["Title"]),Spacer(1,8),Paragraph(f"<b>{escape(str(item.get('name','Experiment')))}</b>",styles["Heading2"]),Paragraph(escape(str(item.get("summary") or "No summary available.")),styles["BodyText"]),Spacer(1,12)]
    rows=[["Experiment ID",escape(str(item.get("id","-")))],["Target",escape(str(item.get("target","-")))],["Scenario",escape(str(item.get("scenario","-")))],["Mode",escape(str(item.get("mode","-")))],["Status",escape(str(item.get("status","-")))],["Resilience score",escape(str(item.get("resilience_score","N/A")))],["Anomaly score",escape(str(item.get("anomaly_score","N/A")))]]
    table=Table(rows,colWidths=[125,350]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#eef2ff")),("TEXTCOLOR",(0,0),(0,-1),colors.HexColor("#334155")),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#cbd5e1")),("PADDING",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.extend([table,Spacer(1,14),Paragraph("Findings",styles["Heading2"])])
    for text in item.get("findings",[]): story.append(Paragraph(f"• {escape(str(text))}",styles["BodyText"]))
    story.extend([Spacer(1,8),Paragraph("Recommendations",styles["Heading2"])])
    for text in item.get("recommendations",[]): story.append(Paragraph(f"• {escape(str(text))}",styles["BodyText"]))
    story.extend([Spacer(1,8),Paragraph("Event timeline",styles["Heading2"])])
    for event in item.get("events",[]): story.append(Paragraph(f"{escape(str(event.get('timestamp','')))} · <b>{escape(str(event.get('level','info')).upper())}</b> · {escape(str(event.get('message','')))}",styles["SmallMuted"]))
    story.extend([Spacer(1,10),Paragraph("Method note: the resilience score is a project-defined comparative index. Anomaly and root-cause outputs are analytical hypotheses and should be verified against source telemetry.",styles["SmallMuted"])])
    doc.build(story); return buffer.getvalue()

def save_local_report(experiment_id: str, content: bytes) -> Path:
    directory=Path(settings.reports_dir); directory.mkdir(parents=True,exist_ok=True)
    path=directory/f"{experiment_id}.pdf"; path.write_bytes(content); return path

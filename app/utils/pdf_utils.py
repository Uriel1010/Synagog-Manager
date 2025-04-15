# file: app/utils/pdf_utils.py
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib import colors
from reportlab.lib.units import inch
from app.models import Event  # Type hinting
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from bidi.algorithm import get_display

# Register a TTF font that supports Hebrew.
pdfmetrics.registerFont(TTFont('HebrewFont', r'app/utils/David.ttf'))
print("DEBUG: pdf_utils module loaded", flush=True)

def generate_pdf_report(event: Event, purchase_details: list):
    print("DEBUG: generate_pdf_report is now running with the new code!", flush=True)
    """Generates a PDF report in Hebrew with full RTL alignment."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)

    # Base styles from ReportLab sample styles.
    base_styles = getSampleStyleSheet()

    # Custom paragraph styles for Hebrew (using right alignment).
    hebrew_right = ParagraphStyle(
        name='HebrewRight',
        parent=base_styles['Normal'],
        fontName='HebrewFont',
        alignment=TA_RIGHT,
        leading=16
    )
    hebrew_title = ParagraphStyle(
        name='HebrewTitle',
        parent=base_styles['h1'],
        fontName='HebrewFont',
        alignment=TA_CENTER,
        leading=20
    )
    hebrew_subheader = ParagraphStyle(
        name='HebrewSubheader',
        parent=base_styles['h3'],
        fontName='HebrewFont',
        alignment=TA_RIGHT,
        leading=16
    )

    story = []

    # Process dynamic event text for RTL.
    event_name_rtl = get_display(event.event_name)
    details_rtl = get_display(event.details) if event.details else ""
    
    # Prepare Hebrew date: if event.hebrew_date is "N/A" or empty, omit it.
    hebrew_date = event.hebrew_date if event.hebrew_date and event.hebrew_date.upper() != "N/A" else ""
    date_str = f"{event.gregorian_date.strftime('%Y-%m-%d')}"
    if hebrew_date:
        date_str += f" ({hebrew_date})"
    date_line = get_display(f"תאריך: {date_str}")

    # --- Title ---
    # Construct the title as "פרשת " + event name, then run get_display() on the whole title.
    title_plain = f"פרשת {event.event_name}"
    title_text = get_display(title_plain)
    story.append(Paragraph(title_text, hebrew_title))
    story.append(Paragraph(date_line, hebrew_right))
    if details_rtl:
        # Prepend a static label "פרטים:" to details.
        details_line = details_rtl + get_display("פרטים: ") 
        story.append(Paragraph(details_line, hebrew_right))
    story.append(Spacer(1, 0.2 * inch))

    # --- Group by Buyer ---
    purchases_by_buyer = {}
    for detail in purchase_details:
        buyer = detail['buyer_name']
        if buyer not in purchases_by_buyer:
            purchases_by_buyer[buyer] = []
        purchases_by_buyer[buyer].append(detail)

    story.append(Spacer(1, 0.1 * inch))
    for buyer_name, items in sorted(purchases_by_buyer.items()):
        buyer_name_rtl = get_display(buyer_name)
        story.append(Paragraph(buyer_name_rtl, hebrew_subheader))
        story.append(Spacer(1, 0.05 * inch))
        buyer_total = 0.0
        item_data = []
        for item_detail in items:
            original_item_name = item_detail['item_name']
            if item_detail['is_unique_item']:
                original_item_name = "*" + original_item_name
            item_name_rtl = get_display(original_item_name)
            price = item_detail['price']
            buyer_total += price
            item_data.append([
                Paragraph(f"₪{price:.0f}", hebrew_right),
                Paragraph(item_name_rtl, hebrew_right)
            ])
        if item_data:
            item_table = Table(item_data, colWidths=[3.5 * inch, 1.0 * inch])
            # Apply an explicit grid style with a 1-point black line.
            item_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(item_table)
            subtotal_line = f" ₪{buyer_total:.2f}"+get_display("סה\"כ: ")
            story.append(Paragraph(subtotal_line, hebrew_right))
        story.append(Spacer(1, 0.15 * inch))

    # --- Build PDF ---
    try:
        doc.build(story)
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Error building PDF: {e}", flush=True)
        return None

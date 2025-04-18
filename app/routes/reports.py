# file: app/routes/reports.py
import io
import pandas as pd
# --- Import quote from urllib.parse ---
from urllib.parse import quote
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    make_response, current_app
)
from flask_login import login_required
from sqlalchemy import func
from app import db
from app.models import Event, Purchase, Buyer, Item
from app.forms import ReportSelectionForm
from app.utils.pdf_utils import generate_pdf_report
from app.utils.hebrew_date_utils import get_hebrew_date_string

bp = Blueprint('reports', __name__)

@bp.route('/', methods=['GET', 'POST'])
@login_required
def select_report():
    """Allows user to select event and report type."""
    form = ReportSelectionForm()
    if form.validate_on_submit():
        event_id = form.event_id.data
        report_type = form.report_type.data
        return redirect(url_for('reports.generate_report',
                                event_id=event_id,
                                report_type=report_type))
    events_exist = Event.query.first() is not None
    return render_template('reports/select_report.html',
                           title='Select Report',
                           form=form,
                           events_exist=events_exist)

def rfc2231_encode(s):
    # This is a very basic illustration. In production, look for a robust solution.
    import urllib.parse
    return "UTF-8''" + urllib.parse.quote(s)

@bp.route('/view/<int:event_id>')
@login_required
def view_report(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash(f"Event with ID {event_id} not found.", "danger")
        return redirect(url_for('reports.select_report'))

    # Query purchase details for the report (similar to ReportDao)
    purchase_details = db.session.query(
            Buyer.name.label('buyer_name'),
            Item.name.label('item_name'),
            Purchase.total_price.label('price'),
            Item.is_unique.label('is_unique_item')
        ).join(Buyer, Purchase.buyer_id == Buyer.id)\
         .join(Item, Purchase.item_id == Item.id)\
         .filter(Purchase.event_id == event_id)\
         .order_by(Buyer.name, Purchase.timestamp)\
         .all() # Returns a list of Row objects (like named tuples)

    # Convert Row objects to dictionaries for easier handling in PDF util if needed
    details_list = [row._asdict() for row in purchase_details]

    # Generate PDF using the utility function
    pdf_buffer = generate_pdf_report(event, details_list)

    if pdf_buffer:
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        safe_event_name = rfc2231_encode(event.event_name)
        response.headers['Content-Disposition'] = f'inline; filename=Report_{safe_event_name}_{event.id}.pdf'
        return response
    else:
        flash("Failed to generate PDF report.", "danger")
        return redirect(url_for('reports.select_report'))
    
@bp.route('/generate/<report_type>/<int:event_id>')
@login_required
def generate_report(report_type, event_id):
    """Generates and serves the selected report."""
    event = db.session.get(Event, event_id)
    if not event:
        flash(f"Event with ID {event_id} not found.", "danger")
        return redirect(url_for('reports.select_report'))

    # Create a base filename (still useful for internal logic/logging)
    safe_event_name_internal = "".join(c if c.isalnum() or c in (' ', '-') else '_' for c in event.event_name).rstrip()
    filename_base_internal = f"Report_{safe_event_name_internal}_{event.gregorian_date.strftime('%Y%m%d')}"

    # --- Prepare filename parts for the header ---
    # Use the original event name for user-friendliness in the download prompt
    # Use quote() to percent-encode non-ASCII chars for the header value
    encoded_event_name = quote(event.event_name.encode('utf-8'))
    encoded_filename_base = f"Report_{encoded_event_name}_{event.gregorian_date.strftime('%Y%m%d')}"

    try:
        if report_type == 'pdf_summary':
            # --- Original PDF Summary ---
            purchase_details = db.session.query(
                    Buyer.name.label('buyer_name'), Item.name.label('item_name'),
                    Purchase.total_price.label('price'), Item.is_unique.label('is_unique_item')
                ).join(Buyer, Purchase.buyer_id == Buyer.id)\
                 .join(Item, Purchase.item_id == Item.id)\
                 .filter(Purchase.event_id == event_id)\
                 .order_by(Buyer.name, Purchase.timestamp).all()
            details_list = [row._asdict() for row in purchase_details]
            pdf_buffer = generate_pdf_report(event, details_list)

            if pdf_buffer:
                response = make_response(pdf_buffer.getvalue())
                response.headers['Content-Type'] = 'application/pdf'
                # --- Create RFC 6266 compliant header ---
                disposition = f"inline; filename*=UTF-8''{encoded_filename_base}_Summary.pdf"
                response.headers['Content-Disposition'] = disposition
                return response
            else:
                # ... (error handling) ...
                flash("Failed to generate PDF report.", "danger")
                return redirect(url_for('reports.select_report'))


        elif report_type.startswith('buyer_'):
            # --- Buyer Summary Report (Excel/CSV) ---
            # ... (query remains the same) ...
            summary_data = db.session.query( Buyer.name.label('Buyer Name'), db.func.sum(Purchase.total_price).label('Total Pledged/Purchased (NIS)') ).join(Purchase, Buyer.id == Purchase.buyer_id).filter(Purchase.event_id == event_id).group_by(Buyer.id, Buyer.name).order_by(Buyer.name).all()

            if not summary_data: # ... (error handling) ...
                flash(f"No purchase data found for event '{event.event_name}' to generate Buyer Summary.", "warning")
                return redirect(url_for('reports.select_report'))

            df = pd.DataFrame(summary_data)
            file_format = report_type.split('_')[1]
            # Pass the UTF-8 encoded base filename to the helper
            return _create_file_response(df, f"{encoded_filename_base}_BuyerSummary", file_format)

        elif report_type.startswith('item_'):
             # --- Item Summary Report (Excel/CSV) ---
             # ... (query remains the same) ...
            summary_data = db.session.query( Item.name.label('Item Name'), db.func.count(Purchase.id).label('Times Purchased'), db.func.sum(Purchase.total_price).label('Total Raised (NIS)') ).join(Purchase, Item.id == Purchase.item_id).filter(Purchase.event_id == event_id).group_by(Item.id, Item.name).order_by(Item.name).all()

            if not summary_data: # ... (error handling) ...
                flash(f"No purchase data found for event '{event.event_name}' to generate Item Summary.", "warning")
                return redirect(url_for('reports.select_report'))

            df = pd.DataFrame(summary_data)
            file_format = report_type.split('_')[1]
            # Pass the UTF-8 encoded base filename to the helper
            return _create_file_response(df, f"{encoded_filename_base}_ItemSummary", file_format)

        else: # ... (error handling) ...
            flash(f"Unknown report type: {report_type}", "danger")
            return redirect(url_for('reports.select_report'))

    except Exception as e: # ... (error handling) ...
        current_app.logger.error(f"Error generating report ({report_type}) for event {event_id}: {e}", exc_info=True)
        flash(f"An error occurred while generating the report: {e}", "danger")
        return redirect(url_for('reports.select_report'))


def _create_file_response(df: pd.DataFrame, encoded_filename_base: str, format: str):
    """Helper to generate CSV or Excel response from a DataFrame using correctly encoded filename."""
    output = io.BytesIO()
    filename_suffix = f".{format}"
    filename_header = f"{encoded_filename_base}{filename_suffix}" # This already has % encoding

    if format == 'csv':
        df.to_csv(output, index=False, encoding='utf-8-sig')
        mime_type = 'text/csv; charset=utf-8' # Explicitly state charset
    elif format == 'excel':
        try:
            writer = pd.ExcelWriter(output, engine='openpyxl')
            df.to_excel(writer, index=False, sheet_name='Summary')
            writer.close()
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        except Exception as e:
             current_app.logger.error(f"Error writing Excel file using openpyxl: {e}", exc_info=True)
             raise
    else:
        raise ValueError("Unsupported file format specified")

    output.seek(0)
    response = make_response(output.getvalue())
    # --- Create RFC 6266 compliant header ---
    # Use filename* for UTF-8 encoding. The filename_header is already percent-encoded.
    disposition = f'attachment; filename*={filename_header}'
    # Some older browsers might need the plain filename as fallback (without non-ASCII)
    # You could create a simplified ascii_filename_base here if needed.
    # disposition += f'; filename="{ascii_filename_base}{filename_suffix}"' # Optional fallback
    response.headers['Content-Disposition'] = disposition
    response.headers['Content-Type'] = mime_type
    return response
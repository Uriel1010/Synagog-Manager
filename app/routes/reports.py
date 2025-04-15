# file: app/routes/reports.py
import io
from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_required
from app import db
from app.models import Event, Purchase, Buyer, Item
from app.forms import ReportSelectionForm
from app.utils.pdf_utils import generate_pdf_report # Import the PDF generator utility

bp = Blueprint('reports', __name__)

@bp.route('/', methods=['GET', 'POST'])
@login_required
def select_report():
    form = ReportSelectionForm()
    if form.validate_on_submit():
        event_id = form.event_id.data
        # Redirect to the route that generates the PDF for the selected event
        return redirect(url_for('reports.view_report', event_id=event_id))
    return render_template('reports/select_report.html', title='Select Report', form=form)

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
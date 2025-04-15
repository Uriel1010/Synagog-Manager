# file: app/routes/scanning.py
import logging
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.forms import ManualPurchaseForm
from app.models import Event, Buyer, Item, Purchase

bp = Blueprint('scanning', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG) # Use DEBUG for development
logger = logging.getLogger(__name__)

@bp.route('/event/<int:event_id>', methods=['GET'])
@login_required
def start_scanning(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash(f"Event with ID {event_id} not found.", "danger")
        return redirect(url_for('main.list_events'))

    # Initialize or clear scanning state in the session
    session['scan_event_id'] = event.id
    session['scan_buyer_id'] = None
    session['scan_buyer_name'] = None
    session['scan_item_id'] = None
    session['scan_item_name'] = None
    session['scan_accumulated_price'] = 0.0

    # Create an instance of the manual purchase form
    manual_form = ManualPurchaseForm()

    return render_template(
        'scanning/scanner.html',
        title=f"Scan Purchases for {event.event_name}",
        event=event,
        manual_form=manual_form  # Pass the form instance into the context
    )


@bp.route('/process_scan', methods=['POST'])
@login_required
def process_scan():
    """
    Receives barcode data from client-side JS via AJAX/Fetch.
    Updates the scanning state stored in the session.
    Returns JSON response with status.
    """
    data = request.get_json()
    barcode_value = data.get('barcode')
    event_id_from_session = session.get('scan_event_id')
    response = {'status': 'error', 'message': 'Unknown error', 'state': get_current_scan_state()}

    logger.debug(f"Received barcode scan: {barcode_value} for session event {event_id_from_session}")

    if not barcode_value:
        response['message'] = 'No barcode data received.'
        logger.warning("Empty barcode data received.")
        return jsonify(response)

    if not event_id_from_session:
         response['message'] = 'Scanning session not initialized. Please select an event.'
         logger.error("Scanning attempted without session event ID.")
         return jsonify(response)

    # --- Core State Machine Logic (Similar to ViewModel) ---
    try:
        if barcode_value.startswith("BUYER:"):
            barcode_id = barcode_value.split(":", 1)[1]
            logger.info(f"Processing BUYER scan: {barcode_id}")
            # Save any pending item before switching buyer
            save_pending_purchase(session)
            buyer = Buyer.query.filter_by(barcode_id=barcode_id).first()
            if buyer:
                session['scan_buyer_id'] = buyer.id
                session['scan_buyer_name'] = buyer.name
                # Reset item/price for new buyer
                session['scan_item_id'] = None
                session['scan_item_name'] = None
                session['scan_accumulated_price'] = 0.0
                session.modified = True # Important: Mark session as modified
                response['status'] = 'success'
                response['message'] = f"Buyer: {buyer.name}. Scan Item."
                logger.info(f"Buyer set: {buyer.name}")
            else:
                response['message'] = f"Error: Buyer Barcode '{barcode_id}' not found."
                logger.warning(f"Buyer barcode not found: {barcode_id}")

        elif barcode_value.startswith("ITEM:"):
            barcode_id = barcode_value.split(":", 1)[1]
            logger.info(f"Processing ITEM scan: {barcode_id}")
            if not session.get('scan_buyer_id'):
                response['message'] = "Error: Scan Buyer first!"
                logger.warning("Item scanned before buyer.")
            else:
                # Save previous item if any
                save_pending_purchase(session)
                item = Item.query.filter_by(barcode_id=barcode_id).first()
                if item:
                    session['scan_item_id'] = item.id
                    session['scan_item_name'] = item.name
                    session['scan_accumulated_price'] = 0.0 # Reset price for new item
                    session.modified = True
                    response['status'] = 'success'
                    response['message'] = f"Item: {item.name}. Scan Price(s)."
                    logger.info(f"Item set: {item.name}")

                    # Check uniqueness (Optional Warning)
                    if item.is_unique:
                        count = Purchase.query.filter_by(event_id=event_id_from_session, item_id=item.id).count()
                        if count > 0:
                            response['message'] += f" WARNING: Unique item '{item.name}' already purchased!"
                            logger.warning(f"Unique item {item.name} scanned again for event {event_id_from_session}")
                else:
                    response['message'] = f"Error: Item Barcode '{barcode_id}' not found."
                    logger.warning(f"Item barcode not found: {barcode_id}")


        elif barcode_value.startswith("PRICE:"):
            price_str = barcode_value.split(":", 1)[1]
            logger.info(f"Processing PRICE scan: {price_str}")
            if not session.get('scan_item_id'):
                response['message'] = "Error: Scan Item first!"
                logger.warning("Price scanned before item.")
            else:
                try:
                    price = float(price_str)
                    session['scan_accumulated_price'] = session.get('scan_accumulated_price', 0.0) + price
                    session.modified = True
                    response['status'] = 'success'
                    price_formatted = f"{session['scan_accumulated_price']:.2f}"
                    response['message'] = f"Price ₪{price:.2f} added. Item Total: ₪{price_formatted}"
                    logger.info(f"Price added: {price}. New total: {session['scan_accumulated_price']}")
                except ValueError:
                    response['message'] = f"Error: Invalid price format '{price_str}'."
                    logger.error(f"Invalid price format scanned: {price_str}")

        else:
            response['message'] = f"Error: Unknown barcode format '{barcode_value}'"
            logger.warning(f"Unknown barcode format received: {barcode_value}")

    except Exception as e:
        logger.exception(f"Error processing scan: {e}") # Log full traceback
        response['message'] = f"Server error processing scan: {e}"

    response['state'] = get_current_scan_state() # Update state in response
    return jsonify(response)


@bp.route('/finish_event', methods=['POST'])
@login_required
def finish_event():
    """ Saves any pending purchase and clears the session state. """
    event_id = session.get('scan_event_id')
    logger.info(f"Finishing scanning for session event {event_id}")
    save_pending_purchase(session) # Save last item

    # Clear session state
    session.pop('scan_event_id', None)
    session.pop('scan_buyer_id', None)
    session.pop('scan_buyer_name', None)
    session.pop('scan_item_id', None)
    session.pop('scan_item_name', None)
    session.pop('scan_accumulated_price', None)
    session.modified = True
    logger.info("Scanning session cleared.")

    flash("Event scanning finished and session cleared.", "success")
    # Redirect to event list or dashboard
    return redirect(url_for('main.list_events'))

@bp.route('/manual_entry', methods=['POST'])
@login_required
def manual_entry():
    form = ManualPurchaseForm()
    if form.validate_on_submit():
        # Create a Purchase object using the form data
        purchase = Purchase(
            event_id=session.get('scan_event_id'),
            buyer_id=form.buyer_id.data,
            item_id=form.item_id.data,
            total_price=form.total_price.data,
            quantity=form.quantity.data,
            is_manual_entry=True,
            manual_entry_notes=form.manual_entry_notes.data
        )
        db.session.add(purchase)
        db.session.commit()
        flash('Manual purchase added successfully!', 'success')
    else:
        flash('Error in manual entry. Please check your input.', 'danger')
    # Redirect back to the scanning page or another appropriate location
    return redirect(url_for('scanning.start_scanning', event_id=session.get('scan_event_id')))

# --- Helper Functions ---
def get_current_scan_state():
    """ Returns the current scanning state from the session. """
    return {
        'event_id': session.get('scan_event_id'),
        'buyer_id': session.get('scan_buyer_id'),
        'buyer_name': session.get('scan_buyer_name'),
        'item_id': session.get('scan_item_id'),
        'item_name': session.get('scan_item_name'),
        'accumulated_price': session.get('scan_accumulated_price', 0.0)
    }

def save_pending_purchase(user_session):
    """ Checks session and saves the current item purchase if valid. """
    event_id = user_session.get('scan_event_id')
    buyer_id = user_session.get('scan_buyer_id')
    item_id = user_session.get('scan_item_id')
    price = user_session.get('scan_accumulated_price', 0.0)

    if event_id and buyer_id and item_id and price > 0.0:
        logger.info(f"Saving pending purchase: Event={event_id}, Buyer={buyer_id}, Item={item_id}, Price={price}")
        try:
            purchase = Purchase(
                event_id=event_id,
                buyer_id=buyer_id,
                item_id=item_id,
                total_price=price
                # timestamp is default=utcnow
            )
            db.session.add(purchase)
            db.session.commit()
            logger.info("Pending purchase saved successfully.")
            # Optionally clear item/price here, but the flow resets them on next scan
            # user_session['scan_item_id'] = None
            # user_session['scan_item_name'] = None
            # user_session['scan_accumulated_price'] = 0.0
            # user_session.modified = True # Mark modified if clearing parts of session
        except Exception as e:
            db.session.rollback() # Rollback on error
            logger.exception(f"Error saving pending purchase: {e}")
    else:
         logger.debug("Skipping save_pending_purchase: No valid buyer/item/price > 0 in session.")
         
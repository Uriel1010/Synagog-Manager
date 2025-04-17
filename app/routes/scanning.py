# file: app/routes/scanning.py

import logging
from flask import (
    Blueprint, render_template, request, jsonify,
    session, flash, redirect, url_for, current_app
)
from flask_login import login_required
from app import db
from app.forms import ManualPurchaseForm, DeleteForm
from app.models import Event, Buyer, Item, Purchase
# Use joinedload for efficient querying
from sqlalchemy.orm import joinedload
# Import func for lowercase comparison if needed
from sqlalchemy import func

bp = Blueprint('scanning', __name__)

# Use Flask's logger
logger = logging.getLogger(__name__)
# Configure logger further if needed (e.g., level, handler)
# logging.basicConfig(level=logging.DEBUG) # Example: Set level for debugging

@bp.route('/event/<int:event_id>', methods=['GET'])
@login_required
def start_scanning(event_id):
    logger.info(f"Attempting to start scanning for event_id: {event_id}")
    event = db.session.get(Event, event_id)
    if not event:
        logger.warning(f"Event with ID {event_id} not found.")
        flash(f"Event {event_id} not found.", "danger")
        return redirect(url_for('main.list_events'))

    # Reset scanning state in session
    session['scan_event_id']       = event.id
    session['scan_buyer_id']       = None
    session['scan_buyer_name']     = None
    session['scan_item_id']        = None
    session['scan_item_name']      = None
    session['scan_accumulated_price'] = 0.0
    session.modified = True
    logger.info(f"Session state reset for event {event.id}: {get_current_scan_state()}")

    return render_template(
        'scanning/scanner.html',
        event=event,
        manual_form=ManualPurchaseForm(), # Pass a fresh form
        delete_event_form=DeleteForm()    # Pass delete form for event deletion
    )


@bp.route('/process_scan', methods=['POST'])
@login_required
def process_scan():
    data     = request.get_json() or {}
    barcode  = data.get('barcode', '').strip()
    event_id = session.get('scan_event_id')

    logger.debug(f"Processing scan. Barcode: '{barcode}', Event ID from session: {event_id}")

    # Start response with current state
    response = {'status':'error', 'message':'', 'state': get_current_scan_state()}

    if not barcode:
        response['message'] = 'No barcode received.'
        logger.warning("Process scan called with empty barcode.")
        return jsonify(response)

    if not event_id:
        response['message'] = 'Error: No active event session. Please select an event.'
        logger.error("Process scan called but no 'scan_event_id' in session.")
        clear_scan_session_keys()
        response['state'] = get_current_scan_state()
        return jsonify(response), 400

    event = db.session.get(Event, event_id)
    if not event:
        response['message'] = f'Error: Event {event_id} not found in database.'
        logger.error(f"Event ID {event_id} from session not found in database.")
        clear_scan_session_keys()
        response['state'] = get_current_scan_state()
        return jsonify(response), 400

    try:
        # --- Buyer Scan ---
        if barcode.startswith('BUYER:'):
            # *** Save any pending purchase from the *previous* buyer/item ***
            save_pending_purchase(session)
            bid = barcode.split(':', 1)[1]
            logger.info(f"Scanned Buyer Barcode: {bid}")
            buyer = Buyer.query.filter_by(barcode_id=bid).first()
            if buyer:
                logger.info(f"Buyer found: {buyer.name} (ID: {buyer.id})")
                # Set new buyer, clear item and price from session state
                session.update({
                    'scan_buyer_id': buyer.id, 'scan_buyer_name': buyer.name,
                    'scan_item_id': None, 'scan_item_name': None,
                    'scan_accumulated_price': 0.0
                })
                session.modified = True
                response.update(status='success', message=f'Buyer set: {buyer.name}. Scan item.')
            else:
                logger.warning(f"Unknown buyer barcode scanned: '{bid}'")
                response['message'] = f"Unknown buyer barcode: '{bid}'."
                # Clear entire state (except event) if buyer not found
                clear_scan_session_keys(clear_event=False) # Keep event_id


        # --- Item Scan ---
        elif barcode.startswith('ITEM:'):
            if not session.get('scan_buyer_id'):
                logger.warning("Item scanned before buyer.")
                response['message'] = 'Scan buyer first.'
            else:
                # *** Save any pending purchase from the *previous* item ***
                save_pending_purchase(session)
                iid = barcode.split(':', 1)[1]
                logger.info(f"Scanned Item Barcode: {iid}")
                item = Item.query.filter_by(barcode_id=iid).first()
                if item:
                    logger.info(f"Item found: {item.name} (ID: {item.id}), Unique: {item.is_unique}")
                    # Set new item, MUST reset accumulated price to 0 for this new item scan
                    session.update({
                        'scan_item_id': item.id, 'scan_item_name': item.name,
                        'scan_accumulated_price': 0.0 # <<< Reset price for the new item
                    })
                    session.modified = True
                    msg = f"Item set: {item.name}. Scan price(s)."
                    # Check uniqueness constraint (optional but good)
                    if item.is_unique:
                        existing = Purchase.query.filter_by(event_id=event_id, item_id=item.id).first()
                        if existing:
                            logger.warning(f"Unique item '{item.name}' already purchased by Buyer ID {existing.buyer_id}.")
                            msg += f" ⚠️ Already purchased by {existing.buyer.name}!"
                    response.update(status='success', message=msg)
                else:
                    logger.warning(f"Unknown item barcode scanned: '{iid}'")
                    response['message'] = f"Unknown item barcode: '{iid}'."
                    # Clear only item/price if item not found
                    session.update({'scan_item_id': None, 'scan_item_name': None, 'scan_accumulated_price': 0.0})
                    session.modified = True

        # --- Price Scan ---
        elif barcode.startswith('PRICE:'):
            # Check if we have a buyer and item selected first
            if not session.get('scan_item_id'):
                logger.warning("Price scanned before item.")
                response['message'] = 'Scan item first.'
            elif not session.get('scan_buyer_id'):
                 logger.warning("Price scanned before buyer.")
                 response['message'] = 'Scan buyer first.'
            else:
                # We have a buyer and an item, proceed to add price
                try:
                    price_str = barcode.split(':', 1)[1]
                    price = float(price_str)
                    logger.info(f"Scanned Price: {price}")

                    # *** Accumulate the price in the session ***
                    current_total = session.get('scan_accumulated_price', 0.0)
                    new_total = current_total + price
                    session['scan_accumulated_price'] = new_total
                    session.modified = True
                    logger.info(f"Accumulated price for item '{session.get('scan_item_name')}' updated to: {new_total}")

                    # *** DO NOT SAVE YET ***
                    # *** DO NOT RESET ITEM/PRICE STATE YET ***

                    # Update response to show the *new accumulated total*
                    response.update(
                        status='success',
                        message=(
                          f"Added ₪{price:.2f}. "
                          f"Current total for {session.get('scan_item_name', 'item')} is ₪{new_total:.2f}. "
                          f"Scan another price or next item/buyer."
                        )
                    )

                except ValueError:
                    logger.warning(f"Invalid price format scanned: '{price_str}'")
                    response['message'] = f"Invalid price format: '{price_str}'."
                except Exception as e_price:
                    logger.exception(f"Error processing price scan: {e_price}")
                    response['message'] = 'Error processing price.'

        # --- Clear Command ---
        elif barcode == 'BUYER:__CLEAR__':
            logger.info("Received clear state command.")
            # *** Save any pending purchase before clearing ***
            save_pending_purchase(session)
            clear_scan_session_keys(clear_event=False) # Keep event id
            response.update(status='success', message='State cleared. Scan buyer.')

        # --- Unknown Barcode Format ---
        else:
            logger.warning(f"Unrecognized barcode format scanned: '{barcode}'")
            response['message'] = f"Unrecognized barcode format: '{barcode}'."

    except Exception as e:
        logger.exception(f"Unexpected error during scan processing for barcode '{barcode}': {e}")
        response['message'] = 'A server error occurred during processing.'
        response['status'] = 'error'

    # Update response state (reflects current accumulation) and purchase list
    response['state'] = get_current_scan_state()
    try:
        response['purchases'] = _get_list(event_id)
    except Exception as e_list:
        logger.exception(f"Error fetching purchase list after scan: {e_list}")
        response['purchases'] = [] # Return empty list on error

    logger.debug(f"Scan process finished. Response: {response}")
    return jsonify(response)


@bp.route('/finish_event', methods=['POST'])
@login_required
def finish_event():
    event_id = session.get('scan_event_id')
    logger.info(f"Finishing scanning for event ID: {event_id}. Saving any pending purchase.")
    # *** Save the very last pending purchase ***
    save_pending_purchase(session)
    clear_scan_session_keys()
    session.modified = True
    flash("Finished scanning session.", "success")
    logger.info("Scanning session finished and state cleared.")
    return redirect(url_for('main.list_events'))


# *** Renamed route to match older JS call ***
@bp.route('/scan/purchases', methods=['GET'])
@login_required
def list_purchases():
    """Endpoint specifically for fetching the current purchase list via JS."""
    event_id = session.get('scan_event_id')
    logger.info(f"'/scan/purchases' GET endpoint called. Event ID from session: {event_id}")

    if not event_id:
        logger.warning("'/scan/purchases' called with no event_id in session.")
        # Return error and empty list, consistent with JS expectations
        return jsonify({'purchases': [], 'error': 'No active event session'}), 400

    try:
        # *** Use the consistent helper name ***
        purchase_list = _get_list(event_id)
        logger.info(f"Returning {len(purchase_list)} purchases for event {event_id}.")
        return jsonify({'purchases': purchase_list})
    except Exception as e:
        logger.exception(f"Error getting purchase list for event {event_id}: {e}")
        # Return error and empty list, consistent with JS expectations
        return jsonify({'purchases': [], 'error': 'Failed to retrieve purchase list'}), 500


# *** Renamed route to match older JS call ***
@bp.route('/scan/purchase/<int:pid>', methods=['DELETE'])
@login_required
def delete_purchase(pid):
    event_id = session.get('scan_event_id')
    logger.info(f"Attempting DELETE '/scan/purchase/{pid}' for event ID: {event_id}")

    if not event_id:
         logger.warning(f"Attempt to delete purchase {pid} but no event_id in session.")
         return jsonify({'success': False, 'message': 'No active event session'}), 400

    p = db.session.get(Purchase, pid)

    if not p:
        logger.warning(f"Purchase ID {pid} not found for deletion.")
        return jsonify({'success': False, 'message': 'Purchase not found'}), 404

    if p.event_id != event_id:
         logger.error(f"Security violation: Attempt to delete purchase {pid} (Event {p.event_id}) from session for Event {event_id}.")
         return jsonify({'success': False, 'message': 'Purchase does not belong to the current event'}), 403

    try:
        db.session.delete(p)
        db.session.commit()
        logger.info(f"Purchase ID {pid} deleted successfully for event {event_id}.")
        # Return success consistent with older JS expectation
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error deleting purchase ID {pid}: {e}")
        return jsonify({'success': False, 'message': 'Database error during deletion'}), 500


# *** Renamed route to match older JS call ***
@bp.route('/scan/add_buyer', methods=['POST'])
@login_required
def add_buyer():
    data = request.get_json() or {}
    name = data.get('name','').strip()
    logger.info(f"Attempting POST '/scan/add_buyer' with name: '{name}'")

    if not name:
        logger.warning("Add buyer request rejected: Name is missing.")
        return jsonify({'error': 'Buyer name cannot be empty.'}), 400

    # Optional: Check for existing name (case-insensitive)
    existing = Buyer.query.filter(func.lower(Buyer.name) == func.lower(name)).first()
    if existing:
         logger.warning(f"Add buyer rejected: Name '{name}' already exists (ID: {existing.id}).")
         # Return error consistent with older JS expectation
         return jsonify({'error': f"Buyer name '{name}' already exists."}), 400 # Use 400 or 409 Conflict

    try:
        from app.utils.barcode_utils import generate_next_barcode_id
        next_barcode = generate_next_barcode_id('B', starting_num=1001)
        if not next_barcode:
             logger.error("Failed to generate next barcode ID for new buyer.")
             return jsonify({'error':'Could not generate barcode ID.'}), 500

        logger.info(f"Generated barcode for new buyer '{name}': {next_barcode}")
        b = Buyer(name=name, barcode_id=next_barcode)
        db.session.add(b)
        db.session.commit()
        logger.info(f"Buyer '{b.name}' (ID: {b.id}, Barcode: {b.barcode_id}) created.")
        # Return format consistent with older JS expectation
        return jsonify({'id': b.id, 'name': b.name, 'barcode_id': b.barcode_id})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error adding new buyer '{name}': {e}")
        return jsonify({'error': 'Database error while adding buyer.'}), 500


# *** Renamed route to match older JS call ***
@bp.route('/scan/add_item', methods=['POST'])
@login_required
def add_item():
    data = request.get_json() or {}
    name = data.get('name','').strip()
    logger.info(f"Attempting POST '/scan/add_item' with name: '{name}'")

    if not name:
        logger.warning("Add item request rejected: Name is missing.")
        return jsonify({'error': 'Item name cannot be empty.'}), 400

    existing = Item.query.filter(func.lower(Item.name) == func.lower(name)).first()
    if existing:
         logger.warning(f"Add item rejected: Name '{name}' already exists (ID: {existing.id}).")
         return jsonify({'error': f"Item name '{name}' already exists."}), 400

    try:
        from app.utils.barcode_utils import generate_next_barcode_id
        next_barcode = generate_next_barcode_id('I', starting_num=5001)
        if not next_barcode:
             logger.error("Failed to generate next barcode ID for new item.")
             return jsonify({'error': 'Could not generate barcode ID.'}), 500

        logger.info(f"Generated barcode for new item '{name}': {next_barcode}")
        it = Item(name=name, barcode_id=next_barcode, is_unique=False)
        db.session.add(it)
        db.session.commit()
        logger.info(f"Item '{it.name}' (ID: {it.id}, Barcode: {it.barcode_id}) created.")
        # Return format consistent with older JS expectation
        return jsonify({'id': it.id, 'name': it.name, 'barcode_id': it.barcode_id})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error adding new item '{name}': {e}")
        return jsonify({'error': 'Database error while adding item.'}), 500


@bp.route('/manual_entry', methods=['POST'])
@login_required
def manual_entry():
    """Handles manual purchase entries submitted from the form."""
    event_id = session.get('scan_event_id')
    logger.info(f"Attempting manual entry for event ID: {event_id}")

    if not event_id:
        logger.error("Manual entry failed: No event_id in session.")
        # Return error format consistent with older JS expectation
        return jsonify({'errors': {'session': 'No active event session.'}}), 400

    form = ManualPurchaseForm() # Populates with request.form data

    logger.debug(f"Manual entry form data received: {request.form.to_dict()}")

    if form.validate_on_submit():
        logger.info("Manual entry form validated successfully.")
        price = form.total_price.data if form.total_price.data is not None else 0.0
        qty = form.quantity.data or 1

        try:
            p = Purchase(
                event_id=event_id, buyer_id=form.buyer_id.data,
                item_id=form.item_id.data, total_price=price, quantity=qty,
                is_manual_entry=True,
                manual_entry_notes=form.manual_entry_notes.data.strip() or None
            )
            db.session.add(p)
            db.session.commit()
            logger.info(f"Manual purchase (ID: {p.id}) added successfully.")

            # Return updated list, consistent with older JS expectation
            # *** Use the consistent helper name ***
            return jsonify({'purchases': _get_list(event_id)})

        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error saving manual purchase to database: {e}")
            return jsonify({'errors': {'database': 'Error saving purchase.'}}), 500
    else:
        logger.warning(f"Manual entry form validation failed. Errors: {form.errors}")
        # Return errors consistent with older JS expectation
        return jsonify({'errors': form.errors}), 400


# --- Helper Functions ---

def get_current_scan_state():
    """Returns the current scanning state from the session."""
    state = {
        'buyer_name': session.get('scan_buyer_name',''),
        'item_name':  session.get('scan_item_name',''),
        'accumulated_price': session.get('scan_accumulated_price', 0.0),
        # Include IDs for potential debugging or state display needs
        'event_id': session.get('scan_event_id'),
        'buyer_id': session.get('scan_buyer_id'),
        'item_id': session.get('scan_item_id'),
    }
    return state

def save_pending_purchase(user_session):
    """
    Saves a purchase to the database if a buyer, item, and event are
    currently set in the session. Uses the 'scan_accumulated_price'.
    This function is called *before* changing the buyer or item,
    or when finishing/clearing.
    """
    eid = user_session.get('scan_event_id')
    bid = user_session.get('scan_buyer_id')
    iid = user_session.get('scan_item_id')
    # *** Use the accumulated price from the session ***
    price = user_session.get('scan_accumulated_price', 0.0)

    # Check if all required IDs are present AND if a price has been scanned/accumulated
    # (We might not want to save if price is still 0, unless explicitly desired)
    # Let's save even if price is 0, as it might represent a 'claimed' item.
    if eid and bid and iid:
        logger.info(f"Attempting save_pending_purchase: E={eid}, B={bid}, I={iid}, Accumulated Price={price}")
        try:
            # Check if this exact item was already purchased by someone else if it's unique
            # (Consider if this check is needed here or only on ITEM scan)
            item = db.session.get(Item, iid)
            if item and item.is_unique:
                existing = Purchase.query.filter(
                    Purchase.event_id == eid,
                    Purchase.item_id == iid,
                    Purchase.buyer_id != bid # Check if bought by *someone else*
                ).first()
                if existing:
                    logger.warning(f"SAVE BLOCKED: Unique item '{item.name}' (ID:{iid}) already purchased by Buyer {existing.buyer_id} in Event {eid}. Cannot save for Buyer {bid}.")
                    # Optionally flash a message or handle this in the response?
                    # For now, just log and don't save.
                    return # Exit the function, do not save

            purchase = Purchase(
                event_id=eid, buyer_id=bid, item_id=iid,
                total_price=price, quantity=1, # Assume quantity 1 for scans
                is_manual_entry=False # This is for scanned entries
            )
            db.session.add(purchase)
            db.session.commit()
            logger.info(f"Pending purchase saved (ID: {purchase.id}). E={eid}, B={bid}, I={iid}, Price={price}")
            # Important: Do NOT clear state here. The calling function (process_scan)
            # decides when to clear parts of the state (e.g., item/price).
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Failed save_pending_purchase (E:{eid}, B:{bid}, I:{iid}, P:{price}): {e}")
    else:
        # Log only if something *was* partially set, indicating an incomplete state that wasn't saved.
        if eid and (bid or iid):
             logger.debug(f"No complete pending purchase to save. State: E={eid}, B={bid}, I={iid}")
        # Otherwise, it's normal (e.g., first scan after loading page), do nothing.


# *** Renamed helper to match newer code standard, keeping older logic/format ***
def _get_list(event_id):
    """Helper to retrieve and format the purchase list for a given event ID."""
    logger.debug(f"Helper _get_list called for event_id: {event_id}")
    if not event_id:
        logger.warning("_get_list called with no event_id, returning empty list.")
        return []

    try:
        # Eager load related Buyer and Item using joinedload
        purchases = Purchase.query.options(
            joinedload(Purchase.buyer),
            joinedload(Purchase.item)
        ).filter_by(event_id=event_id).order_by(Purchase.timestamp.asc()).all() # Order by oldest first

        logger.info(f"_get_list found {len(purchases)} purchases for event {event_id}.")

        result_list = []
        for r in purchases:
            buyer_name = r.buyer.name if r.buyer else "Unknown Buyer"
            item_name = r.item.name if r.item else "Unknown Item"

            result_list.append({
                'id': r.id,
                'buyer': buyer_name,
                'item': item_name,
                'price': r.total_price,
                'quantity': r.quantity,
                'notes': r.manual_entry_notes or '',
                # Use the timestamp format consistent with the older working version if needed,
                # but ISO format might be better for JS date parsing if required later.
                'time': r.timestamp.strftime('%Y-%m-%d %H:%M:%S') if r.timestamp else None,
                'manual': r.is_manual_entry
            })
        return result_list

    except Exception as e:
        logger.exception(f"Database error in _get_list for event {event_id}: {e}")
        return [] # Return empty list on error to prevent breaking UI

def clear_scan_session_keys(clear_event=True):
    """Removes scanning-related keys from the session."""
    keys_to_clear = [
        'scan_buyer_id', 'scan_buyer_name',
        'scan_item_id', 'scan_item_name', 'scan_accumulated_price'
    ]
    if clear_event:
        keys_to_clear.append('scan_event_id')

    cleared_count = 0
    for key in keys_to_clear:
        if key in session:
            session.pop(key, None)
            cleared_count += 1
    if cleared_count > 0:
        session.modified = True
    logger.info(f"Cleared {cleared_count} scanning keys from session (clear_event={clear_event}).")
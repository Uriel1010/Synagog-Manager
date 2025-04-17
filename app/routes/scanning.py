# file: app/routes/scanning.py
import logging
from flask import (
    Blueprint, render_template, request, jsonify,
    session, flash, redirect, url_for
)
from flask_login import login_required
from app import db
from app.forms import ManualPurchaseForm, DeleteForm
from app.models import Event, Buyer, Item, Purchase

bp = Blueprint('scanning', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@bp.route('/event/<int:event_id>', methods=['GET'])
@login_required
def start_scanning(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash(f"Event with ID {event_id} not found.", "danger")
        return redirect(url_for('main.list_events'))

    # Initialize or reset scanning state
    session['scan_event_id'] = event.id
    session['scan_buyer_id'] = None
    session['scan_buyer_name'] = None
    session['scan_item_id'] = None
    session['scan_item_name'] = None
    session['scan_accumulated_price'] = 0.0

    manual_form = ManualPurchaseForm()
    delete_event_form = DeleteForm()

    return render_template(
        'scanning/scanner.html',
        event=event,
        manual_form=manual_form,
        delete_event_form=delete_event_form
    )


@bp.route('/process_scan', methods=['POST'])
@login_required
def process_scan():
    data = request.get_json()
    barcode = data.get('barcode', '')
    event_id = session.get('scan_event_id')
    response = {'status': 'error', 'message': '', 'state': get_current_scan_state()}

    if not barcode:
        response['message'] = 'No barcode received.'
        return jsonify(response)
    if not event_id:
        response['message'] = 'No active event.'
        return jsonify(response)

    try:
        # Buyer scan
        if barcode.startswith("BUYER:"):
            save_pending_purchase(session)
            bid = barcode.split(":", 1)[1]
            buyer = Buyer.query.filter_by(barcode_id=bid).first()
            if buyer:
                session.update({
                    'scan_buyer_id': buyer.id,
                    'scan_buyer_name': buyer.name,
                    'scan_item_id': None,
                    'scan_item_name': None,
                    'scan_accumulated_price': 0.0
                })
                response.update(
                    status='success',
                    message=f"Buyer: {buyer.name}. Now scan item."
                )
            else:
                response['message'] = f"Unknown buyer '{bid}'."

        # Item scan
        elif barcode.startswith("ITEM:"):
            if not session.get('scan_buyer_id'):
                response['message'] = 'Scan buyer first.'
            else:
                save_pending_purchase(session)
                iid = barcode.split(":", 1)[1]
                item = Item.query.filter_by(barcode_id=iid).first()
                if item:
                    session.update({
                        'scan_item_id': item.id,
                        'scan_item_name': item.name,
                        'scan_accumulated_price': 0.0
                    })
                    msg = f"Item: {item.name}. Now scan price(s)."
                    if item.is_unique and Purchase.query.filter_by(
                        event_id=event_id, item_id=item.id
                    ).count():
                        msg += " ⚠️ unique item already used."
                    response.update(status='success', message=msg)
                else:
                    response['message'] = f"Unknown item '{iid}'."

        # Price scan
        elif barcode.startswith("PRICE:"):
            if not session.get('scan_item_id'):
                response['message'] = 'Scan item first.'
            else:
                try:
                    price = float(barcode.split(":", 1)[1])
                    session['scan_accumulated_price'] += price
                    response.update(
                        status='success',
                        message=(
                            f"Added ₪{price:.2f}. "
                            f"Total: ₪{session['scan_accumulated_price']:.2f}"
                        )
                    )
                except ValueError:
                    response['message'] = 'Invalid price.'

        else:
            response['message'] = f"Unknown code '{barcode}'."

    except Exception as e:
        logger.exception(e)
        response['message'] = 'Server error.'

    # Return updated state + full purchases list
    response['state'] = get_current_scan_state()
    response['purchases'] = _get_purchases_list(event_id)
    return jsonify(response)


@bp.route('/finish_event', methods=['POST'])
@login_required
def finish_event():
    event_id = session.get('scan_event_id')
    logger.info(f"Finishing scanning for event {event_id}")
    save_pending_purchase(session)
    for key in (
        'scan_event_id',
        'scan_buyer_id',
        'scan_buyer_name',
        'scan_item_id',
        'scan_item_name',
        'scan_accumulated_price'
    ):
        session.pop(key, None)
    session.modified = True
    flash("Event scanning finished and session cleared.", "success")
    return redirect(url_for('main.list_events'))


@bp.route('/scan/purchases', methods=['GET'])
@login_required
def list_purchases():
    eid = session.get('scan_event_id')
    return jsonify({'purchases': _get_purchases_list(eid)})


@bp.route('/scan/purchase/<int:pid>', methods=['DELETE'])
@login_required
def delete_purchase(pid):
    purchase = db.session.get(Purchase, pid)
    if not purchase or purchase.event_id != session.get('scan_event_id'):
        return jsonify({'success': False}), 404
    db.session.delete(purchase)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/scan/add_buyer', methods=['POST'])
@login_required
def add_buyer():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    last = Buyer.query.filter(Buyer.barcode_id.like('B%')) \
                      .order_by(Buyer.id.desc()).first()
    try:
        num = int(last.barcode_id.lstrip('B')) + 1
    except:
        num = 1001
    code = f'B{num}'
    buyer = Buyer(name=name, barcode_id=code)
    db.session.add(buyer)
    db.session.commit()
    return jsonify({'id': buyer.id, 'name': buyer.name, 'barcode_id': buyer.barcode_id})


@bp.route('/scan/add_item', methods=['POST'])
@login_required
def add_item():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    last = Item.query.filter(Item.barcode_id.like('I%')) \
                     .order_by(Item.id.desc()).first()
    try:
        num = int(last.barcode_id.lstrip('I')) + 1
    except:
        num = 5001
    code = f'I{num}'
    item = Item(name=name, barcode_id=code, is_unique=False)
    db.session.add(item)
    db.session.commit()
    return jsonify({'id': item.id, 'name': item.name, 'barcode_id': item.barcode_id})


@bp.route('/manual_entry', methods=['POST'])
@login_required
def manual_entry():
    form = ManualPurchaseForm()
    if form.validate_on_submit():
        # Treat blank price as zero
        price = form.total_price.data if form.total_price.data is not None else 0.0
        p = Purchase(
            event_id=session['scan_event_id'],
            buyer_id=form.buyer_id.data,
            item_id=form.item_id.data,
            total_price=price,
            quantity=form.quantity.data,
            is_manual_entry=True,
            manual_entry_notes=form.manual_entry_notes.data
        )
        db.session.add(p)
        db.session.commit()
        if request.is_json:
            return jsonify({'purchases': _get_purchases_list(session['scan_event_id'])})
        flash('Manual purchase added successfully!', 'success')
    else:
        if request.is_json:
            return jsonify({'errors': form.errors}), 400
        flash('Error in manual entry. Please check your input.', 'danger')
    return redirect(url_for('scanning.start_scanning', event_id=session.get('scan_event_id')))


def get_current_scan_state():
    return {
        'event_id': session.get('scan_event_id'),
        'buyer_id': session.get('scan_buyer_id'),
        'buyer_name': session.get('scan_buyer_name'),
        'item_id': session.get('scan_item_id'),
        'item_name': session.get('scan_item_name'),
        'accumulated_price': session.get('scan_accumulated_price', 0.0)
    }


def save_pending_purchase(user_session):
    """ Always save even if price is zero """
    eid = user_session.get('scan_event_id')
    bid = user_session.get('scan_buyer_id')
    iid = user_session.get('scan_item_id')
    price = user_session.get('scan_accumulated_price', 0.0)

    # Changed to >= 0.0 so zero-cost purchases are saved
    if eid and bid and iid and price >= 0.0:
        try:
            purchase = Purchase(
                event_id=eid,
                buyer_id=bid,
                item_id=iid,
                total_price=price
            )
            db.session.add(purchase)
            db.session.commit()
        except Exception:
            db.session.rollback()


def _get_purchases_list(event_id):
    if not event_id:
        return []
    rows = Purchase.query.filter_by(event_id=event_id) \
                         .order_by(Purchase.timestamp).all()
    return [{
        'id':       r.id,
        'buyer':    r.buyer.name,
        'item':     r.item.name,
        'price':    r.total_price,
        'quantity': r.quantity,
        'notes':    r.manual_entry_notes or '',
        'time':     r.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'manual':   r.is_manual_entry
    } for r in rows]

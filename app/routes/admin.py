# file: app/routes/admin.py
import io # For in-memory buffer
import pandas as pd # For Excel generation
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    abort, make_response, jsonify, current_app # Added make_response, jsonify
)
from flask_login import login_required, current_user
from app import db
from app.models import Buyer, Item, Purchase, Event
from app.forms import BuyerForm, ItemForm, DeleteForm
from app.utils.barcode_utils import generate_barcode_uri
from sqlalchemy.orm import joinedload # Import joinedload for efficient queries

# from app.forms import BuyerForm, ItemForm, DeleteForm # Already imported

bp = Blueprint('admin', __name__)


# Decorator for admin-only access (Example)
from functools import wraps

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@admin_required
def index():
    return render_template('admin/index.html', title='Admin Panel')

# --- Buyer CRUD ---
# ... (create_buyer, list_buyers, edit_buyer, delete_buyer remain the same) ...
@bp.route('/buyers')
@admin_required
def list_buyers():
    buyers = Buyer.query.order_by(Buyer.name).all()
    delete_form = DeleteForm() # <<< Create instance here
    return render_template(
        'admin/buyers_list.html',
        title='Manage Buyers',
        buyers=buyers,
        delete_form=delete_form # <<< Pass instance to template
    )

@bp.route('/buyer/new', methods=['GET', 'POST'])
@admin_required
def create_buyer():
    form = BuyerForm()
    if form.validate_on_submit():
        # Auto-generate barcode if left blank
        if not form.barcode_id.data:
            # Query the last created buyer that has a barcode starting with 'B'
            last_buyer = Buyer.query.filter(Buyer.barcode_id.like('B%')).order_by(Buyer.id.desc()).first()
            if last_buyer:
                # Extract the numeric part and increment it. Ensure to handle non-integer cases.
                try:
                    last_number = int(last_buyer.barcode_id.lstrip('B'))
                    new_number = last_number + 1
                except ValueError:
                    new_number = 1001  # Fallback if the previous barcode isn't in the expected format
            else:
                new_number = 1001  # Start sequence if no buyer exists
            generated_barcode = f'B{new_number}'
        else:
            generated_barcode = form.barcode_id.data

        buyer = Buyer(name=form.name.data, barcode_id=generated_barcode)
        db.session.add(buyer)
        db.session.commit()
        flash('Buyer created successfully!', 'success')
        return redirect(url_for('admin.list_buyers'))
    return render_template('admin/buyer_form.html', title='New Buyer', form=form, legend='New Buyer')

@bp.route('/buyer/edit/<int:buyer_id>', methods=['GET', 'POST'])
@admin_required
def edit_buyer(buyer_id):
    buyer = db.session.get(Buyer, buyer_id)
    if not buyer:
        abort(404)
    form = BuyerForm() # Create instance before checking request method

    if form.validate_on_submit():
        # Check validation result (important!)
        buyer.name = form.name.data
        buyer.barcode_id = form.barcode_id.data
        db.session.commit()
        flash('Buyer updated successfully!', 'success')
        return redirect(url_for('admin.list_buyers'))
    elif request.method == 'GET':
        # Pre-populate form
        form.name.data = buyer.name
        form.barcode_id.data = buyer.barcode_id
        form.original_barcode_id.data = buyer.barcode_id # Populate hidden field

    # Pass the original buyer barcode ID to the template even on POST validation error
    # so the hidden field gets repopulated.
    if not form.original_barcode_id.data:
         form.original_barcode_id.data = buyer.barcode_id

    return render_template('admin/buyer_form.html', title='Edit Buyer', form=form, legend='Edit Buyer')

@bp.route('/buyer/delete/<int:buyer_id>', methods=['POST'])
@admin_required
def delete_buyer(buyer_id):
    buyer = db.session.get(Buyer, buyer_id)
    if not buyer:
        abort(404)

    # Check if buyer has purchases - prevent deletion if they do (based on model relationship)
    if buyer.purchases.first():
         flash('Cannot delete buyer because they have associated purchases. Consider marking as inactive instead (feature not implemented).', 'danger')
         return redirect(url_for('admin.list_buyers'))

    form = DeleteForm()
    if form.validate_on_submit():
        db.session.delete(buyer)
        db.session.commit()
        flash('Buyer deleted successfully!', 'success')
    else:
        flash('Error deleting buyer. Please try again.', 'danger')

    return redirect(url_for('admin.list_buyers'))


# --- Item CRUD ---
# ... (create_item, list_items, edit_item, delete_item remain the same) ...
@bp.route('/items')
@admin_required
def list_items():
    items = Item.query.order_by(Item.name).all()
    delete_form = DeleteForm() # <<< Create instance here
    return render_template(
        'admin/items_list.html',
        title='Manage Items',
        items=items,
        delete_form=delete_form # <<< Pass instance to template
    )

@bp.route('/item/new', methods=['GET', 'POST'])
@admin_required
def create_item():
    form = ItemForm()
    if form.validate_on_submit():
        if not form.barcode_id.data:
            last_item = Item.query.filter(Item.barcode_id.like('I%')).order_by(Item.id.desc()).first()
            if last_item:
                try:
                    last_number = int(last_item.barcode_id.lstrip('I'))
                    new_number = last_number + 1
                except ValueError:
                    new_number = 5001  # Fallback value
            else:
                new_number = 5001  # Starting value for items
            generated_barcode = f'I{new_number}'
        else:
            generated_barcode = form.barcode_id.data

        item = Item(name=form.name.data, barcode_id=generated_barcode, is_unique=form.is_unique.data)
        db.session.add(item)
        db.session.commit()
        flash('Item created successfully!', 'success')
        return redirect(url_for('admin.list_items'))
    return render_template('admin/item_form.html', title='New Item', form=form, legend='New Item')

@bp.route('/item/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        abort(404)
    form = ItemForm() # Create instance before checking request method

    if form.validate_on_submit():
        item.name = form.name.data
        item.barcode_id = form.barcode_id.data
        item.is_unique = form.is_unique.data
        db.session.commit()
        flash('Item updated successfully!', 'success')
        return redirect(url_for('admin.list_items'))
    elif request.method == 'GET':
        form.name.data = item.name
        form.barcode_id.data = item.barcode_id
        form.is_unique.data = item.is_unique
        form.original_barcode_id.data = item.barcode_id # Populate hidden field

    # Pass the original item barcode ID to the template even on POST validation error
    if not form.original_barcode_id.data:
         form.original_barcode_id.data = item.barcode_id

    return render_template('admin/item_form.html', title='Edit Item', form=form, legend='Edit Item')


@bp.route('/item/delete/<int:item_id>', methods=['POST'])
@admin_required
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        abort(404)

    # Check if item has purchases - prevent deletion if they do (based on model relationship)
    if item.purchases.first():
         flash('Cannot delete item because it has associated purchases. Consider marking as inactive instead (feature not implemented).', 'danger')
         return redirect(url_for('admin.list_items'))

    form = DeleteForm()
    if form.validate_on_submit():
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
    else:
         flash('Error deleting item. Please try again.', 'danger')

    return redirect(url_for('admin.list_items'))

# --- Barcode Card Generation Page ---
@bp.route('/print_cards', methods=['GET', 'POST'])
@admin_required
def print_cards():
    buyers = Buyer.query.order_by(Buyer.name).all()
    items = Item.query.order_by(Item.name).all()
    default_prices = [10, 20, 30, 40, 50]
    custom_prices = []
    copies = 1

    if request.method == 'POST':
        custom_prices_str = request.form.get('custom_prices', '')
        copies_str = request.form.get('copies', '1')
        try: copies = max(1, int(copies_str)) # Ensure at least 1 copy
        except ValueError: copies = 1

        if custom_prices_str:
            try:
                custom_prices = [float(x.strip()) for x in custom_prices_str.split(',') if x.strip()]
            except Exception:
                flash('Error processing custom prices. Using default.', 'warning')
                custom_prices = default_prices
        else:
            custom_prices = default_prices
    else:
        custom_prices = default_prices

    cards_data = [] # Store dicts with all needed info

    # Generate buyer cards data
    for buyer in buyers:
        barcode_data = f"BUYER:{buyer.barcode_id}"
        cards_data.append({
            'label': buyer.name,
            'barcode_uri': generate_barcode_uri(barcode_data),
            'raw_barcode': barcode_data # *** Add raw data for JS ***
        })

    # Generate item cards data
    for item in items:
        barcode_data = f"ITEM:{item.barcode_id}"
        cards_data.append({
            'label': item.name,
            'barcode_uri': generate_barcode_uri(barcode_data),
            'raw_barcode': barcode_data # *** Add raw data for JS ***
         })

    # Generate price cards data
    for price in custom_prices:
        for _ in range(copies):
            barcode_data = f"PRICE:{price:.2f}"
            price_label = f"₪{price:.2f}"
            cards_data.append({
                'label': price_label,
                'barcode_uri': generate_barcode_uri(barcode_data),
                'raw_barcode': barcode_data # *** Add raw data for JS ***
            })

    # Filter out any cards where barcode generation failed (unlikely with SVG but good practice)
    valid_cards_data = [card for card in cards_data if card['barcode_uri']]

    return render_template('admin/print_cards.html',
                           title='Print Barcode Cards',
                           cards=valid_cards_data, # Pass the list of dictionaries
                           default_prices=",".join([str(p) for p in default_prices]),
                           copies=copies)


# --- NEW ROUTE: Download Selected Barcodes as Excel ---
@bp.route('/download_excel', methods=['POST'])
@admin_required
def download_excel():
    """Receives selected barcode data and generates an Excel file."""
    try:
        selected_data = request.get_json()
        if not selected_data or not isinstance(selected_data, list):
            flash('No data received or invalid format for download.', 'warning')
            # Return a JSON error response perhaps?
            return jsonify({"error": "Invalid data received"}), 400

        # Create DataFrame using pandas
        df = pd.DataFrame(selected_data)
        if df.empty:
             flash('No items were selected for download.', 'warning')
             # Or handle differently
             return jsonify({"error": "No items selected"}), 400

        # Ensure columns exist and rename if necessary (df columns match keys in JS object)
        df = df.rename(columns={'label': 'Label', 'raw_barcode': 'Barcode Data'})

        # Create an in-memory Excel file
        output = io.BytesIO()
        # Use openpyxl engine explicitly
        writer = pd.ExcelWriter(output, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='Selected Barcodes')
        # Don't close the writer with 'with' statement if using BytesIO directly like this
        # writer.save() # save is deprecated, use close
        writer.close() # Correct way to finalize the Excel data in buffer
        output.seek(0)

        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=selected_barcodes.xlsx'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        return response

    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error generating Excel file: {e}", exc_info=True)
        flash('An error occurred while generating the Excel file.', 'danger')
        # Redirect back or return an error response
        # Redirecting might lose the context, returning JSON error might be better for AJAX call
        return jsonify({"error": "Server error generating file"}), 500
    

# --- NEW: Buyer Card Route ---
@bp.route('/buyer/<int:buyer_id>/card')
@admin_required
def buyer_card(buyer_id):
    """Displays a detailed card view for a specific buyer."""
    buyer = db.session.get(Buyer, buyer_id)
    if not buyer:
        flash(f"Buyer with ID {buyer_id} not found.", "warning")
        return redirect(url_for('admin.list_buyers'))

    # Query all purchases for this buyer, loading related data efficiently
    purchases = Purchase.query.options(
        joinedload(Purchase.item), # Load the Item object with the Purchase
        joinedload(Purchase.event) # Load the Event object with the Purchase
    ).filter(Purchase.buyer_id == buyer_id)\
     .order_by(Purchase.timestamp.desc())\
        .all()

    # Calculate total spent by this buyer (optional but useful)
    total_spent = db.session.query(db.func.sum(Purchase.total_price))\
                            .filter(Purchase.buyer_id == buyer_id)\
                            .scalar() or 0.0

    return render_template(
        'admin/buyer_card.html',
        title=f"Buyer Card: {buyer.name}",
        buyer=buyer,
        purchases=purchases,
        total_spent=total_spent
    )


# --- NEW: Item Purchase History Route ---
@bp.route('/item/<int:item_id>/history')
@admin_required
def item_history(item_id):
    """Displays recent purchase history for a specific item."""
    item = db.session.get(Item, item_id)
    if not item:
        flash(f"Item with ID {item_id} not found.", "warning")
        return redirect(url_for('admin.list_items'))

    # Query recent purchases for this item
    # Add a limit to avoid excessively long pages for popular items
    limit = 50 # Show the last 50 purchases, adjust as needed
    purchases = Purchase.query.options(
        joinedload(Purchase.buyer), # Load the Buyer object
        joinedload(Purchase.event)  # Load the Event object
    ).filter(Purchase.item_id == item_id)\
     .order_by(Purchase.timestamp.desc())\
     .limit(limit)\
     .all()

    # Calculate total revenue from this item (optional)
    total_revenue = db.session.query(db.func.sum(Purchase.total_price))\
                              .filter(Purchase.item_id == item_id)\
                              .scalar() or 0.0
    purchase_count = Purchase.query.filter(Purchase.item_id == item_id).count()


    return render_template(
        'admin/item_history.html',
        title=f"Item History: {item.name}",
        item=item,
        purchases=purchases,
        total_revenue=total_revenue,
        purchase_count=purchase_count,
        limit=limit
    )
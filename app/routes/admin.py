# file: app/routes/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Buyer, Item
from app.forms import BuyerForm, ItemForm, DeleteForm # Import DeleteForm
from app.utils.barcode_utils import generate_barcode_uri
from app.forms import BuyerForm, ItemForm, DeleteForm # Ensure DeleteForm is imported

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


# --- Item CRUD ---
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

# --- Barcode Card Generation Page ---
@bp.route('/print_cards', methods=['GET', 'POST'])
@admin_required
def print_cards():
    # Retrieve buyers and items as before
    buyers = Buyer.query.order_by(Buyer.name).all()
    items = Item.query.order_by(Item.name).all()

    # Define a default list of prices (optional)
    default_prices = [10, 20, 30, 40, 50]  # Example default prices

    # Initialize variables
    custom_prices = []
    copies = 1  # default to 1 copy if no custom input is provided

    # If the request is a POST, try to read custom values
    if request.method == 'POST':
        # Expect a comma-separated list of amounts
        custom_prices_str = request.form.get('custom_prices', '')
        copies_str = request.form.get('copies', '1')
        try:
            copies = int(copies_str)
        except ValueError:
            copies = 1
        if custom_prices_str:
            try:
                # Parse the input string into a list of floats
                custom_prices = [float(x.strip()) for x in custom_prices_str.split(',') if x.strip()]
            except Exception as e:
                flash('There was an error processing your custom prices. Using default prices.', 'warning')
                custom_prices = default_prices
        else:
            custom_prices = default_prices
    else:
        # For GET requests, you could either use the default list or leave it empty.
        custom_prices = default_prices

    cards = []

    # Generate buyer cards (unchanged)
    for buyer in buyers:
        barcode_data = f"BUYER:{buyer.barcode_id}"
        cards.append({'label': buyer.name, 'barcode_uri': generate_barcode_uri(barcode_data)})

    # Generate item cards (unchanged)
    for item in items:
        barcode_data = f"ITEM:{item.barcode_id}"
        cards.append({'label': item.name, 'barcode_uri': generate_barcode_uri(barcode_data)})

    # Generate price cards using custom or default prices.
    price_cards = []
    for price in custom_prices:
        for _ in range(copies):
            barcode_data = f"PRICE:{price:.2f}"
            # Use the Israeli Shekel sign; you can also add extra formatting if needed.
            price_label = f"₪{price:.2f}"
            price_cards.append({'label': price_label, 'barcode_uri': generate_barcode_uri(barcode_data)})

    cards.extend(price_cards)
    valid_cards = [card for card in cards if card['barcode_uri']]

    return render_template('admin/print_cards.html',
                           title='Print Barcode Cards',
                           cards=valid_cards,
                           default_prices=",".join([str(p) for p in default_prices]),
                           copies=copies)

# --- Buyer Edit/Delete ---
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


# --- Item Edit/Delete ---
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
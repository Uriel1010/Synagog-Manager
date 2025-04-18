# file: app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Event
from app.forms import EventForm, DeleteForm
from app.utils.hebrew_date_utils import get_hebrew_date_string
from datetime import datetime
# --- Import the decorator (needed if used anywhere in this file) ---
from app.decorators import admin_required

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    # Dashboard showing upcoming or recent events, maybe summary stats
    events = Event.query.order_by(Event.gregorian_date.desc()).limit(5).all()
    return render_template('main/index.html', title='Dashboard', events=events)

@bp.route('/events')
@login_required
def list_events():
    page = request.args.get('page', 1, type=int)
    events = Event.query.order_by(Event.gregorian_date.desc()).paginate(page=page, per_page=10)
    delete_form = DeleteForm()
    return render_template(
        'main/events_list.html',
        title='Events',
        events=events,
        delete_form=delete_form
    )


@bp.route('/event/new', methods=['GET', 'POST'])
@login_required
def create_event():
    form = EventForm()
    if form.validate_on_submit():
        greg_date = form.gregorian_date.data or datetime.utcnow().date()
        # Ensure greg_date is a date object before creating datetime
        if isinstance(greg_date, datetime):
             greg_date = greg_date.date()
        heb_date_dt = datetime(greg_date.year, greg_date.month, greg_date.day)
        heb_date_str = get_hebrew_date_string(heb_date_dt) # Pass datetime object
        event = Event(
            event_name=form.event_name.data,
            gregorian_date=datetime(greg_date.year, greg_date.month, greg_date.day),
            hebrew_date=heb_date_str,
            details=form.details.data
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created successfully!', 'success')
        return redirect(url_for('main.list_events'))
    return render_template('main/event_form.html', title='New Event', form=form, legend='New Event')

@bp.route('/event/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)

    form = EventForm()
    if form.validate_on_submit():
        greg_date = form.gregorian_date.data or event.gregorian_date.date()
        if isinstance(greg_date, datetime):
             greg_date = greg_date.date()
        heb_date_dt = datetime(greg_date.year, greg_date.month, greg_date.day)
        heb_date_str = get_hebrew_date_string(heb_date_dt) # Pass datetime object

        event.event_name = form.event_name.data
        event.gregorian_date = datetime(greg_date.year, greg_date.month, greg_date.day)
        event.hebrew_date = heb_date_str
        event.details = form.details.data
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('main.list_events'))
    elif request.method == 'GET':
        form.event_name.data = event.event_name
        form.gregorian_date.data = event.gregorian_date.date()
        form.details.data = event.details

    return render_template('main/event_form.html', title='Edit Event', form=form, legend='Edit Event')

@bp.route('/event/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)

    form = DeleteForm()
    if form.validate_on_submit():
        db.session.delete(event)
        db.session.commit()
        flash('Event and associated purchases deleted successfully!', 'success')
    else:
        flash('Error deleting event. Please try again.', 'danger')

    return redirect(url_for('main.list_events'))

@bp.route('/help')
@login_required # Requires login to see help page
def help_page():
    """Renders the help and documentation page."""
    return render_template('help/index.html', title="Help & Documentation")
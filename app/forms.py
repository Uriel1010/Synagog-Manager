# file: app/forms.py
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    SelectField, FloatField, IntegerField, TextAreaField,
    DateField, HiddenField
)
from wtforms.validators import (
    DataRequired, Length, EqualTo, ValidationError,
    Optional, NumberRange
)
from flask import request
from app.models import User, Buyer, Item, Event


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    username = StringField(
        'Username',
        validators=[DataRequired(), Length(min=3, max=64)]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired(), Length(min=6)]
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password')]
    )
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError(
                'Username already taken. Please choose a different one.'
            )


class EventForm(FlaskForm):
    event_name = StringField(
        'Event Name',
        validators=[DataRequired(), Length(max=120)]
    )
    gregorian_date = DateField(
        'Date (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    details = StringField(
        'Details (e.g., Parsha, Holiday)',
        validators=[Length(max=200)]
    )
    submit = SubmitField('Save Event')


class BuyerForm(FlaskForm):
    name = StringField(
        'Buyer Name',
        validators=[DataRequired(), Length(max=120)]
    )
    barcode_id = StringField(
        'Barcode ID (Optional)',
        validators=[Optional(), Length(min=1, max=50)],
        description=(
            "Leave blank to auto-generate (e.g., B1001). "
            "Enter manually to match an existing card."
        )
    )
    original_barcode_id = HiddenField()
    submit = SubmitField('Save Buyer')

    def validate_barcode_id(self, barcode_id):
        if not barcode_id.data:
            return
        if (
            request.form.get('original_barcode_id') and
            barcode_id.data == request.form.get('original_barcode_id')
        ):
            return
        existing = Buyer.query.filter_by(barcode_id=barcode_id.data).first()
        if existing:
            raise ValidationError(
                'Barcode ID already exists for another buyer.'
            )


class ItemForm(FlaskForm):
    name = StringField(
        'Item Name',
        validators=[DataRequired(), Length(max=120)]
    )
    barcode_id = StringField(
        'Barcode ID (Optional)',
        validators=[Optional(), Length(min=1, max=50)],
        description=(
            "Leave blank to auto-generate (e.g., I5001). "
            "Enter manually to match an existing card."
        )
    )
    is_unique = BooleanField('Is Unique Item (e.g., Specific Aliyah)?')
    original_barcode_id = HiddenField()
    submit = SubmitField('Save Item')

    def validate_barcode_id(self, barcode_id):
        if not barcode_id.data:
            return
        if (
            request.form.get('original_barcode_id') and
            barcode_id.data == request.form.get('original_barcode_id')
        ):
            return
        existing = Item.query.filter_by(barcode_id=barcode_id.data).first()
        if existing:
            raise ValidationError(
                'Barcode ID already exists for another item.'
            )


class ManualPurchaseForm(FlaskForm):
    buyer_id = SelectField(
        'Buyer',
        coerce=int,
        validators=[DataRequired()]
    )
    item_id = SelectField(
        'Item',
        coerce=int,
        validators=[DataRequired()]
    )
    total_price = FloatField(
        'Total Price (₪)',
        validators=[Optional(), NumberRange(min=0)],
        default=0.0
    )
    quantity = IntegerField(
        'Quantity',
        default=1,
        validators=[DataRequired(), NumberRange(min=1)]
    )
    is_manual_entry = BooleanField(
        'Is Manual / Donation?',
        default=True
    )
    manual_entry_notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=300)]
    )
    submit = SubmitField('Add Manual Purchase')

    def __init__(self, *args, **kwargs):
        super(ManualPurchaseForm, self).__init__(*args, **kwargs)
        # Populate choices dynamically
        self.buyer_id.choices = [
            (b.id, b.name)
            for b in Buyer.query.order_by(Buyer.name).all()
        ]
        self.item_id.choices = [
            (i.id, i.name)
            for i in Item.query.order_by(Item.name).all()
        ]


class ReportSelectionForm(FlaskForm):
    event_id = SelectField(
        'Select Event',
        coerce=int,
        validators=[DataRequired()]
    )
    submit = SubmitField('Generate Report')

    def __init__(self, *args, **kwargs):
        super(ReportSelectionForm, self).__init__(*args, **kwargs)
        self.event_id.choices = [
            (e.id, f"{e.event_name} ({e.gregorian_date.strftime('%Y-%m-%d')})")
            for e in Event.query.order_by(Event.gregorian_date.desc()).all()
        ]


class DeleteForm(FlaskForm):
    submit = SubmitField(
        'Delete',
        render_kw={'class': 'btn btn-sm btn-danger'}
    )

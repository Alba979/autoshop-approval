from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, TextAreaField, SelectField, DecimalField,
    IntegerField,
)
from wtforms.validators import DataRequired, Optional, Email, NumberRange, Length


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class NewJobForm(FlaskForm):
    customer_id = SelectField("Customer", coerce=int, validators=[DataRequired()])
    vehicle_id = SelectField("Vehicle", coerce=int, validators=[DataRequired()])
    technician_id = SelectField("Technician", coerce=int, validators=[Optional()])
    customer_concern = TextAreaField("Customer's stated concern", validators=[Optional()])


class DiagnosticFindingForm(FlaskForm):
    system_area = StringField("System / area", validators=[DataRequired(), Length(max=80)])
    description = TextAreaField("Finding", validators=[DataRequired()])
    severity = SelectField(
        "Severity",
        choices=[("urgent", "Urgent"), ("recommended", "Recommended"), ("monitor", "Monitor")],
        default="recommended",
    )
    photo = FileField(
        "Photo (optional)",
        validators=[FileAllowed(["png", "jpg", "jpeg", "heic", "webp"], "Images only")],
    )


class EstimateLineItemForm(FlaskForm):
    kind = SelectField("Type", choices=[("part", "Part"), ("labor", "Labor")])
    description = StringField("Description", validators=[DataRequired()])
    quantity = DecimalField("Qty", places=2, default=1, validators=[NumberRange(min=0)])
    unit_price = DecimalField("Unit price", places=2, validators=[NumberRange(min=0)])


class SendEstimateForm(FlaskForm):
    channel = SelectField("Send via", choices=[("sms", "Text message"), ("email", "Email")])


class CustomerResponseForm(FlaskForm):
    """CSRF-protected wrapper for the approve/decline buttons.

    Deliberately carries no 'decision' field of its own - the decision comes
    from whichever submit button the customer tapped (name="decision",
    value="approved"/"declined"), read directly from request.form in the
    route. This avoids any ambiguity between a same-named hidden field and
    button value that could otherwise arise depending on form-encoding
    order, and works correctly with JavaScript disabled.
    """
    pass


class NewCustomerForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired()])
    last_name = StringField("Last name", validators=[DataRequired()])
    phone_number = StringField("Mobile number", validators=[DataRequired()])
    email = StringField("Email", validators=[Optional(), Email()])
    spending_cap = DecimalField("Spending cap ($)", places=2, validators=[NumberRange(min=0)])


class NewVehicleForm(FlaskForm):
    year = IntegerField("Year", validators=[DataRequired(), NumberRange(min=1950, max=2100)])
    make = StringField("Make", validators=[DataRequired()])
    model = StringField("Model", validators=[DataRequired()])
    vin = StringField("VIN", validators=[Optional(), Length(max=17)])
    license_plate = StringField("License plate", validators=[Optional()])
    mileage = IntegerField("Mileage", validators=[Optional(), NumberRange(min=0)])


class CompleteJobForm(FlaskForm):
    final_cost = DecimalField("Final invoice total ($)", places=2, validators=[DataRequired(), NumberRange(min=0)])

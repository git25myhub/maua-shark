from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp, Optional

class PassengerDetailsForm(FlaskForm):
    name = StringField('Full Name', validators=[
        DataRequired(message='Full name is required'),
        Length(min=3, max=100, message='Name must be between 3 and 100 characters')
    ])
    
    id_number = StringField('National ID Number', validators=[
        DataRequired(message='National ID is required'),
        Length(min=5, max=30, message='ID number must be between 5 and 30 characters'),
        Regexp(r'^[0-9A-Za-z-]+$', message='ID can contain letters, numbers and dashes')
    ])
    
    sex = SelectField('Sex', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], validators=[DataRequired(message='Please select a gender')])
    
    age = IntegerField('Age', validators=[
        DataRequired(message='Age is required'),
        NumberRange(min=1, max=120, message='Age must be between 1 and 120')
    ])
    
    phone = StringField('Phone Number', validators=[
        DataRequired(message='Phone number is required'),
        Length(min=10, max=15, message='Phone number must be between 10 and 15 digits'),
        Regexp(r'^[0-9+]+$', message='Phone number can only contain numbers and +')
    ])

    pickup_location = StringField('Pickup Location (optional)', validators=[
        Optional(),
        Length(max=255, message='Pickup location must be at most 255 characters')
    ])
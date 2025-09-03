from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp

class PassengerDetailsForm(FlaskForm):
    name = StringField('Full Name', validators=[
        DataRequired(message='Full name is required'),
        Length(min=3, max=100, message='Name must be between 3 and 100 characters')
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
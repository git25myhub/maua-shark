from flask import Blueprint

bp = Blueprint('main', __name__)

from maua.main import routes, health
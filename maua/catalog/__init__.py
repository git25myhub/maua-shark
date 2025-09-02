from flask import Blueprint

bp = Blueprint('catalog', __name__)

from maua.catalog import routes
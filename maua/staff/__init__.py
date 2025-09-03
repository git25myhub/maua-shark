from flask import Blueprint

staff_bp = Blueprint('staff', __name__)

from . import routes  # noqa: E402,F401



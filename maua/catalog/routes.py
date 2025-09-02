from flask import render_template
from maua.catalog import bp

@bp.route('/routes')
def routes():
    return render_template('catalog/routes.html', title='Routes')
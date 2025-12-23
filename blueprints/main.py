"""Main blueprint for top-level pages."""

from flask import Blueprint, render_template
from utils.decorators import login_required, admin_required

main = Blueprint('main', __name__)


@main.route('/')
@login_required
def index():
    """Main song list page"""
    return render_template('index.html')


@main.route('/admin')
@admin_required
def admin():
    """Admin page for managing skills"""
    return render_template('admin.html')

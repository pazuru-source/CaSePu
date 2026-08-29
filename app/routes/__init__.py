"""Routes package for CaSePu."""
from flask import Blueprint

api_bp = Blueprint('api', __name__)

from app.routes import api  # noqa: F401, E402

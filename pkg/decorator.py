# app/utils/decorators.py

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
from ..model.model import User, Role



def role_required(required_role):
    """
    Generic role decorator factory.
    Usage: @role_required(Role.EDITOR)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not Role.has_permission(current_user.role, required_role):
                abort(403)   # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Convenience shortcuts — makes routes clean and readable
def admin_required(f):
    return role_required(Role.ADMIN)(f)

def editor_required(f):
    return role_required(Role.EDITOR)(f)

def contributor_required(f):
    return role_required(Role.CONTRIBUTOR)(f)
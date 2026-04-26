from flask import Flask, session
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from pkg.config import TestConfig,LiveConfig
from pkg.blogmodel import Reader, db
from pkg.limiter import limiter
from pkg.route_constants import READER_SESSION_KEY

csrf= CSRFProtect()
def create_app():
    from pkg.blogmodel import db
    # from pkg.admin import adminobj
    # from pkg.user import userobj
    # from pkg.api import apiobj
    app=Flask(__name__, instance_relative_config=True)
    # app.register_blueprint(adminobj)
    # app.register_blueprint(userobj)
    # app.register_blueprint(apiobj)

    
    app.config.from_object(LiveConfig)
    app.config.from_pyfile('config.py', silent=True)

    db.init_app(app)
    migrate = Migrate(app,db)
    csrf.init_app(app)
    limiter.init_app(app)
    # csrf.exempt(apiobj)
    return app

app = create_app()

from pkg import user_routes
from pkg.blogmodel import Category


@app.context_processor
def inject_nav_categories():
    current_reader = None

    try:
        categories = Category.query.order_by(Category.name.asc()).all()
    except Exception:
        categories = []

    reader_id = session.get(READER_SESSION_KEY)
    if reader_id:
        try:
            current_reader = Reader.query.get(reader_id)
        except Exception:
            current_reader = None

    return {
        "nav_categories": categories,
        "current_reader": current_reader,
        "is_reader_logged_in": current_reader is not None,
    }
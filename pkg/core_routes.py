from sqlalchemy.exc import OperationalError
from flask_wtf.csrf import CSRFError
from flask import render_template
from pkg import app


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template(
        "error.html",
        code=400,
        title="Security Error",
        message="Your session has expired. Please refresh the page and try again.",
    ), 400

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    return response


@app.errorhandler(404)
def page_not_found(e):
    return render_template(
        "error.html",
        code=404,
        title="Page Not Found",
        message="The page you're looking for doesn't exist or may have been moved.",
    ), 404


@app.route("/newsletters")
def newsletters():
    # Temporarily return 404 until newsletters are implemented
    return render_template(
        "error.html",
        code=404,
        title="Coming Soon",
        message="Newsletters feature is coming soon! Stay tuned for updates.",
    ), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template(
        "error.html",
        code=500,
        title="Something Went Wrong",
        message="An unexpected error occurred on our end. Please try again in a moment.",
    ), 500


@app.errorhandler(OperationalError)
def database_error(e):
    return render_template(
        "error.html",
        code=503,
        title="Database Unavailable",
        message="We couldn't connect to the database. Please try again shortly.",
    ), 503

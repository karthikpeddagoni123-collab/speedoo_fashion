"""Speedoo Fashion — Flask application entrypoint.

A SINGLE-OWNER men's fashion e-commerce store. Customers can browse and
buy; only the authorized owner can manage the product collection. The
backend enforces this through decorators and DB-level constraints.
"""
from __future__ import annotations

import os

from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from config import FLASK_SECRET, MAX_UPLOAD_BYTES, UPLOAD_DIR
from customer_routes import customer_bp
from db import init_db
from owner_routes import owner_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = FLASK_SECRET
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["UPLOAD_DIR"] = UPLOAD_DIR

    # Bootstrap the single-owner schema on first run.
    init_db()

    app.register_blueprint(customer_bp)
    app.register_blueprint(owner_bp)

    # ---------- Error handlers ----------
    @app.errorhandler(403)
    def _403(e):
        return render_template("403.html", message=str(e.description)), 403

    @app.errorhandler(404)
    def _404(e):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def _413(e):
        return render_template("error.html",
                               title="File too large",
                               message=(
                                   "The uploaded file exceeds the maximum "
                                   "allowed size."
                               ),
                               back="/"), 413

    @app.errorhandler(Exception)
    def _generic(e):

        if isinstance(e, HTTPException):
            return e

        print("\n========================================")
        print("        SPEEDOO FASHION ERROR")
        print("========================================")
        print("Error:", e)

        import traceback
        traceback.print_exc()

        print("========================================\n")

        return render_template(
            "error.html",
            title="Something went wrong",
            message="Please try again later.",
            back="/"
        ), 500

    return app


# Build the module-level app so `flask run --app app.py` and
# `python app.py` both work.
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)

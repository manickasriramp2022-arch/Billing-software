import os

from flask import Flask


def create_app(test_config=None):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
        DATABASE=os.environ.get("BILLING_DB", os.path.join(app.instance_path, "billing.sqlite")),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    from . import db, utils
    db.init_app(app)

    app.jinja_env.filters["money"] = utils.money
    app.jinja_env.filters["inr"] = utils.inr
    app.jinja_env.filters["qty"] = utils.qty
    app.jinja_env.filters["docdate"] = utils.format_date
    app.jinja_env.globals["amount_in_words"] = utils.amount_in_words

    from .views import buyers, dashboard, invoices, products, reports, settings
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(buyers.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(invoices.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(settings.bp)

    return app

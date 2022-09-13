from os import getenv
from flask import Flask
from werkzeug.wrappers import Request, Response
from routes.item import item_route
from routes.user import user_route
from routes.admin import admin
from routes.checkout import checkout_route
from routes.image import image_route
from key_routine import key_routine

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = "a_ACZr49{m4YL@=Y"

    app.register_blueprint(item_route)
    app.register_blueprint(user_route)
    app.register_blueprint(checkout_route)
    app.register_blueprint(image_route)

    admin.init_app(app)

    key_routine()

    return app
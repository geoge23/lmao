from flask import request, jsonify
from peewee import DoesNotExist
from models import ApiKey

def auth_middleware():
    auth_header = request.headers.get('Authorization', "").replace("Bearer ", "")

    try:
        ApiKey.select().where(ApiKey.code == auth_header).dicts().get()
    except DoesNotExist:
        return jsonify({"error": "Client is unauthorized"}), 401
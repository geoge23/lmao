from flask import Blueprint, request, jsonify
from models import Item
from peewee import IntegrityError
from json import dumps
from datetime import datetime
from middleware import auth_middleware

item_route = Blueprint("item-route", __name__)
item_route.before_request(auth_middleware)

@item_route.get('/item')
def get_item():
    if (len(request.args.to_dict()) > 0):
        items = Item.select().where(
            Item.barcode == request.args.get('barcode') or
            Item.name == request.args.get('name')
        ).dicts()
    else:
        items = Item.select().dicts()

    return jsonify(list(items))

@item_route.post('/item')
def put_item():
    try:
        body = request.json
        new_item = Item(barcode=body["barcode"], name=body["name"])
        if "area" in body:
            new_item.area = body['area']
        if "image_id" in body:
            new_item.image = body['image_id']
        if "description" in body:
            new_item.description = body['description']
        if "last-calibration" in body and body["last-calibration"] != "":
            new_item.last_calibration = datetime.strptime(body['last-calibration'], "%Y-%m-%d")
        new_item.save(force_insert=True)
        return {'id': new_item.id}
    except AttributeError as e:
        return {"error": "Missing information to create this object"}, 400
    except IntegrityError as e:
        return {"error": "This barcode already exists in the system"}, 400
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500
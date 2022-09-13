from flask import Blueprint, request, jsonify
from peewee import DoesNotExist, IntegrityError, JOIN
from models import User, Checkout, Item
from middleware import auth_middleware

user_route = Blueprint("user-route", __name__)
user_route.before_request(auth_middleware)

@user_route.get('/ping')
def ping():
    return "Pong"

@user_route.get('/user')
def get_user():
    try:
        return User.select().where(User.gtid == request.args['gtid']).dicts().get()
    except KeyError:
        return {"error": "Missing GT id"}, 400
    except DoesNotExist:
        return {"error": "User does not exist"}, 404
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500

@user_route.post('/user')
def put_user():
    try:
        body = request.get_json()
        new_user = User(gtid=body["gtid"], name=body["name"])
        if "email" in body:
            new_user.email = body['email']
        new_user.save(force_insert=True)
        return {"id": new_user.id}
    except KeyError:
        return {"error": "Missing required information to create this user"}, 400
    except IntegrityError as e:
        return {"error": "This user already exists in the system"}, 400
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500

@user_route.get('/user/items')
def get_user_items():
    try:
        user = User.select().where(User.gtid == request.args['gtid']).get()
        open_checkouts = Checkout.select(Checkout.start_date, Item.name, Item.barcode, Item.area, Item.image).where((Checkout.user_id == user) & (Checkout.return_date.is_null())).join(Item).dicts()
        return jsonify(list(open_checkouts))
    except KeyError:
        return {"error": "Missing GT id"}, 400
    except DoesNotExist:
        return {"error": "User or checkout does not exist"}, 404
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500
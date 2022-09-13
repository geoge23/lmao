from flask import Blueprint, request, jsonify
from models import Checkout, User, Item
from datetime import datetime, date
from peewee import IntegrityError, DoesNotExist
from middleware import auth_middleware

checkout_route = Blueprint("checkout-route", __name__)
checkout_route.before_request(auth_middleware)

@checkout_route.post('/checkout')
def create_checkout():
    try:
        body = request.get_json()
        user = User.get(User.gtid == body['gtid'])
        item = Item.get(Item.barcode == body['barcode'])
        
        try:
            past_checkout = Checkout.get(
                (Checkout.item_id == item) & (Checkout.return_date.is_null())
            )
            if past_checkout is not None:
                owning_user = User.get_by_id(past_checkout.user_id)
                return {"error": "This item is already checked out by {}".format(owning_user.name)}, 403
        except DoesNotExist:
            new_checkout = Checkout(item_id=item, user_id=user)
            new_checkout.save(force_insert=True)

            time_since_cal = (date.today() - item.last_calibration).days if item.last_calibration is not None else 0
            
            if time_since_cal > 330:
                return {"id": new_checkout.id, "message": "⚠ Not calibrated in {} days!".format(time_since_cal)}
            else:
                return {"id": new_checkout.id}
    except KeyError:
        return {"error": "Missing required information to check out this item"}, 400
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500

@checkout_route.delete('/checkout')
def delete_checkout():
    try:
        body = request.get_json()
        item = Item.get(Item.barcode == body['barcode'])
        ended_checkout = Checkout.get((Checkout.item_id == item) & (Checkout.return_date.is_null()))
        ended_checkout.return_date = datetime.now()
        ended_checkout.save()

        if not ended_checkout.user_id.gtid == str(body['gtid']):
            return {"id": ended_checkout.id, "message": "This item is returned for {}".format(ended_checkout.user_id.name)}
        else:
            return {"id": ended_checkout.id}
    except KeyError:
        return {"error": "Missing required information to check out this item"}, 400
    except DoesNotExist:
        return {"error": "This item is already checked back in"}, 400
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500


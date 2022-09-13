from flask import Blueprint, request, jsonify, send_file
from models import Image
from peewee import IntegrityError
from json import dumps
from PIL import Image as PILImage
import io
from middleware import auth_middleware

image_route = Blueprint("image-route", __name__)

@image_route.get('/image/<id>')
def get_item(id):
    try:
        img = Image.get(Image.id == id)
        return send_file(io.BytesIO(img.image), mimetype='image/jpeg')
    except Image.DoesNotExist:
        return jsonify({"error": "Image does not exist"}), 404
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500

    return jsonify(list(items))

@image_route.post('/image')
def put_image():
    #applies middleware to only this route in the file
    auth = auth_middleware()
    if auth is not None:
        return auth

    try:
        f = request.files['file']
        
        img = PILImage.open(f)
        #scales image down to have a height of 400 px but a preserved aspect ratio
        ratio = img.width / img.height
        cropped_img = img.resize((int(400*ratio), 400))

        #converts image to 400x400 and centers it
        mid_x = int(cropped_img.width/2)
        mid_y = int(cropped_img.height/2)
        cropped_img = cropped_img.crop((mid_x-200, mid_y-200, mid_x+200, mid_y+200))
        
        img_byte_arr = io.BytesIO()
        cropped_img.save(img_byte_arr, format='JPEG')

        new_image = Image(image=img_byte_arr.getvalue())
        new_image.save(force_insert=True)
        return {'id': new_image.id}
    except AttributeError as e:
        return {"error": "Missing information to create this object"}, 400
    except IntegrityError as e:
        return {"error": "This image already exists in the system"}, 400
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}, 500
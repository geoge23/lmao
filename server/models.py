from os import getenv
from datetime import datetime
import uuid
from peewee import PostgresqlDatabase, Model, TextField, ForeignKeyField, DateTimeField, IntegerField, BlobField

def gen_uuid():
    return str(uuid.uuid4())

db = PostgresqlDatabase(
    'inventory', 
    user=getenv('POSTGRES_USER'), 
    password=getenv('POSTGRES_PASSWORD'), 
    host=getenv('POSTGRES_HOST'),
    port=getenv('POSTGRES_PORT') or 5432
)

db.connect()

class Image(Model):
    id = TextField(primary_key=True, default=gen_uuid)
    image = BlobField()

    class Meta:
        database = db
        table_name = "images"

class Item(Model):
    id = TextField(primary_key=True, default=gen_uuid)
    barcode = TextField(unique=True)
    name = TextField()
    area = IntegerField(null=True)
    image = ForeignKeyField(Image, null=True)
    description = TextField(null=True)
    last_calibration = DateTimeField(null=True)

    class Meta:
        database = db
        table_name = "items"

class User(Model):
    id = TextField(primary_key=True, default=gen_uuid)
    gtid = TextField(unique=True)
    name = TextField()
    email = TextField(unique=True, null=True)

    class Meta:
        database = db
        table_name = "users"

class Checkout(Model):
    id = TextField(primary_key=True, default=gen_uuid)
    start_date = DateTimeField(default=datetime.now())
    #Returned date being null indicates that the item has not been returned
    return_date = DateTimeField(null=True)
    item_id = ForeignKeyField(Item)
    user_id = ForeignKeyField(User)

    class Meta:
        database = db
        table_name = "checkouts"

class ApiKey(Model):
    code = TextField(default=gen_uuid)

    class Meta:
        database = db
        table_name = "api_keys"



db.create_tables([Item, User, Checkout, ApiKey, Image])
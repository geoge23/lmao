from models import ApiKey
import os

def key_routine():
    if not os.path.exists("key"):
        if ApiKey.select().count() == 0:
            with open('key', 'w') as f:
                key = ApiKey()
                key.save()
                f.write(key.code)

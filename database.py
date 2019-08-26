import pymongo
import os

channels = None
users = None

URI = os.environ.get('MONGODB_URI')
PROD = int(os.environ.get('PROD'))

def name_to_id(name):
    query = {"name": name}
    result = users.find_one(query)
    if result:
        return result.get("id")
    return None

def id_to_name(user_id):
    query = {"id": user_id}
    result = users.find_one(query)
    if result:
        return result.get("name")
    return None

def add_user(user):
    users.insert_one(user)

def add_channel(channel):
    channels.insert_one(channel)

def id_to_channel(channel_id):
    query = {"id": channel_id}
    result = channels.find_one(query)
    if result:
        return result.get("name")
    return None

def channel_to_id(channel_name):
    query = {"name": channel_name}
    result = channels.find_one(query)
    if result:
        return result.get("id")
    return None

def load_database():
    global channels, users

    if PROD:
        client = pymongo.MongoClient(URI, retryWrites=False)
    else:
        client = pymongo.MongoClient("mongodb://localhost:27017/testing", retryWrites=False)
    db = client.get_default_database()

    # {"name": channel_name, "id": channel_id}
    channels = db["channels"]
    # {"name": user_name, "id": user_id}
    users = db["users"]

def clean_database():
    channels.drop()
    users.drop()

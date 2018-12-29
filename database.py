import pickle
data = None

def load_database():
    global data
    try:
        data = pickle.load(open("data.p", "rb"))
    except:
        pass
    finally:
        if not data:
            data = {
                "channels": {},
                "users": {
                    "id_to_name": {},
                    "name_to_id": {},
                },
            }

def save_database():
    global data
    pickle.dump(data, open("data.p", "wb"))

def clean_database():
    data = {
        "channels": {},
        "users": {
            "id_to_name": {},
            "name_to_id": {},
        },
    }


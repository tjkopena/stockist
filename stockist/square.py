
from square.client import Client as sqClient

import logberry
import tjawn
from dataclasses import dataclass
from dacite import from_dict

@dataclass
class Settings:
    access_token: str
    environment: str

def load_configuration(fn='.conf/square.jawn'):
    return from_dict(data_class=Settings, data=tjawn.loads(open(fn, "rt").read()))

@dataclass
class Item:
    id: str

class Client:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = sqClient(access_token = settings.access_token,
                               environment = settings.environment)

    def delete_catalog(self):
        t = logberry.task("Deleting catalog")
        objects = self.get_catalog();

        limit = self.client.catalog.catalog_info().body['limits']['batch_delete_max_object_ids']

        while objects:
            batch = [from_dict(data_class=Item, data=o).id for o in objects[:limit]]

            tt = t.task("Deleting batch")
            self.client.catalog.batch_delete_catalog_objects({'object_ids': batch})
            tt.success(n=len(batch))

            objects = objects[len(batch):]

        t.success()

    def get_catalog(self):
        t = logberry.task("Retrieving catalog")

        objects = []
        cursor = None

        while True:
            res = self.client.catalog.list_catalog(cursor=cursor, types='ITEM')
            objects.extend(res.body.get('objects', []))
            cursor = res.cursor
            if not res.cursor:
                break

        t.success(items=len(objects))

        return objects

def client(settings: Settings):
    return Client(settings)

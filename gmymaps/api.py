"""Client for the internal endpoints of the My Maps web editor.

Every write is a "mutation" posted to /mutate, shaped like the requests the web app sends.
Payload layouts were captured from the web app; see docs/protocol.md.
"""

import base64
import enum
import json
import random
import time
from dataclasses import dataclass, field

import requests
from lxml import html

from .cookies import get_cookies

BASE_URL = "https://www.google.com/maps/d/u/0"
GEOMETRY_KEY = "strgeo:" + base64.b64encode(b"gme_geometry_").decode()


# Slots of the change list: each kind of edit lives at a fixed index.
class Slot(enum.IntEnum):
    CREATE_FEATURE = 1
    DELETE_FEATURE = 2
    UPDATE_FEATURE = 4
    MAP_INFO = 8
    CREATE_LAYER = 9
    DELETE_LAYER = 10
    RENAME_LAYER = 11
    MOVE_LAYER = 25


@dataclass
class Point:
    id: str
    layer_id: str
    name: str | None
    description: str | None
    coords: tuple[float, float] | None
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class Layer:
    id: str
    name: str
    columns: dict[str, str]  # column name -> attribute key
    title_key: str | None
    points: list[Point]

    @property
    def description_key(self):
        return self.columns.get("description")


@dataclass
class MyMap:
    id: str
    title: str
    description: str | None
    layers: list[Layer]

    def layer(self, name_or_id):
        for layer in self.layers:
            if name_or_id in (layer.id, layer.name):
                return layer
        raise KeyError(f"No layer named or with id {name_or_id!r}")


def new_feature_id():
    # Same shape as the web app's ids: 16 uppercase hex digits.
    return f"{random.getrandbits(64):016X}"


def change(map_id, slot, body):
    """One entry of the change list: the map id, then the body at its slot."""
    return [map_id] + [None] * (slot - 1) + [body]


def text_attr(key, value, edited=True):
    attr = [None] * 10
    attr[4] = value
    attr[7] = 1 if edited else None
    attr[9] = key
    return attr


def geometry_attr(lat, lng, edited=True):
    attr = [None] * 10
    attr[6] = [[[lat, lng]]]
    attr[7] = 1 if edited else None
    attr[9] = GEOMETRY_KEY
    return attr


def parse_point(raw, layer_id, key_to_column, title_key, description_key):
    point = Point(id=raw[0], layer_id=layer_id, name=None, description=None, coords=None)
    for attr in raw[11] or []:
        key = attr[9]
        if key == GEOMETRY_KEY and attr[6]:
            point.coords = tuple(attr[6][0][0])
        elif key == title_key:
            point.name = attr[4]
        elif key == description_key:
            point.description = attr[4]
        elif key in key_to_column and attr[4] is not None:
            point.fields[key_to_column[key]] = attr[4]
    return point


def parse_layer(raw):
    columns = {}
    if len(raw) > 14 and raw[14]:
        for name, _type, key in raw[14][0]:
            columns[name] = key
    title_key = raw[5][4] if raw[5] and len(raw[5]) > 4 else None
    layer = Layer(id=raw[0], name=raw[1], columns=columns, title_key=title_key, points=[])

    key_to_column = {key: name for name, key in columns.items()}
    raw_points = raw[17] if len(raw) > 17 and raw[17] else []
    for raw_point in raw_points:
        layer.points.append(parse_point(raw_point, layer.id, key_to_column, title_key, layer.description_key))
    return layer


def parse_map(map_data):
    header = map_data[0]
    layers = [parse_layer(raw) for raw in map_data[1] or []]
    return MyMap(id=header[0], title=header[1], description=header[2], layers=layers)


def extract_page_data(page):
    # Decode explicitly: given raw bytes, lxml would guess latin-1 and garble accents.
    if isinstance(page, bytes):
        page = page.decode("utf-8")
    for script in html.fromstring(page).xpath("//script[not(@src)]"):
        if script.text and "_pageData" in script.text:
            raw = script.text.split("_pageData = ", 1)[1].strip().rstrip(";")
            return json.loads(raw)
    raise RuntimeError("_pageData not found in the editor page")


def get_client():
    return MapsClient(get_cookies())


class MapsClient:
    MAX_ATTEMPTS = 5

    def __init__(self, cookies):
        self.session = requests.Session()
        self.session.cookies = cookies
        self.xsrf_tokens = {}
        self.layers = {}  # (map_id, layer_id) -> Layer, kept for the attribute keys

    def _request(self, method, url, **kwargs):
        """Send a request, waiting and retrying when Google rate-limits (HTTP 429)."""
        for attempt in range(self.MAX_ATTEMPTS):
            response = self.session.request(method, url, timeout=30, **kwargs)
            if response.status_code != 429 or attempt == self.MAX_ATTEMPTS - 1:
                break
            retry_after = response.headers.get("Retry-After", "")
            time.sleep(int(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1))
        response.raise_for_status()
        return response

    # Reading

    def get_map(self, map_id):
        response = self._request("GET", f"{BASE_URL}/edit", params={"mid": map_id})
        if "/edit" not in response.url:
            raise PermissionError("No edit access: cookies expired, or the map is not shared with this account")

        page_data = extract_page_data(response.content)
        self.xsrf_tokens[map_id] = page_data["xsrfToken"]
        my_map = parse_map(json.loads(page_data["mapdataJson"]))
        for layer in my_map.layers:
            self.layers[(map_id, layer.id)] = layer
        return my_map

    def _layer(self, map_id, layer_id):
        if (map_id, layer_id) not in self.layers:
            self.get_map(map_id)
        return self.layers[(map_id, layer_id)]

    # Writing

    def mutate(self, map_id, *changes):
        if map_id not in self.xsrf_tokens:
            self.get_map(map_id)
        payload = [map_id, None, 2] + [None] * 27 + [list(changes)]
        response = self._request(
            "POST",
            f"{BASE_URL}/mutate",
            params={"cid": "mp", "rt": "j"},
            data={"f.req": json.dumps(payload), "at": self.xsrf_tokens[map_id]},
        )
        # The body starts with an anti-JSON-hijacking prefix before the first bracket.
        body = response.text
        return json.loads(body[body.index("["):])

    # Map

    def set_map_info(self, map_id, title, description=""):
        self.mutate(map_id, change(map_id, Slot.MAP_INFO, [title, description]))

    # Layers

    def create_layer(self, map_id, name=None):
        before = {layer.id for layer in self.get_map(map_id).layers}
        self.mutate(map_id, change(map_id, Slot.CREATE_LAYER, [None, 1]))
        created = [layer for layer in self.get_map(map_id).layers if layer.id not in before]
        if len(created) != 1:
            raise RuntimeError("Could not identify the created layer")
        layer_id = created[0].id
        if name:
            self.rename_layer(map_id, layer_id, name)
        return layer_id

    def rename_layer(self, map_id, layer_id, name):
        self.mutate(map_id, change(map_id, Slot.RENAME_LAYER, [layer_id, name]))

    def delete_layer(self, map_id, layer_id):
        self.mutate(map_id, change(map_id, Slot.DELETE_LAYER, [layer_id]))

    def move_layer(self, map_id, layer_id, position):
        """Position 0 is the top of the legend."""
        self.mutate(map_id, change(map_id, Slot.MOVE_LAYER, [layer_id, position]))

    # Points

    def create_point(self, map_id, layer_id, name, lat, lng, description=None):
        layer = self._layer(map_id, layer_id)
        point_id = new_feature_id()
        attrs = [geometry_attr(lat, lng, edited=False), text_attr(layer.title_key, name, edited=False)]
        if description is not None and layer.description_key:
            attrs.append(text_attr(layer.description_key, description, edited=False))
        feature = [point_id] + [None] * 10 + [attrs]
        self.mutate(map_id, change(map_id, Slot.CREATE_FEATURE, [None, [feature], None, layer_id]))
        return point_id

    def update_point(self, map_id, layer_id, point_id, name=None, description=None, coords=None):
        layer = self._layer(map_id, layer_id)
        attrs = []
        if name is not None:
            attrs.append(text_attr(layer.title_key, name))
        if description is not None:
            if not layer.description_key:
                raise ValueError(f"Layer {layer.name!r} has no description column")
            attrs.append(text_attr(layer.description_key, description))
        if coords is not None:
            attrs.append(geometry_attr(*coords))
        feature = [point_id] + [None] * 10 + [attrs]
        self.mutate(map_id, change(map_id, Slot.UPDATE_FEATURE, [None, [feature], None, layer_id]))

    def move_point(self, map_id, layer_id, point_id, lat, lng):
        self.update_point(map_id, layer_id, point_id, coords=(lat, lng))

    def delete_point(self, map_id, layer_id, point_id):
        self.mutate(map_id, change(map_id, Slot.DELETE_FEATURE, [None, [point_id], layer_id]))

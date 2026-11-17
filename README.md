# gmymaps

Read and edit [Google My Maps](https://www.google.com/maps/d/) maps from Python.

Google has no API for My Maps<sup>[1](#references)</sup>. gmymaps talks to the same internal endpoints as
the My Maps web editor, with your own Google session.

> [!WARNING]
> This is an unofficial, reverse-engineered client. Google can change these endpoints at any time and
> break it. Try your scripts on a throwaway map before running them on one that matters.

Fork of [heyzec/google-mymaps-api](https://github.com/heyzec/google-mymaps-api), extended to cover
styles, icons, layer order and map details.

## Features

| | |
|---|---|
| Map | read everything; set the title and description |
| Layers | create, rename, delete, reorder, show or hide; individual or uniform style; color and icon; labels |
| Points | create, rename, describe, move, delete, reorder; color and icon |
| Icons | catalog of the 397 editor icons, searchable by label |

Lines, shapes, routes, photos and extra data columns are not supported yet.

## Install

Python 3.11+ and a Chromium-based browser (Chromium or Google Chrome) for signing in.

```sh
pip install git+https://github.com/Striffly/google-mymaps-api.git
# or
uv add git+https://github.com/Striffly/google-mymaps-api.git
```

## Sign in

The My Maps editor only accepts a browser session: OAuth tokens, even with Drive access, are
redirected to the read-only viewer. gmymaps therefore uses the cookies of a signed-in browser
profile, but never your everyday browser's:

```sh
python -m gmymaps.login
```

1. A Chromium window opens on a new, empty, temporary profile.
2. Sign in to the Google account that can edit your maps, wait for My Maps to load, close the window.
3. gmymaps reads the profile's google.com cookies headlessly, saves them, and deletes the profile.

Cookies are saved to `~/.config/gmymaps/cookies.txt` (mode 600). Set `GMYMAPS_COOKIES` to use another
path, or pass `--output`.

Google sessions eventually expire. To refresh the cookies without signing in again, keep the profile:

```sh
python -m gmymaps.login --profile ~/.config/gmymaps/profile            # first time, with a window
python -m gmymaps.login --profile ~/.config/gmymaps/profile --refresh  # later, headless
```

> [!CAUTION]
> The cookie file (and a kept profile) gives full access to the Google account. Keep it private, and
> consider a dedicated Google account that only has access to the maps you script.

## Usage

The map id is the `mid` parameter of the editor URL: `https://www.google.com/maps/d/edit?mid=MAP_ID`.

### Read a map

```python
import gmymaps

client = gmymaps.get_client()
my_map = client.get_map(map_id)

for layer in my_map.layers:
    print(layer.name, layer.style_mode, layer.color, layer.icon)
    for point in layer.points:
        print(point.name, point.description, point.coords, point.color, point.icon)

tokyo = my_map.layer("Tokyo")  # by name or id
```

### Map and layers

```python
client.set_map_info(map_id, "Japan 2027", "Trip planning")

layer_id = client.create_layer(map_id, name="Tokyo")
client.rename_layer(map_id, layer_id, "Tokyo - temples")
client.move_layer(map_id, layer_id, 0)             # 0 = top of the legend
client.set_layer_labels(map_id, layer_id, "name")  # None hides the labels
client.set_layer_visible(map_id, layer_id, False)  # unchecked in the legend, for every viewer
client.delete_layer(map_id, layer_id)
```

### Points

```python
point_id = client.create_point(map_id, layer_id, "Sensō-ji", 35.7148, 139.7967, description="Asakusa")
client.update_point(map_id, layer_id, point_id, name="Sensō-ji temple", description="Go early")
client.move_point(map_id, layer_id, point_id, 35.7147, 139.7966)
client.order_points(map_id, layer_id, [point_id, ...])  # legend order, first to last
client.delete_point(map_id, layer_id, point_id)
```

### Colors and icons

A layer either styles each point on its own, or gives all its points the same style.

```python
from gmymaps import StyleMode, find_icons, icon_id

find_icons("ski")   # [{'id': 1688, 'label': 'Ski de descente', 'section': 'Sports et loisirs'}, ...]
icon_id("Temple")   # 1706

# One color and icon per point
client.set_layer_style_mode(map_id, layer_id, StyleMode.INDIVIDUAL)
client.set_point_style(map_id, layer_id, point_id, color="#C2185B", icon=icon_id("Temple"))

# Same color and icon for the whole layer
client.set_layer_style_mode(map_id, layer_id, StyleMode.UNIFORM)
client.set_layer_style(map_id, layer_id, color="#558B2F", icon=icon_id("Source d'eau chaude"))
```

Icon labels are in French, as scraped from the editor; `find_icons` ignores case and accents.
Any `#RRGGBB` color works; the editor's palette uses Material colors such as `#0288D1` or `#FF5252`.

Requests that Google rate-limits (HTTP 429) are retried with a backoff.

## Contributing

- [docs/protocol.md](docs/protocol.md) describes the editor's data and request formats.
- `tools/capture_mutations.py` prints the requests the editor sends while you edit a map by hand:
  the way to add a new operation.
- `tools/check_client.py MAP_ID` runs every operation against a throwaway map and checks the result.

## References

1. Feature request for a My Maps API: https://issuetracker.google.com/issues/35820262

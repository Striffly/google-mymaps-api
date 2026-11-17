# My Maps editor protocol

Captured from the web editor (November 2026) by logging its `mutate` requests while editing a test map.

## Reading

`GET https://www.google.com/maps/d/u/0/edit?mid=MAP_ID` with a signed-in session.
An inline script sets `_pageData`, a JSON object with:

- `xsrfToken`: sent as `at` with every mutation.
- `mapdataJson`: the whole map, as a JSON string.

Without edit access the request is redirected to `/viewer`. OAuth tokens (gcloud) are not accepted; only session cookies are.

### Map data

| Path | Content |
|---|---|
| `[0][0]`, `[0][1]`, `[0][2]` | map id, title, description |
| `[0][4]` | layer ids, legend order |
| `[0][8]` | ids of the hidden (unchecked) layers, or null |
| `[1]` | layers |

Layer:

| Path | Content |
|---|---|
| `[0]`, `[1]` | layer id, name |
| `[5][4]` | attribute key of the title column |
| `[6]` | style block (below) |
| `[14][0]` | columns: `[name, type, key]`; type 6 = geometry, 3 = text |
| `[17]` | features |

Attribute keys are `str:` + base64 of the column name (`strgeo:` for the geometry).
Column names follow the language the layer was created in: the title column is `nom` on a French map, `name` on an English one, so keys must be read from the schema, never hard-coded.

Feature: `[0]` is the id (16 uppercase hex digits, chosen by the client), `[11]` the attributes.
Attribute: `[4]` text value, `[6]` geometry `[[[lat, lng]]]`, `[9]` key.

Style block: `[0]` active mode, `[16]` one entry per mode `[mode, base style, …]`.
Stored modes: 4 sequence, 5 uniform, 6 individual, 7 by column, 8 gradient.
In individual mode, `entry[17]` is `[base style, [[feature_id, style], …]]`.
A style has the outline color at `[3]`, the fill color at `[4]` (hex strings) and the icon id at `[7]`.
`[19]` is the key of the column shown as label, or null.

## Writing

`POST https://www.google.com/maps/d/u/0/mutate?cid=mp&rt=j`, form fields:

- `f.req`: `[MAP_ID, null, 2, null × 27, [CHANGE, …]]`
- `at`: the xsrf token

A change is `[MAP_ID, null, …, BODY]`, BODY at a fixed index per operation:

| Index | Operation | BODY |
|---|---|---|
| 1 | create feature | `[null, [FEATURE], null, LAYER]` |
| 2 | delete feature | `[null, [FEATURE_ID], LAYER]` |
| 4 | update feature | `[null, [FEATURE], null, LAYER]`, only the changed attributes |
| 8 | map title, description | `[TITLE, DESCRIPTION]` |
| 9 | create layer | `[null, 1]` |
| 10 | delete layer | `[LAYER]` |
| 11 | rename layer, show or hide it | `[LAYER, NAME]`; `[LAYER, null, 1]` hides it, `[LAYER, null, 0]` shows it |
| 25 | move layer | `[LAYER, POSITION]`, 0 = top |
| 28 | layer style | `[LAYER, [MODE]]`, `[LAYER, null, null, null, [[null, STYLE]]]`, or labels `[LAYER, null × 6, [1, KEY]]` (`[0]` hides them) |
| 29 | feature style | `[LAYER, null, null, [FEATURE_ID, [STYLE]]]` |

FEATURE is `[ID, null × 10, [ATTRIBUTE, …]]`; an attribute is `[null × 4, TEXT, null, GEOMETRY, EDITED, null, KEY]`, with EDITED = 1 on updates.

Modes sent at index 28: 1 individual, 4 uniform (not the stored codes).

STYLE, as sent for a whole layer (a feature wraps it in one more list):

- color: `[[[null, [null, [C]]]], [[C]], [[C], [C]]]` with C the color as an integer (`0x01579B` → 87963)
- icon: `[[[1, [ICON_ID]]]]`

The web app sends color and icon as two separate mutations.

## Icons

`gmymaps/icons.json` lists the 397 current icons (id, French label, section), scraped from the editor's icon dialog.
Image: `https://mt.google.com/vt/icon/name=icons/onion/SHARED-mymaps-container_4x.png,icons/onion/ID-NAME_4x.png&highlight=RRGGBB`.

## Capturing a new operation

1. Sign in once with a kept profile: `python -m gmymaps.login --profile ~/.config/gmymaps/profile`.
2. Open that profile with remote debugging: `chromium --user-data-dir=$HOME/.config/gmymaps/profile --remote-debugging-port=9222`, then open a test map in the editor.
3. Run `python tools/capture_mutations.py` and make the edit by hand: each mutation prints as one JSON line.
4. Add the operation to `gmymaps/api.py`, a check to `tools/check_client.py`, and the layout to this file.

## Not captured yet

Lines and shapes, routes, photos, extra data columns, base map style, sharing.

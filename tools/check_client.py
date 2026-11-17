"""End-to-end check of every client operation, on a throwaway map you own.

Usage: python tools/check_client.py MAP_ID

It renames the map, then creates, styles and deletes a temporary layer. Never run it on a real map.
"""

import sys

from gmymaps import StyleMode, get_client, icon_id

results = []


def check(label, condition, detail=""):
    results.append(condition)
    print(f"{'OK  ' if condition else 'FAIL'} {label}{'' if condition else f'  ({detail})'}")


def points_by_id(client, map_id, layer_id):
    return {point.id: point for point in client.get_map(map_id).layer(layer_id).points}


def main():
    map_id = sys.argv[1]
    client = get_client()
    start = client.get_map(map_id)
    print(f"Map « {start.title} », layers: {[layer.name for layer in start.layers]}")

    # Accented text checks the page decoding as well as the write.
    client.set_map_info(map_id, "gmymaps check (à supprimer)", "Vérifié par check_client.py")
    my_map = client.get_map(map_id)
    check("map title and description",
          (my_map.title, my_map.description) == ("gmymaps check (à supprimer)", "Vérifié par check_client.py"),
          f"{my_map.title!r}, {my_map.description!r}")

    layer_id = client.create_layer(map_id, name="check_client layer")
    check("create and name a layer", client.get_map(map_id).layer(layer_id).name == "check_client layer")

    temple = client.create_point(map_id, layer_id, "Sensō-ji", 35.7148, 139.7967, description="Temple d'Asakusa")
    onsen = client.create_point(map_id, layer_id, "Onsen", 35.70, 139.80)
    points = points_by_id(client, map_id, layer_id)
    check("create points with a name", (points[temple].name, points[onsen].name) == ("Sensō-ji", "Onsen"),
          f"{points[temple].name!r}, {points[onsen].name!r}")
    check("description on creation", points[temple].description == "Temple d'Asakusa")
    check("coordinates on creation", points[temple].coords == (35.7148, 139.7967))

    client.update_point(map_id, layer_id, onsen, name="Onsen renommé", description="Nouvelle description")
    client.move_point(map_id, layer_id, onsen, 35.6895, 139.6917)
    point = points_by_id(client, map_id, layer_id)[onsen]
    check("rename a point", point.name == "Onsen renommé", repr(point.name))
    check("change a description", point.description == "Nouvelle description")
    check("move a point", point.coords == (35.6895, 139.6917))

    client.set_layer_style_mode(map_id, layer_id, StyleMode.INDIVIDUAL)
    client.set_point_style(map_id, layer_id, temple, color="#C2185B", icon=icon_id("Temple"))
    layer = client.get_map(map_id).layer(layer_id)
    point = {p.id: p for p in layer.points}[temple]
    check("individual style mode", layer.style_mode == "individual", layer.style_mode)
    check("point color and icon", (point.color, point.icon) == ("C2185B", icon_id("Temple")),
          f"{point.color}, {point.icon}")

    client.set_layer_style_mode(map_id, layer_id, StyleMode.UNIFORM)
    client.set_layer_style(map_id, layer_id, color="#558B2F", icon=icon_id("Source d'eau chaude"))
    layer = client.get_map(map_id).layer(layer_id)
    check("uniform style mode", layer.style_mode == "uniform", layer.style_mode)
    check("layer color and icon", (layer.color, layer.icon) == ("558B2F", icon_id("Source d'eau chaude")),
          f"{layer.color}, {layer.icon}")

    client.set_layer_labels(map_id, layer_id, "name")
    labels = client.get_map(map_id).layer(layer_id).labels
    check("show names as labels", labels == "name", repr(labels))
    client.set_layer_labels(map_id, layer_id, None)
    labels = client.get_map(map_id).layer(layer_id).labels
    check("hide labels", labels is None, repr(labels))

    client.set_layer_visible(map_id, layer_id, False)
    check("hide the layer", not client.get_map(map_id).layer(layer_id).visible)
    client.set_layer_visible(map_id, layer_id, True)
    check("show the layer", client.get_map(map_id).layer(layer_id).visible)

    client.move_layer(map_id, layer_id, 0)
    check("move the layer to the top", client.get_map(map_id).layers[0].id == layer_id)

    client.order_points(map_id, layer_id, [onsen, temple])
    order = list(points_by_id(client, map_id, layer_id))
    check("reorder points", order == [onsen, temple], repr(order))

    client.delete_point(map_id, layer_id, onsen)
    remaining = list(points_by_id(client, map_id, layer_id))
    check("delete a point", remaining == [temple], repr(remaining))

    client.delete_layer(map_id, layer_id)
    check("delete the layer", layer_id not in [layer.id for layer in client.get_map(map_id).layers])

    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()

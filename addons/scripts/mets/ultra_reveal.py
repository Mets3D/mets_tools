import bpy

def reveal_recursive(lc):
    lc.exclude = False
    lc.hide_viewport = False
    lc.collection.hide_viewport = False

    for o in lc.collection.objects:
        o.hide_viewport = False
        o.hide_set(False)

    for lc in lc.children:
        reveal_recursive(lc)

reveal_recursive(bpy.context.view_layer.layer_collection)
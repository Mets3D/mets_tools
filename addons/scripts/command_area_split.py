# Split the area
# Press MMB to toggle direction

# Usage (Command tab):
# execute_script("scripts/command_area_split.py", mode='AUTO')

import bpy


def split_area(mode='AUTO'):
    a = bpy.context.area
    if not a:
        return

    if mode not in {'AUTO', 'VERTICAL', 'HORIZONTAL'}:
        mode = 'AUTO'

    if mode == 'AUTO':
        mode = 'VERTICAL' if a.width > a.height else 'HORIZONTAL'

    mx, my = None, None
    mx = a.x + a.width // 2
    if a.y != 0:
        my = a.y
    elif a.y + a.height != bpy.context.window.height:
        my = a.y + a.height
    vertical = None if mx is None or my is None else (mx, my)

    mx, my = None, None
    my = a.y + a.height // 2
    if a.x != 0:
        mx = a.x
    elif a.x + a.width != bpy.context.window.width:
        mx = a.x + a.width
    horizontal = None if mx is None or my is None else (mx, my)

    mouse = mode == 'VERTICAL' and vertical or horizontal or vertical
    if mouse:
        bpy.ops.screen.area_split(
            'INVOKE_DEFAULT', cursor=[mouse[0], mouse[1]])


mode = locals().get("kwargs", {}).get("mode", 'AUTO')
split_area(mode)

# Join 2 areas

# Usage (Command tab):
# execute_script("scripts/command_area_join.py")

import bpy
from pie_menu_editor import pme


def join_area():
    a = bpy.context.area
    if not a:
        return

    x, y, w, h = a.x, a.y, a.width, a.height
    if "cursor" in bpy.ops.screen.area_join.get_rna_type().properties:
        cursor = None
        for area in bpy.context.screen.areas:
            if a.x == area.x and a.width == area.width:
                if a.y + a.height + 1 == area.y:
                    cursor = (x + 2, y + h - 2)
                    break
                elif area.y + area.height + 1 == a.y:
                    cursor = (x + 2, y)
                    break
            if a.y == area.y and a.height == area.height:
                if a.x + a.width + 1 == area.x:
                    cursor = (x + w - 2, y + 2)
                    break
                elif area.x + area.width + 1 == a.x:
                    cursor = (x, y + 2)
                    break

        if cursor:
            bpy.ops.screen.area_join('INVOKE_DEFAULT', cursor=cursor)

        return

    r = (x + w + 2, y + h - 2, x + w - 2, y + h - 2)
    l = (x - 2, y + 2, x + 2, y + 2)
    t = (x + w - 2, y + h + 2, x + w - 2, y + h - 2)
    b = (x + 2, y - 2, x + 2, y + 2)

    mx, my = pme.context.event.mouse_x, pme.context.event.mouse_y
    cx, cy = x + 0.5 * w, y + 0.5 * h
    horizontal = (l, r) if mx < cx else (r, l)
    vertical = (b, t) if my < cy else (t, b)

    dx = min(mx - x, x + w - mx)
    dy = min(my - y, y + h - my)
    rects = vertical + horizontal if dy < dx else horizontal + vertical

    for rect in rects:
        if 'RUNNING_MODAL' in bpy.ops.screen.area_join(
                'INVOKE_DEFAULT', min_x=rect[0], min_y=rect[1],
                max_x=rect[2], max_y=rect[3]):
            break


join_area()

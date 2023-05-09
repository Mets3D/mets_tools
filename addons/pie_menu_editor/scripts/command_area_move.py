# Moves the edge (TOP, BOTTOM, LEFT or RIGHT) of the area

# Usage (Command tab):
# execute_script("scripts/command_area_move.py", area=C.area, edge='TOP', delta=300, move_cursor=False)

import bpy


def move_area(area, edge='TOP', delta=300, move_cursor=False):
    a = area or bpy.context.area
    if not a:
        return

    if edge not in {'BOTTOM', 'LEFT', 'RIGHT'}:
        edge = 'TOP'

    mx, my = E.mouse_x, E.mouse_y
    x, y = mx, my
    if edge == 'TOP':
        y = a.y + a.height
        my += delta * move_cursor
    elif edge == 'BOTTOM':
        y = a.y
        my += delta * move_cursor
    elif edge == 'RIGHT':
        x = a.x + a.width
        mx += delta * move_cursor
    elif edge == 'LEFT':
        x = a.x
        mx += delta * move_cursor

    bpy.context.window.cursor_warp(x, y)

    bpy.ops.pme.timeout(
        delay=0.0001,
        cmd=(
            "bpy.ops.screen.area_move(x=%d, y=%d, delta=%d);"
            "bpy.context.window.cursor_warp(%d, %d)"
        ) % (x, y, delta, mx, my)
    )


kwargs = locals().get("kwargs", {})
area = kwargs.get("area", C.area)
edge = kwargs.get("edge", 'TOP')
delta = kwargs.get("delta", 300)
move_cursor = kwargs.get("move_cursor", False)

move_area(area, edge, delta, move_cursor)

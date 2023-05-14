# Join 2 areas

# Usage (Command tab):
# execute_script("scripts/command_area_join.py")

import bpy
from pie_menu_editor import pme

def join_area(direction: str):
    active = bpy.context.area
    if not active:
        return

    # Thanks to Harley Acheson for explaining: 
    # https://devtalk.blender.org/t/join-two-areas-by-python-area-join-what-arguments-blender-2-80/18165/2
    cursor = None
    mouse_x, mouse_y = pme.context.event.mouse_x, pme.context.event.mouse_y
    if direction == 'LEFT':
        cursor = (active.x+2, mouse_y)
    elif direction == 'RIGHT':
        cursor = (active.x+active.width, mouse_y)
    elif direction == 'UP':
        cursor = (mouse_x, active.y+active.height)
    elif direction == 'DOWN':
        cursor = (mouse_x, active.y)

    bpy.ops.screen.area_join('INVOKE_DEFAULT', cursor=cursor)

kwargs = locals().get("kwargs", {})
direction = kwargs.get("direction", 'LEFT')

join_area(direction=direction)

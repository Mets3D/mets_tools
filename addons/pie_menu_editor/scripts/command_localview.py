# Toggle Local/Global view mode without changing the view

# Usage 1 (Command tab):
# execute_script("scripts/command_localview.py", mode='TOGGLE')

# Usage 2 (Command tab):
# from .scripts.command_localview import localview; localview('TOGGLE')

import bpy


def localview(mode='TOGGLE'):
    context = bpy.context
    area = context.area
    area_type = area.ui_type if hasattr(area, "ui_type") else area.type
    if area_type != 'VIEW_3D':
        return

    if mode not in {'TOGGLE', 'LOCAL', 'GLOBAL'}:
        mode = 'TOGGLE'

    if len(context.space_data.region_quadviews):
        regions = context.space_data.region_quadviews
    else:
        regions = [context.space_data.region_3d]

    view_data = [
        dict(
            view_camera_offset=region.view_camera_offset,
            view_camera_zoom=region.view_camera_zoom,
            view_distance=region.view_distance,
            view_location=region.view_location.copy(),
            view_matrix=region.view_matrix.copy(),
            view_perspective=region.view_perspective,
            is_perspective=region.is_perspective,
            view_rotation=region.view_rotation.copy(),
        ) for region in regions]

    upr = getattr(context, "user_preferences", context.preferences)
    smooth_view = upr.view.smooth_view
    upr.view.smooth_view = 0

    if mode == 'TOGGLE' or \
            mode == 'LOCAL' and not context.space_data.local_view or \
            mode == 'GLOBAL' and context.space_data.local_view:
        bpy.ops.view3d.localview()

    upr.view.smooth_view = smooth_view
    for region, data in zip(regions, view_data):
        for k, v in data.items():
            setattr(region, k, v)


mode = locals().get("kwargs", {}).get("mode", 'TOGGLE')
localview(mode)

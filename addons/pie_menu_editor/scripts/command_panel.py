# Open side panel with a single tab/category

# Usage (Command tab):

# Open panels by tab/category
# from .scripts.command_panel import open_tab; open_tab("Tools", region='ANY')

# Open panel by name
# from .scripts.command_panel import open_panel; open_panel("3D Cursor", region='ANY')

# Restore hidden panels
# from .scripts.command_panel import restore_panels; restore_panels()

import bpy
from inspect import isclass


hidden_panels = {}


@classmethod
def _dummy_poll(cls, context):
    return False


def _panel_types():
    ret = []
    panel_tp = bpy.types.Panel
    for tp_name in dir(bpy.types):
        tp = getattr(bpy.types, tp_name)
        if tp == panel_tp or not isclass(tp) or not issubclass(tp, panel_tp):
            continue

        ret.append(tp)

    return ret


def _reregister_panel(tp):
    try:
        bpy.utils.unregister_class(tp)
        bpy.utils.register_class(tp)
    except:
        pass


def _hide_panel(tp, context):
    area = context.area.type
    if area not in hidden_panels:
        hidden_panels[area] = {}

    panels = hidden_panels.get(context.area.type, None)
    if tp.__name__ in panels:
        return
    panels[tp.__name__] = hasattr(tp, "poll") and tp.poll
    tp.poll = _dummy_poll

    _reregister_panel(tp)


def _restore_panel(tp, context):
    panels = hidden_panels.get(context.area.type, None)
    if panels and tp.__name__ in panels:
        poll = panels.pop(tp.__name__)
        if poll:
            tp.poll = poll
        else:
            delattr(tp, "poll")

        _reregister_panel(tp)


def restore_panels():
    context = bpy.context
    panels = hidden_panels.get(context.area.type, None)
    if not panels:
        return

    for tp in _panel_types():
        _restore_panel(tp, context)

    context.area.tag_redraw()


def _open_panels_by(name=None, category=None, region='ANY'):
    context = bpy.context
    side_regions = {'TOOLS', 'UI'}
    if region not in side_regions:
        region = 'ANY'

    panels_to_show = []
    panels_to_hide = []
    for tp in _panel_types():
        if tp.bl_space_type != context.area.type or \
                tp.bl_region_type not in side_regions:
            continue
        if name and getattr(tp, "bl_label", None) == name:
            panels_to_show.append(tp)
        elif category and getattr(tp, "bl_category", "Misc") == category:
            panels_to_show.append(tp)
        else:
            panels_to_hide.append(tp)

    if not panels_to_show:
        return

    for tp in panels_to_show:
        if region == 'ANY':
            region = tp.bl_region_type
        _restore_panel(tp, context)

    for tp in panels_to_hide:
        if tp.bl_region_type == region:
            _hide_panel(tp, context)

    context.area.tag_redraw()

    for r in context.area.regions:
        if r.type == region and r.width <= 1:
            bpy.ops.wm.pme_sidebar_toggle(tools=region == 'TOOLS')


def open_tab(category, region='ANY'):
    _open_panels_by(category=category, region=region)


def open_panel(name, region='ANY'):
    _open_panels_by(name=name, region=region)

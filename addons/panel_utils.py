import bpy
import re
from inspect import isclass
from itertools import chain
from types import MethodType
from .addon import prefs, uprefs, print_exc, ic, is_28
from . import constants as CC
from . import c_utils as CTU
from bl_ui import space_userpref
from .bl_utils import bl_context, PopupOperator
from .ui import utitle
from .debug_utils import *
from . import pme


_hidden_panels = {}
_panels = {}
_context_items = []
_bl_panel_types = []

_prefs_panel_types = None
_prefs_panel_polls = None


def panel_types_sorter(tp, value=0):
    if tp is None:
        return value - 1

    pid = getattr(tp, "bl_parent_id", None)
    if pid is None or value > 10:
        return value
    else:
        return panel_types_sorter(
            getattr(bpy.types, pid, _hidden_panels.get(pid, None)), value + 1)


def panel_type_names_sorter(tp_name):
    return panel_types_sorter(
        getattr(bpy.types, tp_name, None))


def hide_panel(tp_name):
    if tp_name in _hidden_panels:
        pass

    elif hasattr(bpy.types, tp_name):
        tp = getattr(bpy.types, tp_name)
        bpy.utils.unregister_class(tp)
        _hidden_panels[tp_name] = tp


def unhide_panel(tp_name):
    tp = _hidden_panels.get(tp_name, None)
    if tp:
        pid = getattr(tp, "bl_parent_id", None)
        if pid:
            unhide_panel(pid)

        bpy.utils.register_class(tp)
        del _hidden_panels[tp_name]

    else:
        pass


def unhide_panels(tp_names=None):
    if tp_names is None:
        tp_names = list(_hidden_panels.keys())

    def _sort_value(tp, value=0):
        pid = getattr(tp, "bl_parent_id", None)
        if pid is None:
            return value
        else:
            return _sort_value(bpy.types, pid, value + 1)

    def sorter(tp_name):
        tp = _hidden_panels.get(tp_name, None)
        if not tp:
            return 99

        return panel_types_sorter(tp)

    tp_names.sort(key=sorter)

    for tp_name in tp_names:
        unhide_panel(tp_name)


def hidden_panel(tp_name):
    if tp_name in _hidden_panels:
        return _hidden_panels[tp_name]

    return None


def is_panel_hidden(tp_name):
    return tp_name in _hidden_panels


def get_hidden_panels():
    return _hidden_panels


def bar_panel_poll(poll=None):
    def func(cls, context):
        pr = prefs()
        return context.area.width > pr.toolbar_width and \
            context.area.height > pr.toolbar_height and (
                not poll or poll(context))

    return func


def to_valid_name(name):
    def repl(mo):
        c = mo.group(0)
        try:
            cc = ord(c)
        except:
            return "_"
        return chr(97 + cc % 26)

    name = name.replace(" ", "_")
    name = re.sub(r"[^_a-z0-9]", repl, name, flags=re.I)
    return name


def gen_panel_tp_name(name, idx, id):
    return "PME_PT_%s_%s_%d" % (to_valid_name(name), to_valid_name(id), idx)


def add_panel_group(pm, draw_pme_panel, poll_pme_panel):
    last_parent = None
    for i, pmi in enumerate(pm.pmis):
        if pmi.icon == "sub":
            parent = last_parent if pmi.icon == "sub" else None
        else:
            parent = None
            last_parent = gen_panel_tp_name(pm.name, i, pmi.text)

        add_panel(
            pm.name, i, pmi.text, pmi.name,
            pm.panel_space, pm.panel_region,
            pm.panel_context, pm.panel_category,
            draw_pme_panel, poll_pme_panel, parent)


def add_panel(
        name, idx, id, label, space, region,
        context=None, category=None, draw=None, poll=None, parent=None):
    if name not in _panels:
        _panels[name] = []

    if not label:
        label = "PME Panel"

    tp_name = gen_panel_tp_name(name, idx, id)
    defs = {
        "bl_label": label,
        "bl_space_type": space,
        "bl_region_type": region,
        "pm_name": name,
        "pme_data": id,
        "draw": draw,
        "poll": classmethod(poll)
    }
    if context and context != 'ANY':
        defs["bl_context"] = context
    if category:
        defs["bl_category"] = category
    if parent:
        defs["bl_parent_id"] = parent
        defs["bl_options"] = {'DEFAULT_CLOSED'}

    base = bpy.types.Header if region == 'HEADER' else bpy.types.Panel

    tp = type(tp_name, (base,), defs)

    try:
        bpy.utils.register_class(tp)
        _panels[name].insert(idx, tp)
    except:
        print_exc()
        pass


def remove_panel(name, idx):
    if name not in _panels or idx >= len(_panels[name]):
        return

    bpy.utils.unregister_class(_panels[name][idx])
    _panels[name].pop(idx)


def remove_panel_group(name):
    if name not in _panels:
        return

    for panel in _panels[name]:
        bpy.utils.unregister_class(panel)

    del _panels[name]


def refresh_panel_group(name):
    if name not in _panels:
        return

    for panel in _panels[name]:
        bpy.utils.unregister_class(panel)

    for panel in _panels[name]:
        bpy.utils.register_class(panel)


def rename_panel_group(old_name, name):
    if old_name not in _panels:
        return

    for panel in _panels[old_name]:
        panel.pm_name = name

    _panels[name] = _panels[old_name]
    del _panels[old_name]


def move_panel(name, old_idx, idx):
    if name not in _panels or old_idx == idx or \
            old_idx >= len(_panels[name]) or idx > len(_panels[name]):
        return

    panels = _panels[name]
    panel = panels.pop(old_idx)
    panels.insert(idx, panel)

    # refresh_panel_group(name)


def panel_context_items(self, context):
    if not _context_items:
        _context_items.append(('ANY', "Any Context", "", 'NODE_SEL', 0))
        panel_tp = bpy.types.Panel
        contexts = set()
        for tp_name in dir(bpy.types):
            tp = getattr(bpy.types, tp_name, None)
            if not tp or tp == panel_tp or not isclass(tp) or \
                    not issubclass(tp, panel_tp) or \
                    not hasattr(tp, "bl_context"):
                continue

            contexts.add(tp.bl_context)

        idx = 1
        ic_items = prefs().rna_type.properties[
            "panel_info_visibility"].enum_items

        for ctx in sorted(contexts):
            _context_items.append((
                ctx, ctx.replace("_", " ").title(), "",
                ic_items['CTX'].icon, idx))
            idx += 1

    return _context_items


def bl_header_types():
    ret = []
    header_tp = bpy.types.Header
    for tp_name in dir(bpy.types):
        tp = getattr(bpy.types, tp_name, None)
        if not tp or not isclass(tp):
            continue

        if tp is header_tp or not issubclass(tp, header_tp):
            continue

        ret.append(tp)

    return ret


def bl_menu_types():
    ret = []
    menu_tp = bpy.types.Menu
    for tp_name in dir(bpy.types):
        tp = getattr(bpy.types, tp_name, None)
        if not tp or not isclass(tp):
            continue

        if tp is menu_tp or not issubclass(tp, menu_tp):
            continue

        ret.append(tp)

    return ret


def bl_panel_types():
    ret = []
    panel_tp = bpy.types.Panel
    for tp_name in chain(dir(bpy.types), _hidden_panels.keys()):
        tp = _hidden_panels[tp_name] if tp_name in _hidden_panels else \
            getattr(bpy.types, tp_name, None)
        if not tp or not isclass(tp):
            continue

        if tp is panel_tp or not issubclass(tp, panel_tp) or \
                hasattr(tp, "pme_data"):
            continue

        ret.append(tp)

    return ret


def bl_panel_enum_items(include_hidden=True):
    ret = []
    panel_tp = bpy.types.Panel
    panels = chain(dir(bpy.types), _hidden_panels.keys()) if include_hidden \
        else dir(bpy.types)
    for tp_name in panels:
        tp = _hidden_panels[tp_name] if tp_name in _hidden_panels else \
            getattr(bpy.types, tp_name, None)
        if not tp or not isclass(tp):
            continue

        if tp == panel_tp or not issubclass(tp, panel_tp) or \
                hasattr(tp, "pme_data"):
            continue

        tp_name = getattr(tp, "bl_idname", tp.__name__)
        ctx, _, name = tp_name.partition("_PT_")
        if ctx == tp_name:
            ctx = "USER"
        label = hasattr(
            tp, "bl_label") and tp.bl_label or name or tp_name
        label = "%s|%s" % (utitle(label), ctx)

        ret.append((tp_name, label, ""))

    return ret


class PME_OT_panel_toggle(bpy.types.Operator):
    bl_idname = "pme.panel_toggle"
    bl_label = ""
    bl_description = "Show/hide the panel"
    bl_options = {'INTERNAL'}

    collapsed_panels = set()

    panel_id: bpy.props.StringProperty()

    def execute(self, context):
        if self.panel_id in self.__class__.collapsed_panels:
            self.__class__.collapsed_panels.remove(self.panel_id)
        else:
            self.__class__.collapsed_panels.add(self.panel_id)
        return {'FINISHED'}


class PME_OT_panel_reset(bpy.types.Operator):
    bl_idname = "pme.panel_reset"
    bl_label = ""
    bl_description = "Reset panel"
    bl_options = {'INTERNAL'}

    item_id: bpy.props.StringProperty()

    def execute(self, context):
        PLayout.idx_map[self.item_id].clear()
        return {'FINISHED'}


class PME_OT_panel_editor_toggle(bpy.types.Operator):
    bl_idname = "pme.panel_editor_toggle"
    bl_label = ""
    bl_description = "Toggle editor"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()

    def execute(self, context):
        PLayout.editor = not PLayout.editor
        return {'FINISHED'}


class PME_OT_btn_hide(bpy.types.Operator):
    bl_idname = "pme.btn_hide"
    bl_label = ""
    bl_description = "Hide the button"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()
    item_id: bpy.props.StringProperty()

    def execute(self, context):
        indices = PLayout.idx_map[self.item_id]
        if self.idx in indices:
            indices.remove(self.idx)
        else:
            indices.add(self.idx)
        return {'FINISHED'}


class PLayout:
    real_operator = None
    real_getattribute = None
    idx = 0
    item_id = None
    indices = set()
    idx_map = {}
    interactive_panels = False
    active = False
    editor = False

    @staticmethod
    def save(layout, item_id):
        PLayout.active = True
        PLayout.item_id = item_id
        PLayout.real_getattribute = bpy.types.UILayout.__getattribute__
        bpy.types.UILayout.__getattribute__ = PLayout.getattribute
        PLayout.real_operator = layout.operator
        PLayout.idx = 0
        PLayout.interactive_panels = prefs().interactive_panels

    @staticmethod
    def restore():
        PLayout.active = False
        if bpy.types.UILayout.__getattribute__ == PLayout.getattribute:
            bpy.types.UILayout.__getattribute__ = PLayout.real_getattribute

    def getattribute(self, attr):
        bpy.types.UILayout.__getattribute__ = PLayout.real_getattribute
        PLayout.real_operator = getattr(self, "operator")

        if hasattr(PLayout, attr):
            PLayout.idx += 1
            if PLayout.idx in PLayout.indices:
                ret = PLayout.empty
            elif PLayout.editor:
                ret = getattr(PLayout, attr)
            else:
                ret = getattr(self, attr)
        else:
            ret = getattr(self, attr)

        bpy.types.UILayout.__getattribute__ = PLayout.getattribute
        return ret

    def empty(*args, **kwargs):
        pass

    def prop_name(data, property, default=None):
        prop = data.bl_rna.properties[property]
        return prop.name or default or prop

    def btn_operator(text="", icon='NONE', icon_value=0):
        p = PLayout.real_operator(
            PME_OT_btn_hide.bl_idname, text,
            icon=ic(icon), icon_value=icon_value)
        p.idx = PLayout.idx
        p.item_id = PLayout.item_id

    def prop(
            data, property, text=None, text_ctxt="", translate=True,
            icon='NONE', expand=False, slider=False, toggle=False,
            icon_only=False, event=False, full_event=False, emboss=True,
            index=-1, icon_value=0):
        if text is None:
            prop = data.bl_rna.properties[property]
            text = prop.name or property
            if icon == 'NONE' and icon_value == 0:
                icon = prop.icon
        elif not text:
            prop = data.bl_rna.properties[property]
            if icon == 'NONE' and icon_value == 0:
                icon = prop.icon
            # if icon == 'NONE':
            if prop.type in {'ENUM', 'POINTER'} or \
                    prop.subtype == 'COLOR_GAMMA':
                text = data.bl_rna.properties[property].name or property

        if icon_only:
            text = ""

        PLayout.btn_operator(text, icon, icon_value)

    def props_enum(data, property):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "Enum"))

    def prop_menu_enum(
            data, property, text="", text_ctxt="", translate=True,
            icon='NONE'):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "Enum"))

    def prop_enum(
            data, property, value, text="", text_ctxt="", translate=True,
            icon='NONE'):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "Enum"))

    def prop_search(
            data, property, search_data, search_property, text="",
            text_ctxt="", translate=True, icon='NONE'):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "Search"))

    def operator(
            operator, text=None, text_ctxt="", translate=True, icon='NONE',
            emboss=True, icon_value=0):
        PLayout.btn_operator(text if text else "", icon, icon_value)

    def operator_enum(operator, property):
        PLayout.btn_operator(operator)

    def operator_menu_enum(
            operator, property, text="", text_ctxt="", translate=True,
            icon='NONE'):
        PLayout.btn_operator(operator)

    def label(
            text="", text_ctxt="", translate=True, icon='NONE', icon_value=0):
        PLayout.btn_operator(text, icon, icon_value)

    def menu(
            menu, text="", text_ctxt="", translate=True, icon='NONE',
            icon_value=0):
        PLayout.btn_operator(text, icon, icon_value)

    def template_ID(data, property, new="", open="", unlink=""):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "ID"))

    def template_ID_preview(
            data, property, new="", open="", unlink="", rows=0, cols=0):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "ID Preview"))

    def template_any_ID(
            data, property, type_property, text="", text_ctxt="",
            translate=True):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "Any ID"))

    def template_path_builder(
            data, property, root, text="", text_ctxt="", translate=True):
        PLayout.btn_operator(
            PLayout.prop_name(data, property, "Path Builder"))

    def template_modifier(data):
        PLayout.btn_operator("Modifiers")

    def template_constraint(data):
        PLayout.btn_operator("Constraints")

    def template_preview(
            id, show_buttons=True, parent=None, slot=None, preview_id=""):
        PLayout.btn_operator("Preview")

    def template_curve_mapping(
            data, property, type='NONE', levels=False,
            brush=False, use_negative_slope=False):
        PLayout.btn_operator("Curve Mapping")

    def template_color_ramp(data, property, expand=False):
        PLayout.btn_operator("Color Ramp")

    def template_icon_view(data, property, show_labels=False, scale=5.0):
        PLayout.btn_operator("Icon View")

    def template_histogram(data, property):
        PLayout.btn_operator("Histogram")

    def template_waveform(data, property):
        PLayout.btn_operator("Waveform")

    def template_vectorscope(data, property):
        PLayout.btn_operator("VectorScope")

    def template_layers(
            data, property, used_layers_data, used_layers_property,
            active_layer):
        PLayout.btn_operator("Layers")

    def template_color_picker(
            data, property, value_slider=False, lock=False,
            lock_luminosity=False, cubic=False):
        PLayout.btn_operator("Color Picker")

    def template_palette(data, property, color=False):
        PLayout.btn_operator("Palette")

    def template_image_layers(image, image_user):
        PLayout.btn_operator("Image Layers")

    def template_image(
            data, property, image_user, compact=False, multiview=False):
        PLayout.btn_operator("Image")

    def template_image_settings(image_settings, color_management=False):
        PLayout.btn_operator("Image Settings")

    def template_image_stereo_3d(stereo_3d_format):
        PLayout.btn_operator("Image Stereo 3D")

    def template_image_views(image_settings):
        PLayout.btn_operator("Image Views")

    def template_movieclip(data, property, compact=False):
        PLayout.btn_operator("MovieClip")

    def template_track(data, property):
        PLayout.btn_operator("Track")

    def template_marker(data, property, clip_user, track, compact=False):
        PLayout.btn_operator("Marker")

    def template_movieclip_information(data, property, clip_user):
        PLayout.btn_operator("MovieClip Info")

    def template_list(
            listtype_name, list_id, dataptr, propname, active_dataptr,
            active_propname, item_dyntip_propname="", rows=5, maxrows=5,
            type='DEFAULT', columns=9):
        PLayout.btn_operator("List")

    def template_running_jobs():
        PLayout.btn_operator("Running Jobs")

    def template_operator_search():
        PLayout.btn_operator("Preview")

    def template_header_3D():
        PLayout.btn_operator("Header 3D")

    def template_edit_mode_selection():
        PLayout.btn_operator("Edit Mode Selection")

    def template_reports_banner():
        PLayout.btn_operator("Reports Banner")

    def template_node_link(ntree, node, socket):
        PLayout.btn_operator("Node Link")

    def template_node_view(ntree, node, socket):
        PLayout.btn_operator("Node View")

    def template_texture_user():
        PLayout.btn_operator("Texture User")

    def template_keymap_item_properties(item):
        PLayout.btn_operator("Keymap Item Props")

    def template_component_menu(data, property, name=""):
        PLayout.btn_operator("Component Menu")

    def introspect():
        PLayout.btn_operator("Introspect")

    def template_colorspace_settings(data, property):
        PLayout.btn_operator("Color Space")

    def template_colormanaged_view_settings(data, property):
        PLayout.btn_operator("CMV Settings")

    def template_node_socket(color=(0.0, 0.0, 0.0, 1.0)):
        PLayout.btn_operator("Node Socket")


def panel_type(panel):
    return hidden_panel(panel) or getattr(bpy.types, panel, None)


def panel_label(panel):
    if isinstance(panel, str):
        panel = panel_type(panel)

    if not panel:
        return ""

    label = getattr(panel, "bl_label", None)
    if label:
        return label

    _, _, label = panel.__name__.partition("_PT_")
    if not label:
        label = panel.__name__

    return utitle(label)


class PME_OT_popup_panel_menu(bpy.types.Operator):
    bl_idname = "pme.popup_panel_menu"
    bl_label = "Menu"
    bl_description = "Menu"
    bl_options = {'INTERNAL'}

    panel: bpy.props.StringProperty()

    def draw_popup_panel_menu(self, menu, context):
        layout = menu.layout
        layout.operator("pme.none", text="Move Panel", icon=ic('FORWARD'))

    def execute(self, context):
        context.window_manager.popup_menu(
            self.draw_popup_panel_menu, title=panel_label(self.panel))
        return {'FINISHED'}


def panel(
        pt, frame=True, header=True, expand=None, area=None,
        root=False, poll=True, layout=None,
        **kwargs):
    ctx = bl_context or bpy.context

    if area and area != 'CURRENT':
        bl_context.use_area(area)

    if isinstance(pt, str):
        header_id = pt
        if pt in _hidden_panels:
            pt = _hidden_panels[pt]
        else:
            if not hasattr(bpy.types, pt):
                row = pme.context.layout.row(align=True)
                row.alert = True
                p = row.operator(
                    "pme.message_box", text="Panel not found")
                p.message = "Panel '%s' not found" % pt
                return True
            pt = getattr(bpy.types, pt)
    else:
        header_id = pt.__name__

    panel.active = True
    DBG_PANEL and logh("Panel")
    bl_context.set_context(bpy.context)
    context_class = type(bpy.context)
    for k, v in kwargs.items():
        setattr(context_class, k, v)

    space_data = ctx.space_data
    if space_data:
        space_class = type(space_data)
        setattr(space_class, "use_pin_id", None)
        setattr(space_class, "pin_id", None)

    def restore_data():
        for k in kwargs.keys():
            delattr(context_class, k)

        if space_data:
            delattr(space_class, "use_pin_id")
            delattr(space_class, "pin_id")

        if area and area != 'CURRENT':
            bl_context.restore_area()

        panel.active = False

    try:
        if "tabs_interface" in uprefs().addons:
            import tabs_interface
            tabs_interface.USE_DEFAULT_POLL = True

        if poll and hasattr(pt, "poll") and not pt.poll(ctx):
            restore_data()
            return True

        if "tabs_interface" in uprefs().addons:
            tabs_interface.USE_DEFAULT_POLL = False

    except:
        DBG_PANEL and print_exc()
        restore_data()
        return True

    p = pt(bpy.context.window_manager)
    if root:
        layout = pme.context.layout
    else:
        if layout is None:
            layout = pme.context.layout.box() if frame else \
                pme.context.layout.column()
        else:
            if CTU.is_row(layout):
                layout = layout.column()

    is_collapsed = False
    # item_id = pme.context.item_id()
    # if item_id not in PLayout.idx_map:
    #     PLayout.idx_map[item_id] = set()
    # PLayout.indices = PLayout.idx_map[item_id]

    if header:
        # item_id = pme.context.item_id()
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.alignment = 'LEFT'
        try:
            if expand is not None and pme.context.is_first_draw:
                if expand:
                    if header_id in PME_OT_panel_toggle.collapsed_panels:
                        PME_OT_panel_toggle.collapsed_panels.remove(header_id)
                else:
                    PME_OT_panel_toggle.collapsed_panels.add(header_id)
        except:
            print_exc()

        is_collapsed = header_id in PME_OT_panel_toggle.collapsed_panels
        icon = 'TRIA_RIGHT' if is_collapsed else 'TRIA_DOWN'
        sub.operator(
            PME_OT_panel_toggle.bl_idname, text="",
            icon=ic(icon), emboss=False).panel_id = header_id
        if hasattr(p, "draw_header"):
            p.layout = sub
            if isinstance(p.draw_header, MethodType):
                p.draw_header(ctx)
            else:
                p.draw_header(p, ctx)
        sub.operator(
            PME_OT_panel_toggle.bl_idname, text=panel_label(pt),
            emboss=False).panel_id = header_id
        row.operator(
            PME_OT_panel_toggle.bl_idname, text=" ",
            emboss=False).panel_id = header_id
        # row.operator(
        #     PME_OT_popup_panel_menu.bl_idname, text="",
        #     icon='COLLAPSEMENU', emboss=False)

    if not is_collapsed:
        p.layout = layout if root else layout.column()
        try:
            if hasattr(p, "draw"):
                # if prefs().interactive_panels:
                #     sub = p.layout.row(align=True)
                #     sub.operator(
                #         PME_OT_panel_reset.bl_idname,
                #         text="", icon='FILE_REFRESH'
                #     ).item_id = item_id
                #     sub.operator(
                #         PME_OT_panel_editor_toggle.bl_idname,
                #         text="View" if PLayout.editor else "Edit",
                #     )
                #     sub.operator(
                #       "pme.interactive_panels_toggle",
                #       text="", icon='QUIT',
                #     ).action = 'DISABLE'

                # PLayout.save(pme.context.layout, item_id)
                if isinstance(p.draw, MethodType):
                    p.draw(ctx)
                else:
                    p.draw(p, ctx)
        except:
            DBG_PANEL and print_exc()
        finally:
            pass
            # PLayout.restore()

    restore_data()
    return True


panel.active = False
handle_view = None
handle_props = None


def draw_callback_view():
    if PopupOperator.active:
        return

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == CC.UPREFS:
                area.tag_redraw()


def draw_callback_props():
    pass


def register():
    pme.context.add_global("panel", panel)

    global _prefs_panel_types, _prefs_panel_polls
    bpy_types = bpy.types
    _prefs_panel_types = [
        v for v in dir(bpy_types) if "USERPREF_PT" in v]

    def sorter(tp_name):
        if tp_name == "USERPREF_PT_tabs":
            return -1

        return panel_type_names_sorter(tp_name)

    _prefs_panel_types.sort(key=sorter)
    _prefs_panel_polls = {k: None for k in _prefs_panel_types}

    types = []
    for k in _prefs_panel_types:
        tp = getattr(bpy.types, k, None)
        if not tp:
            continue

        types.append(tp)
        # tp.bl_options = set()
        tp_poll = getattr(tp, "poll", None)
        _prefs_panel_polls[k] = tp_poll
        tp.poll = classmethod(bar_panel_poll(tp_poll))
        bpy.utils.unregister_class(tp)

    for tp in types:
        bpy.utils.register_class(tp)

    global handle_view
    handle_view = bpy.types.SpaceView3D.draw_handler_add(
        draw_callback_view, (), 'WINDOW', 'POST_VIEW')
    # global handle_props
    # handle_props = bpy.types.SpaceProperties.draw_handler_add(
    #     draw_callback_props, (), 'WINDOW', 'POST_VIEW')


def unregister():
    unhide_panels()
    _hidden_panels.clear()

    for panels in _panels.values():
        for panel in panels:
            bpy.utils.unregister_class(panel)

    _panels.clear()

    types = []
    for k in _prefs_panel_types:
        tp = getattr(bpy.types, k, None)
        if not tp:
            continue

        types.append(tp)
        if not _prefs_panel_polls[k]:
            if hasattr(tp, "poll"):
                delattr(tp, "poll")
        else:
            tp.poll = _prefs_panel_polls[k]

        bpy.utils.unregister_class(tp)

    for tp in types:
        bpy.utils.register_class(tp)

    if handle_view:
        bpy.types.SpaceView3D.draw_handler_remove(handle_view, 'WINDOW')
    if handle_props:
        bpy.types.SpaceProperties.draw_handler_remove(handle_props, 'WINDOW')

import bpy
import os
import sys
import marshal
import py_compile
from traceback import format_exc
from errno import ENOENT
from .addon import ADDON_PATH, prefs, print_exc
from . import pme
from .layout_helper import lh, draw_pme_layout, CLayout
from .operators import WM_OT_pme_user_pie_menu_call


class WM_MT_pme:
    bl_label = ""

    def draw(self, context):
        pr = prefs()
        pm = pr.pie_menus[self.bl_label]

        row = self.layout.row()
        lh.column(row, operator_context='INVOKE_DEFAULT')

        for idx, pmi in enumerate(pm.pmis):
            if pmi.mode == 'EMPTY':
                if pmi.text == "":
                    lh.sep()
                elif pmi.text == "spacer":
                    lh.label(" ")
                elif pmi.text == "column":
                    lh.column(row, operator_context='INVOKE_DEFAULT')
                elif pmi.text == "label":
                    text, icon, *_ = pmi.parse()
                    lh.label(text, icon)
                continue

            WM_OT_pme_user_pie_menu_call._draw_item(pr, pm, pmi, idx)


pme_menu_classes = {}


def get_pme_menu_class(name):
    if name not in pme_menu_classes:
        class_name = "PME_MT_menu_%d" % len(pme_menu_classes)
        pme_menu_classes[name] = type(
            class_name,
            (WM_MT_pme, bpy.types.Menu), {
                'bl_label': name,
            })
        bpy.utils.register_class(pme_menu_classes[name])

    return pme_menu_classes[name].__name__


def accordion(layout, data, prop):
    ret = None
    enum_items = data.rna_type.properties[prop].enum_items
    value = getattr(data, prop)
    for item in enum_items:
        layout.prop_enum(data, prop, item.identifier)
        if item.identifier == value:
            ret = layout.box().column()
    return ret


def header_menu(areas):
    ctx = bpy.context

    def draw_menus(area, menu_types, layout):
        if area == "CLIP":
            sd = None
            if ctx.space_data and ctx.space_data.type == 'CLIP_EDITOR':
                sd = ctx.space_data
            else:
                for screen in bpy.data.screens:
                    for a in screen.areas:
                        if a.type == 'CLIP_EDITOR':
                            sd = a.spaces[0]
                            break
                    if sd:
                        break

            if not sd:
                menu_type = "None"
            elif sd.mode == 'TRACKING':
                menu_type = "CLIP_MT_tracking_editor_menus"
            elif sd.mode == 'MASK':
                menu_type = "CLIP_MT_masking_editor_menus"

        elif area in menu_types:
            menu_type = menu_types[area]

        else:
            menu_type = area + "_MT_editor_menus"

        tp = getattr(bpy.types, menu_type, None)
        if tp:
            row = layout.row()
            row.alignment = 'CENTER'
            pm = pme.context.pm
            prop = pme.props.parse(pm.data)
            if pm.mode != 'DIALOG' or not prop.pd_panel and not prop.pd_box:
                row = row.box().row()

            def get_space_data_attribute(self, attr):
                if attr == "space_data":
                    return sd
                del bpy.types.Context.__getattribute__
                return getattr(self, attr)

            bpy.types.Context.__getattribute__ = get_space_data_attribute

            if hasattr(tp, "draw_collapsible"):
                row.emboss = 'PULLDOWN_MENU'
                tp.draw_collapsible(ctx, row)
            else:
                CLayout.use_mouse_over_open = True
                tp.draw_menus(row, ctx)
                CLayout.use_mouse_over_open = None

    if not isinstance(areas, list):
        areas = [areas]

    menu_types = dict(
        TIMELINE="TIME_MT_editor_menus",
        IMAGE="MASK_MT_editor_menus",
        SEQUENCE="SEQUENCER_MT_editor_menus",
    )

    try:
        col = pme.context.layout.column()
        for a in areas:
            if not a or a == 'CURRENT':
                a = ctx.area.type
            a = a.replace("_EDITOR", "").replace("_", "")

            draw_menus(a, menu_types, col)
    except:
        print_exc()

    return True


def execute_script(path, **kwargs):
    if not os.path.isabs(path):
        path = os.path.join(ADDON_PATH, path)
    path = os.path.normpath(path)

    if not os.path.isfile(path):
        raise OSError(ENOENT, os.strerror(ENOENT), path)

    exec_globals = pme.context.gen_globals()
    exec_globals["kwargs"] = kwargs
    exec_globals["__file__"] = path

    pr = prefs()
    if pr.cache_scripts:
        name = os.path.basename(path)
        name, _, _ = name.rpartition(".")
        cname = name + ".cpython-%d%d.pyc" % (
            sys.version_info[0], sys.version_info[1])
        cpath = os.path.join(os.path.dirname(path), "__pycache__", cname)

        try:
            if os.path.isfile(cpath):
                cmod_time = os.stat(cpath).st_mtime
                mod_time = os.stat(path).st_mtime
                if mod_time > cmod_time:
                    cpath = py_compile.compile(path)
            else:
                cpath = py_compile.compile(path)

            with open(cpath, "rb") as f:
                if sys.version_info >= (3, 7, 0):
                    f.read(16)
                else:
                    f.read(12)

                exec(marshal.load(f), exec_globals)
        except:
            if pr.debug_mode:
                s = format_exc()
                print(s)
                if pme.context.exec_operator:
                    pme.context.exec_operator.report({'ERROR'}, s)

    else:
        try:
            with open(path) as f:
                exec(f.read(), exec_globals)
        except:
            if pr.debug_mode:
                s = format_exc()
                print(s)
                if pme.context.exec_operator:
                    pme.context.exec_operator.report({'ERROR'}, s)

    return exec_globals.get("return_value", True)


def draw_menu(name, frame=False, dx=0, dy=0, layout=None):
    pr = prefs()
    if name in pr.pie_menus:
        lh.save()
        if layout:
            lh.lt(layout)

        orow, ocol, drow, dcol = None, None, None, None

        if dx != 0 or dy != 0:
            if dx != 0:
                orow = lh.row()
                if dx > 0:
                    drow = orow.row(align=True)
                    drow.separator()
                    drow.scale_x = dx

            if dy != 0:
                ocol = lh.column()
                if dy < 0:
                    dcol = ocol.column(align=True)
                    dcol.separator()
                    dcol.scale_y = -dy

        if frame:
            lh.box()

        lh.column()

        draw_pme_layout(
            pr.pie_menus[name], lh.layout,
            WM_OT_pme_user_pie_menu_call._draw_item)

        if dx < 0:
            drow = orow.row(align=True)
            drow.separator()
            drow.scale_x = -dx

        if dy > 0:
            dcol = ocol.column(align=True)
            dcol.separator()
            dcol.scale_y = dy

        lh.restore()
        return True
    return False


def open_menu(name, slot=None, **kwargs):
    pr = prefs()
    if name in pr.pie_menus:
        invoke_mode = 'RELEASE'
        if pme.context.pm and pme.context.pm.mode == 'SCRIPT':
            invoke_mode = 'HOTKEY'

        pme.context.exec_user_locals.update(kwargs)

        if slot is None:
            slot = -1
        elif isinstance(slot, str):
            # pmi_name = slot
            slot = pr.pie_menus[name].pmis.find(slot)
            if slot == -1:
                return False
            # pm = pr.pie_menus[name]
            # for i, pmi in enumerate(pm.pmis):
            #     if pmi.name == pmi_name:
            #         slot = i
            #         break

        bpy.ops.wm.pme_user_pie_menu_call(
            'INVOKE_DEFAULT', pie_menu_name=name,
            # invoke_mode=pme.context.last_operator.invoke_mode)
            invoke_mode=invoke_mode,
            slot=slot)

        pme.context.exec_user_locals.clear()
        return True

    return False


def toggle_menu(name, value=None):
    pr = prefs()
    if name in pr.pie_menus:
        pm = pr.pie_menus[name]
        if value is None:
            value = not pm.enabled
        pm.enabled = value
        return True
    return False


def register():
    pme.context.add_global("header_menu", header_menu)
    pme.context.add_global("draw_menu", draw_menu)
    pme.context.add_global("open_menu", open_menu)
    pme.context.add_global("execute_script", execute_script)
    pme.context.add_global("toggle_menu", toggle_menu)


def unregister():
    for cl in pme_menu_classes.values():
        bpy.utils.unregister_class(cl)

    pme_menu_classes.clear()

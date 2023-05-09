import bpy
from . import constants as CC
from . import keymap_helper as KH
from .addon import prefs, temp_prefs, ic_rb, ic_cb, ic_eye, ic_fb, ic
from .constants import MAX_STR_LEN, EMODE_ITEMS
from .debug_utils import *
from .bl_utils import (
    find_context, re_operator, re_prop, re_prop_path, bp,
    message_box, uname, ConfirmBoxHandler, PME_OT_message_box
)
from .collection_utils import (
    sort_collection, AddItemOperator, MoveItemOperator, RemoveItemOperator,
)
from .ui import (
    tag_redraw, shorten_str, gen_prop_name, gen_op_name, find_enum_args,
    utitle
)
from . import utils as U
from . import screen_utils as SU
from .ui_utils import get_pme_menu_class, toggle_menu, pme_menu_classes
from .layout_helper import lh, operator, split, draw_pme_layout, L_SEP, L_LABEL
from .property_utils import to_py_value
from .types import Tag, PMItem, PMIItem
from . import keymap_helper
from . import pme
from . import operator_utils
from .operators import (
    popup_dialog_pie,
    PME_OT_exec,
    PME_OT_docs,
    PME_OT_preview,
    PME_OT_debug_mode_toggle,
    PME_OT_pm_hotkey_remove,
    WM_OT_pm_select,
    PME_OT_pm_search_and_select,
    PME_OT_script_open,
    WM_OT_pme_user_pie_menu_call,
)

EXTENDED_PANELS = {}


def gen_header_draw(pm_name):
    def _draw(self, context):
        is_right_region = context.region.alignment == 'RIGHT'
        _, is_right_pm, _ = U.extract_str_flags_b(
            pm_name, CC.F_RIGHT, CC.F_PRE)
        if is_right_region and is_right_pm or \
                not is_right_region and not is_right_pm:
            draw_pme_layout(
                prefs().pie_menus[pm_name], self.layout.column(align=True),
                WM_OT_pme_user_pie_menu_call._draw_item,
                icon_btn_scale_x=1)

    return _draw


def gen_menu_draw(pm_name):
    def _draw(self, context):
        WM_OT_pme_user_pie_menu_call.draw_rm(
            prefs().pie_menus[pm_name], self.layout)

    return _draw


def gen_panel_draw(pm_name):
    def _draw(self, context):
        draw_pme_layout(
            prefs().pie_menus[pm_name], self.layout.column(align=True),
            WM_OT_pme_user_pie_menu_call._draw_item)

    return _draw


def extend_panel(pm):
    if pm.name in EXTENDED_PANELS:
        return

    tp_name, right, pre = U.extract_str_flags_b(pm.name, CC.F_RIGHT, CC.F_PRE)

    if tp_name.startswith("PME_PT") or \
            tp_name.startswith("PME_MT") or \
            tp_name.startswith("PME_HT"):
        return

    tp = getattr(bpy.types, tp_name, None)
    if tp and issubclass(
            tp, (bpy.types.Panel, bpy.types.Menu, bpy.types.Header)):
        if '_HT_' in pm.name:
            EXTENDED_PANELS[pm.name] = gen_header_draw(pm.name)
        elif '_MT_' in pm.name:
            EXTENDED_PANELS[pm.name] = gen_menu_draw(pm.name)
        else:
            EXTENDED_PANELS[pm.name] = gen_panel_draw(pm.name)
        f = tp.prepend if pre else tp.append
        f(EXTENDED_PANELS[pm.name])
        SU.redraw_screen()


def unextend_panel(pm):
    if pm.name not in EXTENDED_PANELS:
        return

    tp_name, _, _ = U.extract_str_flags_b(pm.name, CC.F_RIGHT, CC.F_PRE)

    tp = getattr(bpy.types, tp_name, None)
    if tp:
        tp.remove(EXTENDED_PANELS[pm.name])
        del EXTENDED_PANELS[pm.name]
        SU.redraw_screen()


class PME_OT_tags_filter(bpy.types.Operator):
    bl_idname = "pme.tags_filter"
    bl_label = "Filter by Tag"
    bl_description = "Filter by tag"
    bl_options = {'INTERNAL'}

    ask: bpy.props.BoolProperty(default=True, options={'SKIP_SAVE'})
    tag: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def draw_menu(self, menu, context):
        pr = prefs()
        tpr = temp_prefs()
        layout = menu.layout
        operator(
            layout, self.bl_idname, "Disable",
            icon=ic_rb(not pr.tag_filter),
            tag="", ask=False)
        layout.separator()

        for t in tpr.tags:
            operator(
                layout, self.bl_idname, t.name,
                icon=ic_rb(t.name == pr.tag_filter),
                tag=t.name, ask=False)

        operator(
            layout, self.bl_idname, CC.UNTAGGED,
            icon=ic_rb(pr.tag_filter == CC.UNTAGGED),
            tag=CC.UNTAGGED, ask=False)

    def execute(self, context):
        if self.ask:
            context.window_manager.popup_menu(
                self.draw_menu, title=self.bl_label)
        else:
            pr = prefs()
            pr.tag_filter = self.tag
            Tag.filter()
            pr.update_tree()
            tag_redraw()

        return {'FINISHED'}


class PME_OT_tags(bpy.types.Operator):
    bl_idname = "pme.tags"
    bl_label = ""
    bl_description = "Manage tags"
    bl_options = {'INTERNAL'}
    bl_property = "tag"

    idx: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})
    action: bpy.props.EnumProperty(
        items=(
            ('MENU', "Menu", ""),
            ('TAG', "Tag", ""),
            ('UNTAG', "Untag", ""),
            ('ADD', "Add", ""),
            ('REMOVE', "Remove", ""),
            ('RENAME', "Rename", ""),
        ),
        options={'SKIP_SAVE'})
    tag: bpy.props.StringProperty(maxlen=50, options={'SKIP_SAVE'})
    group: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def draw_menu(self, menu, context):
        pr = prefs()
        tpr = temp_prefs()
        pm = pr.selected_pm
        layout = menu.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        i = 0
        for i, tag in enumerate(tpr.tags):
            icon = CC.ICON_OFF
            action = 'TAG'
            if pm.has_tag(tag.name):
                icon = CC.ICON_ON
                action = 'UNTAG'
            if self.action != 'MENU':
                action = self.action
                icon = 'NONE'
            operator(
                layout, PME_OT_tags.bl_idname, tag.name, icon,
                idx=i, action=action, group=self.group)

        if self.action not in {'MENU', 'TAG'}:
            return

        if tpr.tags:
            layout.separator()

        operator(
            layout, PME_OT_tags.bl_idname, "Assign New Tag", 'ZOOMIN',
            action='ADD', group=self.group)

        if self.action != 'MENU':
            return

        if not tpr.tags:
            return

        operator(
            layout, PME_OT_tags.bl_idname, "Rename Tag",
            'OUTLINER_DATA_FONT',
            action='RENAME')
        operator(
            layout, PME_OT_tags.bl_idname, "Remove Tag", 'ZOOMOUT',
            action='REMOVE')

    def draw(self, context):
        self.layout.prop(self, "tag", text="", icon=ic('SOLO_OFF'))

    def execute(self, context):
        pr = prefs()
        tpr = temp_prefs()
        pm = pr.selected_pm

        self.tag = self.tag.replace(",", "").strip()
        if not self.tag:
            return {'CANCELLED'}
        if self.tag == CC.UNTAGGED:
            self.tag += ".001"

        if self.action == 'ADD':
            tag = tpr.tags.add()
            tag.name = uname(tpr.tags, self.tag)
            if self.group:
                for v in pr.pie_menus:
                    if v.enabled:
                        v.add_tag(tag.name)
            else:
                pm.add_tag(tag.name)
            sort_collection(tpr.tags, lambda t: t.name)

        elif self.action == 'RENAME':
            tag = tpr.tags[self.idx]
            if tag.name == self.tag:
                return {'CANCELLED'}

            self.tag = uname(tpr.tags, self.tag)
            for pm in pr.pie_menus:
                if pm.has_tag(tag.name):
                    pm.remove_tag(tag.name)
                    pm.add_tag(self.tag)
            tag.name = self.tag

        Tag.filter()
        pr.update_tree()
        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        pr = prefs()
        tpr = temp_prefs()
        pm = pr.selected_pm

        tag = None
        if self.idx >= 0:
            tag = tpr.tags[self.idx]

        if self.action == 'MENU':
            context.window_manager.popup_menu(
                self.draw_menu, title=pm.name, icon=pm.ed.icon)

        elif self.action == 'ADD':
            self.tag = "Tag"
            return context.window_manager.invoke_props_dialog(self)

        elif self.action == 'RENAME':
            if self.idx == -1:
                context.window_manager.popup_menu(
                    self.draw_menu, title="Rename Tag",
                    icon='OUTLINER_DATA_FONT')
            else:
                self.tag = tag.name
                return context.window_manager.invoke_props_dialog(self)

        elif self.action == 'REMOVE':
            if self.idx == -1:
                context.window_manager.popup_menu(
                    self.draw_menu, title="Remove Tag", icon='ZOOMOUT')
            else:
                for pm in pr.pie_menus:
                    pm.remove_tag(tag.name)
                tpr.tags.remove(self.idx)

        elif self.action == 'TAG':
            if tag is None:
                context.window_manager.popup_menu(
                    self.draw_menu, title="Tag Enabled Menus",
                    icon='SOLO_ON')
            else:
                if self.group:
                    for v in pr.pie_menus:
                        if v.enabled:
                            v.add_tag(tag.name)
                else:
                    pm.add_tag(tag.name)

        elif self.action == 'UNTAG':
            if tag is None:
                context.window_manager.popup_menu(
                    self.draw_menu, title="Untag Enabled Menus",
                    icon='SOLO_OFF')
            else:
                if self.group:
                    for v in pr.pie_menus:
                        if v.enabled:
                            v.remove_tag(tag.name)
                else:
                    pm.remove_tag(tag.name)

        Tag.filter()
        pr.update_tree()
        tag_redraw()
        return {'FINISHED'}


class WM_OT_pmi_type_select(bpy.types.Operator):
    bl_idname = "wm.pmi_type_select"
    bl_label = ""
    bl_description = "Select type of the item"
    bl_options = {'INTERNAL'}

    pm_item: bpy.props.IntProperty()
    text: bpy.props.StringProperty()
    mode: bpy.props.StringProperty()

    def _draw(self, menu, context):
        pm = prefs().selected_pm
        lh.lt(menu.layout)

        lh.operator(
            WM_OT_pmi_type_select.bl_idname, "Command",
            pm_item=self.pm_item,
            text=self.text,
            mode='COMMAND')

        if self.mode == 'PROP_ASK':
            lh.operator(
                WM_OT_pmi_type_select.bl_idname, "Property",
                pm_item=self.pm_item,
                text=self.text,
                mode='PROP')

            mo = re_prop.search(self.text)
            prop_path = mo.group(1) + mo.group(2)
            obj_path, _, prop_name = prop_path.rpartition(".")
            prop = None
            try:
                tp = type(eval(obj_path, pme.context.globals))
                prop = tp.bl_rna.properties[prop_name]
            except:
                pass

            if prop and prop.type == 'ENUM':
                lh.operator(
                    WM_OT_pmi_type_select.bl_idname, "Custom (Menu)",
                    pm_item=self.pm_item,
                    text=self.text,
                    mode='PROP_ENUM_MENU')

                lh.operator(
                    WM_OT_pmi_type_select.bl_idname,
                    "Custom (Expand Horizontally)",
                    pm_item=self.pm_item,
                    text=self.text,
                    mode='PROP_ENUM_EXPAND_H')

                lh.operator(
                    WM_OT_pmi_type_select.bl_idname,
                    "Custom (Expand Vertically)",
                    pm_item=self.pm_item,
                    text=self.text,
                    mode='PROP_ENUM_EXPAND_V')

                # if pm.mode != 'PMENU':
                #     lh.operator(
                #         WM_OT_pmi_type_select.bl_idname, "Custom (List)",
                #         pm_item=self.pm_item,
                #         text=self.text,
                #         mode='PROP_ENUM')

        if self.mode == 'ENUM_ASK':
            lh.operator(
                WM_OT_pmi_type_select.bl_idname, "Custom (Menu)",
                pm_item=self.pm_item,
                text=self.text,
                mode='ENUM_MENU')

            if pm.mode != 'PMENU':
                lh.operator(
                    WM_OT_pmi_type_select.bl_idname, "Custom (List)",
                    pm_item=self.pm_item,
                    text=self.text,
                    mode='ENUM')

    def execute(self, context):
        if 'ASK' in self.mode:
            bpy.context.window_manager.popup_menu(
                self._draw, title="Select Type")
        else:
            pm = prefs().selected_pm
            pmi = pm.pmis[self.pm_item]

            if self.mode == 'COMMAND':
                pmi.mode = 'COMMAND'
                pmi.text = self.text
                mo = re_operator.search(self.text)
                if mo:
                    pmi.name = gen_op_name(mo)
                else:
                    mo = re_prop.search(self.text)
                    pmi.name, icon = gen_prop_name(mo)
                    if icon:
                        pmi.icon = icon

            elif self.mode == 'PROP':
                pmi.mode = 'PROP'
                mo = re_prop.search(self.text)
                pmi.text = mo.group(1) + mo.group(2)
                if pmi.text[-1] == "]":
                    pmi.text, _, _ = pmi.text.rpartition("[")
                pmi.name, icon = gen_prop_name(mo, True)
                if icon:
                    pmi.icon = icon

                if pm.mode == 'PMENU':
                    try:
                        obj, _, prop_name = pmi.text.rpartition(".")
                        prop = type(
                            eval(obj, pme.context.globals)
                        ).bl_rna.properties[prop_name]
                        if prop.type != 'BOOLEAN' or len(
                                prop.default_array) > 1:
                            text = "slot"
                            if prop.type == 'ENUM':
                                text = "''"
                            pmi.mode = 'CUSTOM'
                            pmi.text = (
                                "L.column().prop("
                                "%s, '%s', text=%s, icon=icon, "
                                "icon_value=icon_value)") % (
                                obj, prop_name, text)
                    except:
                        pass

            # elif self.mode == 'PROP_ENUM':
            #     pmi.mode = 'CUSTOM'
            #     mo = re_prop.search(self.text)
            #     prop_path = mo.group(1) + mo.group(2)
            #     obj_path, _, prop_name = prop_path.rpartition(".")
            #     pmi.text = (
            #         "L.props_enum(%s, '%s')"
            #     ) % (obj_path, prop_name)
            #     pmi.name, icon = gen_prop_name(mo, True)
            #     if icon:
            #         pmi.icon = icon

            elif self.mode == 'PROP_ENUM_MENU':
                pmi.mode = 'CUSTOM'
                mo = re_prop.search(self.text)
                prop_path = mo.group(1) + mo.group(2)
                obj_path, _, prop_name = prop_path.rpartition(".")
                pmi.text = (
                    "L.prop_menu_enum(%s, '%s', text=text, icon=icon)"
                ) % (obj_path, prop_name)
                pmi.name, icon = gen_prop_name(mo, True)
                if icon:
                    pmi.icon = icon

            elif 'PROP_ENUM_EXPAND' in self.mode:
                pmi.mode = 'CUSTOM'
                mo = re_prop.search(self.text)
                prop_path = mo.group(1) + mo.group(2)
                obj_path, _, prop_name = prop_path.rpartition(".")
                lt = "row" if self.mode == 'PROP_ENUM_EXPAND_H' else "column"
                pmi.text = (
                    "L.%s(align=True).prop(%s, '%s', expand=True)"
                ) % (lt, obj_path, prop_name)
                pmi.name, icon = gen_prop_name(mo, True)
                if icon:
                    pmi.icon = icon

            elif self.mode == 'ENUM':
                pmi.mode = 'CUSTOM'
                mo = re_operator.search(self.text)
                enum_args = find_enum_args(mo)
                pmi.text = \
                    "L.operator_enum(\"%s\", \"%s\")" % (
                        mo.group(1), enum_args[0])
                pmi.name = gen_op_name(mo)

            elif self.mode == 'ENUM_MENU':
                pmi.mode = 'CUSTOM'
                mo = re_operator.search(self.text)
                enum_args = find_enum_args(mo)
                pmi.text = (
                    "L.operator_menu_enum(\"%s\", \"%s\", "
                    "text=text, icon=icon)"
                ) % (mo.group(1), enum_args[0])
                pmi.name = gen_op_name(mo)

            tag_redraw()

        prefs().update_tree()

        return {'CANCELLED'}


def _edit_pmi(operator, text, event):
    pr = prefs()
    pm = pr.selected_pm
    pmi = None

    if not text and operator.text:
        text = operator.text

    if not text:
        message_box(CC.I_CMD)
        return

    if operator.new_script:
        pm = pr.add_pm('SCRIPT')
        pmi = pm.pmis[0]

    if not operator.add:
        if pm.mode == 'DIALOG' and event.ctrl:
            pm.pmis.add()
            if not event.shift:
                operator.pm_item += 1

            pm.pmis.move(len(pm.pmis) - 1, operator.pm_item)
            pmi = pm.pmis[operator.pm_item]
            pmi.mode = 'COMMAND'

        else:
            pmi = pm.pmis[operator.pm_item]
    else:
        if pm.mode in {'RMENU', 'SCRIPT', 'MACRO', 'MODAL'}:
            pm.pmis.add()
            if operator.pm_item != -1:
                pm.pmis.move(len(pm.pmis) - 1, operator.pm_item)
            pmi = pm.pmis[operator.pm_item]
            pmi.mode = 'COMMAND'

        elif pm.mode == 'DIALOG':
            pmi = pm.ed.add_pd_row(pm)

    if not pmi:
        return

    if operator.mode:
        pmi.name = operator.name
        pmi.mode = operator.mode
        pmi.text = operator.text

    else:
        lines = text.split("\n")
        if len(lines) > 1:
            filtered = []
            for line in lines:
                if re_prop.search(line) or re_operator.search(line):
                    filtered.append(line)
            lines = filtered

        len_lines = len(lines)
        if len_lines == 0:
            message_box(CC.I_CMD)
        elif len_lines > 1:
            pmi.mode = 'COMMAND'
            pmi.text = "; ".join(lines)
            pmi.name = shorten_str(pmi.text)
        else:
            parsed = False
            mo = re_operator.search(lines[0])
            if mo:
                parsed = True
                if 'CUSTOM' in pm.ed.supported_slot_modes and find_enum_args(
                        mo):
                    bpy.ops.wm.pmi_type_select(
                        pm_item=operator.pm_item,
                        text=lines[0], mode="ENUM_ASK")
                    return

                else:
                    name = gen_op_name(mo)
                    pmi.name = name
                    pmi.mode = 'COMMAND'
                    pmi.text = lines[0]

            mo = not parsed and re_prop.search(lines[0])
            if mo:
                parsed = True
                if 'PROP' in pm.ed.supported_slot_modes and mo.group(4):
                    bpy.ops.wm.pmi_type_select(
                        pm_item=operator.pm_item,
                        text=lines[0], mode="PROP_ASK")
                    return
                else:
                    pmi.name, icon = gen_prop_name(mo)
                    if icon:
                        pmi.icon = icon
                    pmi.mode = 'COMMAND'
                    pmi.text = lines[0]

            mo = not parsed and re_prop_path.search(lines[0])
            if mo:
                if 'PROP' in pm.ed.supported_slot_modes:
                    parsed = True
                    pmi.name, icon = gen_prop_name(mo, True)
                    if icon:
                        pmi.icon = icon
                    pmi.mode = 'PROP'
                    pmi.text = lines[0]

            if not parsed:
                message_box(CC.I_CMD)

    # if pm.mode == 'MACRO':
    #     update_macro(pm)
    pm.ed.on_pmi_edit(pm, pmi)

    pr.update_tree()


class WM_OT_pmi_edit(bpy.types.Operator):
    bl_idname = "wm.pmi_edit"
    bl_label = ""
    bl_description = "Use selected actions"
    bl_options = {'INTERNAL'}

    pm_item: bpy.props.IntProperty()
    auto: bpy.props.BoolProperty()
    add: bpy.props.BoolProperty()
    new_script: bpy.props.BoolProperty()
    mode: bpy.props.StringProperty(options={'SKIP_SAVE'})
    text: bpy.props.StringProperty(options={'SKIP_SAVE'})
    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        if self.text:
            text = self.text

        else:
            bpy.ops.info.report_copy()
            text = context.window_manager.clipboard
            if text:
                bpy.ops.info.select_all(action='DESELECT')

            text = text.strip("\n")

            if len(text) > MAX_STR_LEN:
                message_box(CC.W_PMI_LONG_CMD)
                return {'CANCELLED'}

        _edit_pmi(self, text, event)

        return {'CANCELLED'}


class WM_OT_pmi_edit_clipboard(bpy.types.Operator):
    bl_idname = "wm.pmi_edit_clipboard"
    bl_label = ""
    bl_description = ""
    bl_options = {'INTERNAL'}

    pm_item: bpy.props.IntProperty()
    auto: bpy.props.BoolProperty()
    add: bpy.props.BoolProperty()
    new_script: bpy.props.BoolProperty()
    mode: bpy.props.StringProperty(options={'SKIP_SAVE'})
    text: bpy.props.StringProperty(options={'SKIP_SAVE'})
    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        text = context.window_manager.clipboard
        text = text.strip("\n")

        if len(text) > MAX_STR_LEN:
            message_box(CC.W_PMI_LONG_CMD)
            return {'CANCELLED'}

        _edit_pmi(self, text, event)

        return {'CANCELLED'}


class WM_OT_pmi_edit_auto(bpy.types.Operator):
    bl_idname = "wm.pmi_edit_auto"
    bl_label = ""
    bl_description = "Use previous action"
    bl_options = {'INTERNAL'}

    ignored_operators = {
        "bpy.ops.pme.pm_edit",
        "bpy.ops.wm.pme_none",
        "bpy.ops.pme.none",
        "bpy.ops.info.reports_display_update",
        "bpy.ops.info.select_all",
        "bpy.ops.info.report_copy",
        "bpy.ops.view3d.smoothview",
    }

    pm_item: bpy.props.IntProperty()
    add: bpy.props.BoolProperty()
    new_script: bpy.props.BoolProperty()
    mode: bpy.props.StringProperty(options={'SKIP_SAVE'})
    text: bpy.props.StringProperty(options={'SKIP_SAVE'})
    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        ctx = find_context('INFO')
        area_type = not ctx and context.area.type
        args = []
        if ctx:
            args.append(ctx)
        else:
            context.area.type = 'INFO'

        bpy.ops.wm.pme_none()
        bpy.ops.info.select_all(*args, action='SELECT')
        bpy.ops.info.report_copy(*args)
        text = context.window_manager.clipboard

        idx2 = len(text)

        while True:
            idx2 = text.rfind("\n", 0, idx2)
            if idx2 == -1:
                text = ""
                break

            idx1 = text.rfind("\n", 0, idx2 - 1)
            line = text[idx1 + 1:idx2]
            op = line[0:line.find("(")]
            if line.startswith("Debug mode"):
                continue
            if op not in self.ignored_operators:
                text = line
                break

        bpy.ops.info.select_all(*args, action='DESELECT')

        text = text.strip("\n")

        _edit_pmi(self, text, event)

        if area_type:
            context.area.type = area_type

        return {'CANCELLED'}


class PME_MT_select_menu(bpy.types.Menu):
    bl_label = "Select Menu"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_DEFAULT'

        operator(
            layout, WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)

        operator(
            layout, PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')


class PME_MT_pm_new(bpy.types.Menu):
    bl_label = "New"

    def draw_items(self, layout):
        lh.lt(layout)

        for id, name, icon in CC.ED_DATA:
            lh.operator(PME_OT_pm_add.bl_idname, name, icon, mode=id)

    def draw(self, context):
        self.draw_items(self.layout)


class PME_OT_pm_add(bpy.types.Operator):
    bl_idname = "wm.pm_add"
    bl_label = ""
    bl_description = "Add an item"
    bl_options = {'INTERNAL'}

    mode: bpy.props.StringProperty()
    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def _draw(self, menu, context):
        PME_MT_pm_new.draw_items(self, menu.layout)

    def execute(self, context):
        if not self.mode:
            context.window_manager.popup_menu(
                self._draw, title=PME_OT_pm_add.bl_description)
        else:
            pr = prefs()
            pr.add_pm(self.mode, self.name or None)
            pr.update_tree()
            tag_redraw()

        return {'CANCELLED'}


class PME_OT_pm_edit(bpy.types.Operator):
    bl_idname = "pme.pm_edit"
    bl_label = "Edit Menu (PME)"
    bl_description = "Edit the menu"

    auto: bpy.props.BoolProperty(default=True, options={'SKIP_SAVE'})
    clipboard: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    mode: bpy.props.StringProperty(options={'SKIP_SAVE'})
    text: bpy.props.StringProperty(options={'SKIP_SAVE'})
    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def _draw_pm(self, menu, context):
        pm = prefs().selected_pm

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        for idx, pmi in enumerate(pm.pmis):
            text, icon, *_ = pmi.parse()
            if pmi.mode == 'EMPTY':
                text = ". . ."

            lh.operator(
                self.op_bl_idname, text, CC.ARROW_ICONS[idx], pm_item=idx,
                mode=self.mode, text=self.text, name=self.name,
                add=False, new_script=False)

        lh.sep()

        # lh.operator(
        #     self.op_bl_idname, "New Stack Key", 'MOD_SKIN',
        #     pm_item=-1, add=False, new_script=True)
        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)

        lh.operator(PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')

    def _draw_rm(self, menu, context):
        pm = prefs().selected_pm

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')
        row = lh.row()
        lh.column(row)
        lh.label(pm.name, icon='MOD_BOOLEAN')
        # lh.operator(
        #     self.op_bl_idname, "New Stack Key", 'MOD_SKIN',
        #     pm_item=-1, add=False, new_script=True)
        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)
        lh.operator(PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')
        lh.sep()

        idx = -1
        for pmi in pm.pmis:
            idx += 1
            name = pmi.name
            icon = pmi.parse_icon()

            if pmi.mode == 'EMPTY':
                if pmi.text == "column":
                    lh.operator(
                        self.op_bl_idname, "Add Item", 'ZOOMIN',
                        pm_item=idx,
                        mode=self.mode, text=self.text, name=self.name,
                        add=True, new_script=False)
                    lh.column(row)
                    lh.label(" ")
                    lh.label(" ")
                    lh.label(" ")
                    lh.sep()

                elif pmi.text == "":
                    lh.sep()

                elif pmi.text == "spacer":
                    lh.label(" ")

                elif pmi.text == "label":
                    lh.label(name, icon=icon)

                continue

            lh.operator(
                self.op_bl_idname, name, icon, pm_item=idx,
                mode=self.mode, text=self.text, name=self.name,
                add=False, new_script=False)

        lh.operator(
            self.op_bl_idname, "Add Item", 'ZOOMIN',
            pm_item=-1, mode=self.mode, text=self.text, name=self.name,
            add=True, new_script=False)

    def _draw_debug(self, menu, context):
        lh.lt(menu.layout)
        lh.operator(PME_OT_debug_mode_toggle.bl_idname, "Enable Debug Mode")

    def _draw_pd(self, menu, context):
        pr = prefs()
        pm = pr.selected_pm

        layout = menu.layout.menu_pie()
        layout.separator()
        layout.separator()
        column = layout.column(align=True)
        row = column.box().row(align=True)
        row.label(text=pm.name, icon=ic(pm.ed.icon))
        sub = row.row(align=True)
        sub.alignment = 'LEFT'
        operator(
            sub, PME_OT_message_box.bl_idname, emboss=False,
            title="Hotkeys", icon=ic('INFO'),
            message="Ctrl+LMB - Add Button to the Right\n"
            "Ctrl+Shift+LMB - Add Button to the Left")
        sub.menu("PME_MT_select_menu", text="", icon=ic('COLLAPSEMENU'))

        col = column.box().column(align=True)
        lh.lt(col, operator_context='INVOKE_DEFAULT')

        def draw_pmi(pr, pm, pmi, idx):
            text, icon, _, icon_only, hidden, _ = pmi.parse_edit()

            lh.operator(
                self.op_bl_idname, text, icon,
                pm_item=idx, mode=self.mode, text=self.text, name=self.name,
                add=False, new_script=False)

        draw_pme_layout(pm, col, draw_pmi)

        operator(
            column, self.op_bl_idname, "Add New Row", 'ZOOMIN',
            pm_item=-1, mode=self.mode, name=self.name,
            add=True, new_script=False).text = self.text

    def _draw_script(self, menu, context):
        pm = prefs().selected_pm

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        for idx, pmi in enumerate(pm.pmis):
            text, *_ = pmi.parse()
            lh.operator(
                self.op_bl_idname, text, 'MOD_SKIN', pm_item=idx,
                mode=self.mode, text=self.text, name=self.name,
                add=False, new_script=False)

        lh.operator(
            self.op_bl_idname, "New Command", 'ZOOMIN',
            pm_item=-1, mode=self.mode, text=self.text, name=self.name,
            add=True, new_script=False)

        lh.sep()

        # lh.operator(
        #     self.op_bl_idname, "New Stack Key", 'MOD_SKIN',
        #     pm_item=-1, add=False, new_script=True)
        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)

        lh.operator(PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')

    def _draw_sticky(self, menu, context):
        pm = prefs().selected_pm

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        for idx, pmi in enumerate(pm.pmis):
            text, *_ = pmi.parse()
            lh.operator(
                self.op_bl_idname, text,
                'MESH_CIRCLE' if idx == 0 else 'MESH_UVSPHERE',
                pm_item=idx, mode=self.mode, text=self.text, name=self.name,
                add=False, new_script=False)

        lh.sep()

        # lh.operator(
        #     self.op_bl_idname, "New Stack Key", 'MOD_SKIN',
        #     pm_item=-1, add=False, new_script=True)
        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)

        lh.operator(PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')

    def _draw_panel(self, menu, context):
        lh.lt(menu.layout)

        # lh.operator(
        #     self.op_bl_idname, "New Stack Key", 'MOD_SKIN',
        #     pm_item=-1, add=False, new_script=True)
        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)

        lh.operator(PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        if context.area and context.area.type == 'INFO':
            self.auto = False

        pr = prefs()
        if len(pr.pie_menus) == 0:
            bpy.ops.wm.pm_select(pm_name="")
            return {'CANCELLED'}
        pm = pr.selected_pm

        self.op_bl_idname = WM_OT_pmi_edit.bl_idname
        if self.clipboard:
            self.op_bl_idname = WM_OT_pmi_edit_clipboard.bl_idname
        elif self.auto:
            self.op_bl_idname = WM_OT_pmi_edit_auto.bl_idname

        if not self.text and not bpy.app.debug_wm:
            bpy.context.window_manager.popup_menu(
                self._draw_debug, title="Debug Mode")

        elif pm.mode == 'DIALOG':
            popup_dialog_pie(event, self._draw_pd)

        elif pm.mode == 'PMENU':
            bpy.context.window_manager.popup_menu(
                self._draw_pm,
                title=pm.name)

        elif pm.mode == 'RMENU':
            bpy.context.window_manager.popup_menu(self._draw_rm)

        elif pm.mode == 'SCRIPT':
            bpy.context.window_manager.popup_menu(
                self._draw_script, title=pm.name)

        elif pm.mode == 'STICKY':
            bpy.context.window_manager.popup_menu(
                self._draw_sticky, title=pm.name)

        elif pm.mode == 'MACRO':
            bpy.context.window_manager.popup_menu(
                self._draw_script, title=pm.name)

        elif pm.mode == 'MODAL':
            pm.ed.popup_edit_menu(pm, self)

        elif pm.mode == 'PANEL' or pm.mode == 'HPANEL':
            bpy.context.window_manager.popup_menu(
                self._draw_panel, title=pm.name)

        return {'FINISHED'}


class PME_OT_pmi_menu(bpy.types.Operator):
    bl_idname = "pme.pmi_menu"
    bl_label = ""
    bl_description = "Slot tools"
    bl_options = {'INTERNAL'}

    draw_func = None

    idx: bpy.props.IntProperty()

    def draw_menu(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')
        self.__class__.draw_func(context, self.idx)

    def execute(self, context):
        if self.__class__.draw_func:
            context.window_manager.popup_menu(self.draw_menu)
            self.__class__.draw_func = None
        return {'FINISHED'}


class PME_OT_pmi_add(AddItemOperator, bpy.types.Operator):
    bl_idname = "pme.pmi_add"
    bl_label = "Add Slot"
    bl_description = "Add a slot"

    def get_collection(self):
        return prefs().selected_pm.pmis

    def finish(self, item):
        pm = prefs().selected_pm
        pm.ed.on_pmi_add(pm, item)

        tag_redraw()


class PME_OT_pmi_move(MoveItemOperator, bpy.types.Operator):
    bl_idname = "pme.pmi_move"

    def get_collection(self):
        return prefs().selected_pm.pmis

    def get_icon(self, pmi, idx):
        pm = prefs().selected_pm
        return pm.ed.get_pmi_icon(pm, pmi, idx)

    def get_title(self):
        pm = prefs().selected_pm
        pmi = pm.pmis[self.old_idx]
        return "Move " + shorten_str(pmi.name) \
            if pmi.name.strip() else "Move Slot"

    def finish(self):
        pm = prefs().selected_pm
        pm.ed.on_pmi_move(pm)

        tag_redraw()


class PME_OT_pmi_remove(RemoveItemOperator, bpy.types.Operator):
    bl_idname = "pme.pmi_remove"

    def get_collection(self):
        return prefs().selected_pm.pmis

    def finish(self):
        pr = prefs()
        pm = pr.selected_pm
        pm.ed.on_pmi_remove(pm)

        pr.update_tree()
        tag_redraw()


class PME_OT_pmi_clear(ConfirmBoxHandler, bpy.types.Operator):
    bl_idname = "pme.pmi_clear"
    bl_label = "Clear"
    bl_description = "Clear the slot"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()

    def on_confirm(self, value):
        if not value:
            return

        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.idx]

        pmi.text = ""
        pmi.name = ""
        pmi.icon = ""
        pmi.mode = 'EMPTY'

        pm.ed.on_pmi_remove(pm)

        pr.update_tree()
        tag_redraw()
        return {'FINISHED'}


class PME_OT_pmi_cmd_generate(bpy.types.Operator):
    bl_idname = "pme.pmi_cmd_generate"
    bl_label = "Generate Command"
    bl_description = "Generate command"

    clear: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        data = pr.pmi_data

        if self.clear:
            keys = list(data.kmi.properties.keys())
            for k in keys:
                del data.kmi.properties[k]

        if pr.mode == 'PMI' and data.mode in CC.MODAL_CMD_MODES:
            op_idname, _, pos_args = operator_utils.find_operator(data.cmd)

            args = []
            for k in data.kmi.properties.keys():
                v = getattr(data.kmi.properties, k)
                value = to_py_value(data.kmi, k, v)
                if value is None or isinstance(value, dict) and not value:
                    continue
                args.append("%s=%s" % (k, repr(value)))

            if len(pos_args) > 3:
                pos_args.clear()

            pos_args = [pos_args[0]] \
                if pos_args and isinstance(eval(pos_args[0]), dict) \
                else []
            if data.cmd_ctx == 'INVOKE_DEFAULT':
                if not data.cmd_undo:
                    pos_args.append(repr(data.cmd_undo))
            else:
                pos_args.append(repr(data.cmd_ctx))
                if data.cmd_undo:
                    pos_args.append(repr(data.cmd_undo))

            if pos_args and args:
                pos_args.append("")

            cmd = "bpy.ops.%s(%s%s)" % (
                op_idname, ", ".join(pos_args), ", ".join(args))

            if DBG_CMD_EDITOR:
                data.cmd = cmd
            else:
                data["cmd"] = cmd

        return {'PASS_THROUGH'}


class WM_OT_pmi_data_edit(bpy.types.Operator):
    bl_idname = "wm.pmi_data_edit"
    bl_label = "Edit Slot"
    bl_description = (
        "Edit the slot\n"
        "Enter - OK\n"
        "Esc - Cancel"
    )
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()
    ok: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    hotkey: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        tpr = temp_prefs()

        if self.hotkey:
            if pr.mode != 'PMI' or \
                    self.ok and pr.pmi_data.has_errors():
                return {'PASS_THROUGH'}

        pm = pr.selected_pm
        data = pr.pmi_data
        data_mode = data.mode
        if data_mode in CC.MODAL_CMD_MODES:
            data_mode = 'COMMAND'

        if self.ok:
            pr.leave_mode()
            self.idx = pme.context.edit_item_idx
            pmi = pm.pmis[self.idx]

            if not data.has_errors():
                if not pmi.name and not data.name and data.sname:
                    data.name = data.sname

                pmi.mode = data.mode
                if data_mode == 'COMMAND':
                    pmi.text = data.cmd

                elif data_mode == 'PROP':
                    pmi.text = data.prop

                elif data_mode == 'MENU':
                    pmi.text = data.menu

                    sub_pm = pmi.text and pmi.text in pr.pie_menus and \
                        pr.pie_menus[pmi.text]
                    if sub_pm and sub_pm.mode in {'DIALOG', 'RMENU'} and \
                            data.expand_menu:

                        if sub_pm.mode == 'RMENU':
                            get_pme_menu_class(pmi.text)

                        if data.use_frame:
                            pmi.text = CC.F_EXPAND + pmi.text

                        pmi.text = CC.F_EXPAND + pmi.text

                elif data_mode == 'HOTKEY':
                    pmi.text = keymap_helper.to_hotkey(
                        data.key, data.ctrl, data.shift, data.alt,
                        data.oskey, data.key_mod)

                elif data_mode == 'CUSTOM':
                    pmi.text = data.custom

                    # elif data.mode == 'OPERATOR':
                    #     pmi.text = data.custom

            pmi.name = data.name
            pmi.icon = data.icon

            pm.ed.on_pmi_edit(pm, pmi)

            pr.update_tree()

            tag_redraw()
            return {'FINISHED'}

        if self.idx == -1:
            data.info()
            pr.leave_mode()
            tag_redraw()
            return {'FINISHED'}

        pmi = pm.pmis[self.idx]
        pme.context.edit_item_idx = self.idx
        pr.enter_mode('PMI')

        tpr.update_pie_menus()

        pm.ed.on_pmi_pre_edit(pm, pmi, data)

        data.check_pmi_errors(context)

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        if self.hotkey and (
                not context.area or context.area.type != CC.UPREFS or
                prefs().mode != 'PMI'):
            return {'PASS_THROUGH'}

        return self.execute(context)


class WM_OT_pmi_icon_tag_toggle(bpy.types.Operator):
    bl_idname = "wm.pmi_icon_tag_toggle"
    bl_label = ""
    bl_description = ""
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()
    tag: bpy.props.StringProperty()

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pr.pmi_data if self.idx < 0 else pm.pmis[self.idx]

        icon, icon_only, hidden, use_cb = pmi.extract_flags()
        if self.tag == CC.F_ICON_ONLY:
            if not icon or icon == 'NONE':
                icon = 'FILE_HIDDEN'
            icon_only = not icon_only

        elif self.tag == CC.F_HIDDEN:
            hidden = not hidden

        elif self.tag == CC.F_CB:
            use_cb = not use_cb

        if icon_only:
            icon = CC.F_ICON_ONLY + icon
        if hidden:
            icon = CC.F_HIDDEN + icon
        if use_cb:
            icon = CC.F_CB + icon

        pmi.icon = icon

        tag_redraw()
        return {'FINISHED'}


class WM_OT_pmi_icon_select(bpy.types.Operator):
    bl_idname = "wm.pmi_icon_select"
    bl_label = "Select Icon"
    bl_description = (
        "Select an icon\n"
        "Esc - Cancel"
    )
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()
    icon: bpy.props.StringProperty(options={'SKIP_SAVE'})
    hotkey: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()

        if self.hotkey and pr.mode != 'ICONS':
            return {'PASS_THROUGH'}

        if self.idx == -1:  # Cancel
            pr.leave_mode()
            tag_redraw()
            return {'FINISHED'}

        pm = pr.selected_pm
        pmi = pm.pmis[self.idx]

        data = pmi
        if pr.is_edit_mode():
            data = pr.pmi_data

        if not self.icon:
            if data.mode == 'PROP':
                text = data.prop if hasattr(data, "prop") else data.text
                bl_prop = bp.get(text)
                if bl_prop and bl_prop.icon != 'NONE':
                    message_box("Unable to change icon for this property")
                    return {'FINISHED'}
            pme.context.edit_item_idx = self.idx
            pr.enter_mode('ICONS')

            tag_redraw()
            return {'FINISHED'}
        else:
            icon = self.icon
            _, icon_only, hidden, use_cb = data.extract_flags()
            if icon_only:
                icon = CC.F_ICON_ONLY + icon
            if hidden:
                icon = CC.F_HIDDEN + icon
            if use_cb:
                icon = CC.F_CB + icon
            data.icon = icon if self.icon != 'NONE' else ""
            if pr.mode == 'ICONS':
                pr.leave_mode()

        if not pr.is_edit_mode():
            pm.ed.on_pmi_icon_edit(pm, pmi)

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        if self.hotkey and (
                not context.area or context.area.type != CC.UPREFS or
                prefs().mode != 'ICONS'):
            return {'PASS_THROUGH'}

        return self.execute(context)


class PME_MT_header_menu_set(bpy.types.Menu):
    bl_label = "Menu"

    def draw(self, context):
        lh.save()
        lh.lt(self.layout)

        for id, name, _, icon, _ in CC.SPACE_ITEMS:
            lh.operator(
                "pme.exec", name, icon,
                cmd=(
                    "d = prefs().pmi_data; "
                    "d.mode = 'CUSTOM'; "
                    "d.custom = 'header_menu([\"{0}\"])'; "
                    "d.sname = '{1}'"
                ).format(id, name, icon))

        lh.sep()
        lh.operator(
            "pme.exec", "Current", 'BLANK1',
            cmd=(
                "d = prefs().pmi_data; "
                "d.mode = 'CUSTOM'; "
                "d.custom = 'header_menu([\"CURRENT\"])'; "
                "d.sname = 'Current Area'"
            ))

        lh.restore()


class PME_MT_screen_set(bpy.types.Menu):
    bl_label = "Menu"

    def draw(self, context):
        lh.save()
        lh.lt(self.layout)

        icons = {
            "Layout": 'MENU_PANEL',
            "Modeling": 'VIEW3D',
            "Sculpting": 'SCULPTMODE_HLT',
            "UV Editing": 'UV',
            "Texture Paint": 'TPAINT_HLT',
            "Shading": 'SHADING_RENDERED',
            "Animation": 'NLA',
            "Rendering": 'RENDER_ANIMATION',
            "Compositing": 'NODETREE',
            "Scripting": 'TEXT',

            "3D View Full": 'FULLSCREEN',
            "Default": 'VIEW3D',
            "Game Logic": 'AUTO',
            "Motion Tracking": 'RENDER_ANIMATION',
            "Video Editing": 'SEQUENCE',
        }

        for name in sorted(bpy.data.workspaces.keys()):
            if name == "temp" or name.startswith(CC.PME_TEMP_SCREEN) or \
                    name.startswith(CC.PME_SCREEN):
                continue
            icon = icons.get(name, 'LAYER_USED')

            lh.operator(
                "pme.exec", name, icon,
                cmd=(
                    "d = prefs().pmi_data; "
                    "d.mode = 'COMMAND'; "
                    "d.cmd = 'bpy.ops.pme.screen_set(name=\"{0}\")'; "
                    "d.sname = '{0}'; "
                    "d.icon = '{1}'"
                ).format(name, icon))

        lh.restore()


class PME_MT_brush_set(bpy.types.Menu):
    bl_label = "Menu"

    def draw(self, context):
        brushes = bpy.data.brushes
        lh.save()

        def add_brush(col, brush):
            brush = brushes[brush]

            col.operator(
                "pme.exec",
                text=brush.name, icon=ic('LAYER_ACTIVE')).cmd = (
                "d = prefs().pmi_data; "
                "d.mode = 'COMMAND'; "
                "d.cmd = 'paint_settings(C).brush = D.brushes[\"{0}\"]'; "
                "d.sname = '{0}'; "
                "d.icon = '{1}'"
            ).format(brush.name, 'BRUSH_DATA')

        image_brushes = []
        sculpt_brushes = []
        vertex_brushes = []
        weight_brushes = []
        for name in sorted(brushes.keys()):
            brush = brushes[name]
            brush.use_paint_image and image_brushes.append(brush.name)
            brush.use_paint_sculpt and sculpt_brushes.append(brush.name)
            brush.use_paint_vertex and vertex_brushes.append(brush.name)
            brush.use_paint_weight and weight_brushes.append(brush.name)

        row = self.layout.row()
        col_image = row.column()
        col_image.label(text="Image", icon=ic('TPAINT_HLT'))
        col_image.separator()
        for brush in image_brushes:
            add_brush(col_image, brush)

        col_vertex = row.column()
        col_vertex.label(text="Vertex", icon=ic('VPAINT_HLT'))
        col_vertex.separator()
        for brush in vertex_brushes:
            add_brush(col_vertex, brush)

        col_weight = row.column()
        col_weight.label(text="Weight", icon=ic('WPAINT_HLT'))
        col_weight.separator()
        for brush in weight_brushes:
            add_brush(col_weight, brush)

        col_sculpt = row.column()
        col_sculpt.label(text="Sculpt", icon=ic('SCULPTMODE_HLT'))
        col_sculpt.separator()
        for brush in sculpt_brushes:
            add_brush(col_sculpt, brush)

        lh.restore()


class PME_MT_poll_mesh(bpy.types.Menu):
    bl_label = "Mesh Select Mode"

    def draw(self, context):
        layout = self.layout

        layout.operator(
            PME_OT_exec.bl_idname, text="Vertex Select Mode",
            icon=ic('VERTEXSEL')
        ).cmd = (
            "prefs().selected_pm.poll_cmd = "
            "'return C.scene.tool_settings.mesh_select_mode[0]'"
        )
        layout.operator(
            PME_OT_exec.bl_idname, text="Edge Select Mode",
            icon=ic('EDGESEL')
        ).cmd = (
            "prefs().selected_pm.poll_cmd = "
            "'return C.scene.tool_settings.mesh_select_mode[1]'"
        )
        layout.operator(
            PME_OT_exec.bl_idname, text="Face Select Mode",
            icon=ic('FACESEL')
        ).cmd = (
            "prefs().selected_pm.poll_cmd = "
            "'return C.scene.tool_settings.mesh_select_mode[2]'"
        )


class PME_MT_poll_object(bpy.types.Menu):
    bl_label = "Active Object Type"

    def draw(self, context):
        layout = self.layout

        icon = ic('NODE_SEL')
        for item in sorted(
                bpy.types.Object.bl_rna.properties["type"].enum_items,
                key=lambda item: item.name):
            layout.operator(
                PME_OT_exec.bl_idname, text=item.name + " Object",
                icon=icon
            ).cmd = (
                "prefs().selected_pm.poll_cmd = "
                "\"return C.active_object and "
                "C.active_object.type == '%s'\""
            ) % item.identifier


class PME_MT_poll_workspace(bpy.types.Menu):
    bl_label = "Active Workspace"

    def draw(self, context):
        layout = self.layout

        icon = ic('WORKSPACE')
        for item in sorted(
                bpy.data.workspaces,
                key=lambda item: item.name):
            layout.operator(
                PME_OT_exec.bl_idname, text=item.name,
                icon=icon
            ).cmd = (
                "prefs().selected_pm.poll_cmd = "
                "\"return C.workspace.name == '%s'\""
            ) % item.name


class PME_OT_poll_specials_call(bpy.types.Operator):
    bl_idname = "pme.poll_specials_call"
    bl_label = "Menu"
    bl_description = "Menu"
    bl_options = {'INTERNAL'}

    def _poll_specials_call_menu(self, menu, context):
        layout = menu.layout
        layout.operator_context = 'INVOKE_DEFAULT'

        layout.operator(
            PME_OT_script_open.bl_idname,
            text="External Script", icon=ic('FILE_FOLDER'),
        )

        layout.separator()

        layout.label(text="Examples:", icon=ic('NODE_SEL'))
        layout.menu("PME_MT_poll_mesh", icon=ic('VERTEXSEL'))
        layout.menu("PME_MT_poll_object", icon=ic('OBJECT_DATAMODE'))
        layout.menu("PME_MT_poll_workspace", icon=ic('WORKSPACE'))

        layout.separator()

        layout.operator(
            PME_OT_exec.bl_idname, text="Reset", icon=ic('X')
        ).cmd = "prefs().selected_pm.poll_cmd = 'return True'"

    def execute(self, context):
        context.window_manager.popup_menu(self._poll_specials_call_menu)
        return {'FINISHED'}


class PME_OT_keymap_add(bpy.types.Operator):
    bl_idname = "pme.keymap_add"
    bl_label = ""
    bl_description = "Add a keymap"
    bl_options = {'INTERNAL'}
    bl_property = "enumprop"

    items = None

    def get_items(self, context):
        cl = PME_OT_keymap_add
        if not cl.items:
            it1 = []
            it2 = []
            pr = prefs()
            pm = pr.selected_pm

            for km in context.window_manager.keyconfigs.user.keymaps:
                has_hotkey = False
                for kmi in km.keymap_items:
                    if kmi.idname and kmi.type != 'NONE' and \
                            kmi.type == pm.key and \
                            kmi.ctrl == pm.ctrl and \
                            kmi.shift == pm.shift and \
                            kmi.alt == pm.alt and \
                            kmi.oskey == pm.oskey and \
                            kmi.key_modifier == pm.key_mod:
                        has_hotkey = True
                        break

                if has_hotkey:
                    it1.append((km.name, "%s (%s)" % (km.name, kmi.name), ""))
                else:
                    it2.append((km.name, km.name, ""))

            it1.sort()
            it2.sort()

            cl.items = [t for t in it1]
            cl.items.extend([t for t in it2])

        return cl.items

    enumprop: bpy.props.EnumProperty(items=get_items)

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm
        km_names = pm.parse_keymap()
        if self.enumprop not in km_names:
            # names = parse_keymap(pm.km_name)
            names = list(km_names)
            if len(names) == 1 and names[0] == "Window":
                names.clear()
            names.append(self.enumprop)
            names.sort()
            pm.km_name = (CC.KEYMAP_SPLITTER + " ").join(names)

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        PME_OT_keymap_add.items = None
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_pm_open_mode_select(bpy.types.Operator):
    bl_idname = "pme.pm_open_mode_select"
    bl_label = "Hotkey Mode"
    bl_description = "Select hotkey mode"

    def _draw(self, menu, context):
        layout = menu.layout
        pm = prefs().selected_pm
        layout.prop(pm, "open_mode", expand=True)

    def execute(self, context):
        context.window_manager.popup_menu(
            self._draw, title=PME_OT_pm_open_mode_select.bl_label)
        return {'FINISHED'}


class PME_OT_pm_hotkey_convert(bpy.types.Operator):
    bl_idname = "pme.pm_hotkey_convert"
    bl_label = ""
    bl_options = {'INTERNAL'}
    bl_description = "Replace the key with ActionMouse/SelectMouse"

    def execute(self, context):
        pm = prefs().selected_pm
        if pm and (pm.key == 'LEFTMOUSE' or pm.key == 'RIGHTMOUSE'):
            pm.key = keymap_helper.to_blender_mouse_key(pm.key, context)
            return {'FINISHED'}
        return {'CANCELLED'}


class PME_OT_pmi_copy(bpy.types.Operator):
    bl_idname = "pme.pmi_copy"
    bl_label = "Copy Slot"
    bl_description = "Copy the slot"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        pmi = pm.pmis[self.idx]

        pr.pmi_clipboard.copy(pm, pmi)
        return {'FINISHED'}


class PME_OT_pmi_paste(bpy.types.Operator):
    bl_idname = "pme.pmi_paste"
    bl_label = "Paste Slot"
    bl_description = "Paste the slot"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.idx]
        cb = pr.pmi_clipboard

        cb.paste(pm, pmi)

        pm.ed.on_pmi_paste(pm, pmi)

        pr.update_tree()
        tag_redraw()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        pr = prefs()
        pm = pr.selected_pm
        cb = pr.pmi_clipboard
        return cb.has_data() and \
            cb.mode in pm.ed.supported_slot_modes and \
            cb.pm_mode in pm.ed.supported_paste_modes


class PME_OT_pm_toggle(bpy.types.Operator):
    bl_idname = "pme.pm_toggle"
    bl_label = "Enable or Disable Item"
    bl_description = "Enable or disable the active item"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(options={'SKIP_SAVE'})
    action: bpy.props.EnumProperty(
        items=(
            ('TOGGLE', "Toggle", ""),
            ('ENABLE', "Enable", ""),
            ('DISABLE', "Disable", ""),
        ),
        options={'SKIP_SAVE'})

    def execute(self, context):
        value = None
        if self.action == 'ENABLE':
            value = True
        elif self.action == 'DISABLE':
            value = False
        toggle_menu(self.name, value)
        return {'FINISHED'}


class PME_OT_pmi_toggle(bpy.types.Operator):
    bl_idname = "pme.pmi_toggle"
    bl_label = "Enable or Disable Menu Slot"
    bl_description = "Enable or disable the slot"
    bl_options = {'INTERNAL'}

    pm: bpy.props.StringProperty(options={'SKIP_SAVE'})
    pmi: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        pm = pr.pie_menus[self.pm]
        pmi = pm.pmis[self.pmi]
        pmi.enabled = not pmi.enabled
        pm.ed.on_pmi_toggle(pm, pmi)
        tag_redraw()
        return {'FINISHED'}


class EditorBase:
    def __init__(self):
        prefs().editors[self.id] = self

        for id, name, icon in CC.ED_DATA:
            if id == self.id:
                self.default_name = name
                self.icon = icon
                break

        # self.props = set()
        self.docs = None
        self.editable_slots = True
        self.use_slot_icon = True
        self.copy_paste_slot = True
        self.use_preview = True
        self.sub_item = True
        self.has_hotkey = True
        self.has_extra_settings = True
        self.default_pmi_data = ""
        self.fixed_num_items = False
        self.movable_items = True
        self.use_swap = False
        self.pmi_move_operator = PME_OT_pmi_move.bl_idname
        self.toggleable_slots = True

        self.supported_slot_modes = {
            'EMPTY', 'COMMAND', 'PROP', 'MENU', 'HOTKEY', 'CUSTOM'
        }
        self.supported_open_modes = {
            'PRESS', 'HOLD', 'DOUBLE_CLICK', 'ONE_SHOT'
        }
        self.supported_sub_menus = {
            'PMENU', 'RMENU', 'DIALOG', 'SCRIPT', 'STICKY', 'MACRO', 'MODAL',
            'PROPERTY'
        }
        self.supported_paste_modes = {
            'PMENU', 'RMENU', 'DIALOG', 'SCRIPT', 'STICKY', 'MACRO'
        }

    def register_temp_prop(self, id, prop):
        tpr = temp_prefs()
        try:
            del tpr.ed_props[id]
        except:
            pass

        setattr(tpr.ed_props.__class__, id, prop)

    def register_pm_prop(self, id, prop):
        setattr(PMItem, id, prop)

    def register_pmi_prop(self, id, prop):
        setattr(PMIItem, id, prop)

    def register_props(self, pm):
        pass

    def unregister_props(self):
        def del_ed_props(cls):
            for k in dir(cls):
                if k.startswith("ed_"):
                    delattr(cls, k)

        del_ed_props(temp_prefs().ed_props.__class__)
        del_ed_props(PMItem)
        del_ed_props(PMIItem)
        # for id in self.props:
        #     delattr(cls, id)

        # self.props.clear()

    def init_pm(self, pm):
        if not pm.data:
            pm.data = self.default_pmi_data

    def on_pm_select(self, pm):
        self.register_props(pm)

    def on_pm_add(self, pm):
        pass

    def on_pm_remove(self, pm):
        pass

    def on_pm_duplicate(self, from_pm, pm):
        for from_pmi in from_pm.pmis:
            pmi = pm.pmis.add()
            pmi.name = from_pmi.name
            pmi.icon = from_pmi.icon
            pmi.mode = from_pmi.mode
            pmi.text = from_pmi.text

    def on_pm_enabled(self, pm, value):
        if self.has_hotkey:
            pm.update_keymap_item(bpy.context)

            if pm.key_mod in KH.MOUSE_BUTTONS:
                kms = pm.parse_keymap()
                for km in kms:
                    if pm.enabled:
                        pass
                        # KH.add_mouse_button(pm.key_mod, kh, km)
                    else:
                        KH.remove_mouse_button(pm.key_mod, prefs().kh, km)

    def on_pm_rename(self, pm, name):
        pr = prefs()
        tpr = temp_prefs()

        old_name = pm.name

        for link in tpr.links:
            if link.pm_name == old_name:
                link.pm_name = name

        if pm.mode == 'RMENU' and old_name in pme_menu_classes:
            del pme_menu_classes[old_name]
            get_pme_menu_class(name)

        for v in pr.pie_menus:
            if v == pm:
                continue

            for pmi in v.pmis:
                if pmi.mode == 'MENU':
                    menu_name, mouse_over, _ = U.extract_str_flags(
                        pmi.text, CC.F_EXPAND, CC.F_EXPAND)
                    if menu_name == old_name:
                        pmi.text = CC.F_EXPAND + name \
                            if mouse_over else name

        if old_name in pm.kmis_map:
            if pm.kmis_map[old_name]:
                pm.unregister_hotkey()
            else:
                pm.kmis_map[name] = pm.kmis_map[old_name]
                del pm.kmis_map[old_name]

        if old_name in pr.tree_ul.expanded_folders:
            pr.tree_ul.expanded_folders.remove(old_name)
            pr.tree_ul.expanded_folders.add(name)

        if old_name in pr.old_pms:
            pr.old_pms.remove(old_name)
            pr.old_pms.add(name)

        for link in tpr.links:
            if link.pm_name == old_name:
                link.pm_name = name
            for i in range(0, len(link.path)):
                if link.path[i] == old_name:
                    link.path[i] = name

        pm.name = name

        if pm.name not in pm.kmis_map:
            pm.register_hotkey()

        pr.update_tree()

    def on_pmi_check(self, pm, pmi_data):
        pr = prefs()

        data = pmi_data
        data.info()
        pmi_mode = 'COMMAND' if data.mode in CC.MODAL_CMD_MODES else data.mode

        if pmi_mode == 'COMMAND':
            if data.cmd:
                try:
                    compile(data.cmd, '<string>', 'exec')
                except:
                    data.info(CC.W_PMI_SYNTAX)

            data.sname = ""
            if not data.has_errors():
                mo = re_operator.search(data.cmd)
                if mo:
                    data.sname = gen_op_name(mo, True)
                else:
                    mo = re_prop.search(data.cmd)
                    if mo:
                        data.sname, icon = gen_prop_name(mo, False, True)
                    else:
                        data.sname = shorten_str(data.cmd, 20)

        elif pmi_mode == 'PROP':
            if data.prop:
                try:
                    compile(data.prop, '<string>', 'eval')
                except:
                    data.info(CC.W_PMI_SYNTAX)

            data.sname = ""
            if not data.has_errors():
                prop = bp.get(data.prop)
                if prop:
                    data.sname = prop.name or utitle(prop.identifier)
                else:
                    data.sname = utitle(data.prop.rpartition(".")[2])

        elif pmi_mode == 'MENU':
            data.sname = data.menu
            pr = prefs()
            if not data.menu or data.menu not in pr.pie_menus:
                data.info(CC.W_PMI_MENU)

        elif pmi_mode == 'HOTKEY':
            data.sname = keymap_helper.to_ui_hotkey(data)
            if data.key == 'NONE':
                data.info(CC.W_PMI_HOTKEY)

        elif pmi_mode == 'CUSTOM':
            data.sname = ""

            if data.custom:
                try:
                    compile(data.custom, '<string>', 'exec')
                    data.sname = shorten_str(data.custom, 20)
                except:
                    data.info(CC.W_PMI_SYNTAX)

    def on_pmi_add(self, pm, pmi):
        pmi.mode = 'COMMAND'
        pmi.name = uname(pm.pmis, "Command", " ", 1, False)

    def on_pmi_move(self, pm):
        pass

    def on_pmi_remove(self, pm):
        pass

    def on_pmi_paste(self, pm, pmi):
        pmi.icon, *_ = pmi.extract_flags()

    def on_pmi_pre_edit(self, pm, pmi, data):
        data.sname = ""
        data.kmi.idname = ""
        data.mode = pmi.mode if pmi.mode != 'EMPTY' else 'COMMAND'
        data.name = pmi.name
        data.icon = pmi.icon

        data_mode = 'COMMAND' if data.mode in CC.MODAL_CMD_MODES else data.mode

        data.cmd = pmi.text if data_mode == 'COMMAND' else ""
        data.custom = pmi.text if data_mode == 'CUSTOM' else ""
        data.prop = pmi.text if data_mode == 'PROP' else ""
        data.menu = pmi.text if data_mode == 'MENU' else ""
        data.menu, data.expand_menu, data.use_frame = U.extract_str_flags(
            data.menu, CC.F_EXPAND, CC.F_EXPAND)

        data.key, data.ctrl, data.shift, data.alt, \
            data.oskey, data.key_mod = \
            'NONE', False, False, False, False, 'NONE'

        if pmi.mode == 'HOTKEY':
            data.key, data.ctrl, data.shift, data.alt, \
                data.oskey, data.any, data.key_mod, _ = \
                keymap_helper.parse_hotkey(pmi.text)

    def on_pmi_rename(self, pm, pmi, old_name, name):
        pmi.name = name

    def on_pmi_toggle(self, pm, pmi):
        pass

    def on_pmi_edit(self, pm, pmi):
        pass

    def on_pmi_icon_edit(self, pm, pmi):
        pass

    def draw_extra_settings(self, layout, pm):
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.alert = pm.name in pm.poll_methods and \
            pm.poll_methods[pm.name] is None
        sub.prop(pm, "poll_cmd", text="", icon=ic('NODE_SEL'))
        row.operator(
            PME_OT_poll_specials_call.bl_idname, text="",
            icon=ic('COLLAPSEMENU'))

    def draw_pm_name(self, layout, pm):
        pr = prefs()
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator_context = 'INVOKE_DEFAULT'
        row.operator(
            PME_OT_pm_toggle.bl_idname, text="",
            icon=ic_cb(pm.enabled)).name = pm.name

        if self.use_preview:
            p = row.operator(
                PME_OT_preview.bl_idname, text="", icon=ic('HIDE_OFF'))
            p.pie_menu_name = pm.name

        p = row.operator(
            WM_OT_pm_select.bl_idname, text="", icon=ic(self.icon))
        p.pm_name = ""
        p.use_mode_icons = True
        row.prop(pm, "label", text="")

        row.operator(
            PME_OT_tags.bl_idname, text="",
            icon=ic_fb(pm.tag))

        if self.docs:
            p = row.operator(PME_OT_docs.bl_idname, text="", icon=ic('HELP'))
            p.id = self.docs

        if self.has_extra_settings:
            row.prop(
                pr, "show_advanced_settings", text="",
                icon=ic('SETTINGS'))

            if pr.show_advanced_settings:
                self.draw_extra_settings(col.box().column(), pm)

    def draw_keymap(self, layout, data):
        row = layout.row(align=True)
        if ',' in data.km_name:
            row.prop(data, "km_name", text="", icon=ic('SPLITSCREEN'))
        else:
            row.prop_search(
                data, "km_name",
                bpy.context.window_manager.keyconfigs.user, "keymaps",
                text="", icon=ic('SPLITSCREEN'))
        row.operator(PME_OT_keymap_add.bl_idname, text="", icon=ic('ZOOMIN'))

    def draw_hotkey(self, layout, data):
        row = layout.row(align=True)
        row.operator_context = 'INVOKE_DEFAULT'
        item = None
        pd = data.__annotations__["open_mode"]
        pkeywords = pd.keywords if hasattr(pd, "keywords") else pd[1]
        for i in pkeywords['items']:
            if i[0] == data.open_mode:
                item = i
                break

        subcol = row.column(align=True)
        subcol.scale_y = 2
        subcol.operator(
            PME_OT_pm_open_mode_select.bl_idname, text="", icon_value=item[3])

        subcol = row.column(align=True)
        if data.open_mode != 'CHORDS':
            subrow = subcol.row(align=True)
        else:
            subrow = split(subcol, 5 / 6, align=True)
        # left = subrow.row(align=True)
        # left.alignment = 'LEFT'
        # left.operator(
        #     PME_OT_pm_open_mode_select.bl_idname, text=item[1], icon=item[3])
        subrow.prop(data, "key", text="", event=True)
        if data.open_mode == 'CHORDS':
            subrow.prop(data, "chord", text="", event=True)

        # if data.key == 'LEFTMOUSE' or data.key == 'RIGHTMOUSE':
        #     subrow.operator(
        #         PME_OT_pm_hotkey_convert.bl_idname, text="",
        #         icon='RESTRICT_SELECT_OFF')
        if data.any:
            subrow = split(subcol, 5 / 6, align=True)
            subrow.prop(data, "any", text="Any", toggle=True)
        else:
            subrow = subcol.row(align=True)
            subrow.prop(data, "any", text="Any", toggle=True)
            subrow.prop(data, "ctrl", text="Ctrl", toggle=True)
            subrow.prop(data, "shift", text="Shift", toggle=True)
            subrow.prop(data, "alt", text="Alt", toggle=True)
            subrow.prop(data, "oskey", text="OSkey", toggle=True)
        subrow.prop(data, "key_mod", text="", event=True)

        subcol = row.column(align=True)
        subcol.scale_y = 2
        subcol.operator(PME_OT_pm_hotkey_remove.bl_idname, icon=ic('X'))

    def draw_items(self, layout, pm):
        pr = prefs()
        column = layout.column(align=True)

        for idx, pmi in enumerate(pm.pmis):
            lh.row(column, active=pmi.enabled)

            self.draw_item(pm, pmi, idx)
            self.draw_pmi_menu_btn(pr, idx)

        if not self.fixed_num_items:
            lh.lt(column)
            lh.operator(PME_OT_pmi_add.bl_idname, "Add Item")

    def draw_item(self, pm, pmi, idx):
        if self.editable_slots:
            lh.operator(
                WM_OT_pmi_data_edit.bl_idname,
                "", self.get_pmi_icon(pm, pmi, idx),
                idx=idx,
                ok=False)

        if self.get_use_slot_icon(pm, pmi, idx):
            icon = pmi.parse_icon('FILE_HIDDEN')

            lh.operator(
                WM_OT_pmi_icon_select.bl_idname, "", icon,
                idx=idx,
                icon="")

        lh.prop(pmi, "label", "")

    def draw_pmi_menu_btn(self, pr, idx):
        if pr.expand_item_menu:
            lh.icon_only = True
            lh.skip(L_SEP | L_LABEL)
            self.draw_pmi_menu(bpy.context, idx)
            lh.icon_only = False
            lh.skip()
        else:
            PME_OT_pmi_menu.draw_func = self.draw_pmi_menu
            lh.operator(
                PME_OT_pmi_menu.bl_idname,
                "", 'COLLAPSEMENU',
                idx=idx)

    def draw_pmi_menu(self, context, idx):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[idx]

        text, *_ = pmi.parse()
        icon = self.get_pmi_icon(pm, pmi, idx)
        lh.label(shorten_str(text) if text.strip() else "Slot", icon)

        lh.sep(check=True)

        if self.editable_slots:
            lh.operator(
                WM_OT_pmi_data_edit.bl_idname,
                "Edit Slot", 'TEXT',
                idx=idx,
                ok=False)

        if not self.fixed_num_items:
            lh.operator(
                PME_OT_pmi_add.bl_idname, "Add Slot", 'ZOOMIN',
                idx=idx)

        if self.copy_paste_slot:
            lh.sep(check=True)

            lh.operator(
                PME_OT_pmi_copy.bl_idname, None, 'COPYDOWN',
                enabled=(pmi.mode != 'EMPTY'),
                idx=idx)

            if pr.pmi_clipboard.has_data():
                lh.operator(
                    PME_OT_pmi_paste.bl_idname, None, 'PASTEDOWN',
                    idx=idx)

        if self.movable_items and len(pm.pmis) > 1:
            lh.sep(check=True)

            lh.operator(
                self.pmi_move_operator, "Move Slot",
                'ARROW_LEFTRIGHT' if self.use_swap else 'FORWARD',
                old_idx=idx, swap=self.use_swap)

        if self.toggleable_slots:
            lh.sep(check=True)
            lh.operator(
                PME_OT_pmi_toggle.bl_idname,
                "Enabled" if pmi.enabled else "Disabled", ic_eye(pmi.enabled),
                pm=pm.name, pmi=idx)

        if self.fixed_num_items:
            if 'EMPTY' in self.supported_slot_modes:
                lh.sep(check=True)

                lh.operator(
                    PME_OT_pmi_clear.bl_idname,
                    "Clear", 'X',
                    idx=idx)
        elif len(pm.pmis) > 1:
            lh.sep(check=True)

            lh.operator(
                PME_OT_pmi_remove.bl_idname,
                "Remove", 'X',
                idx=idx, confirm=lh.icon_only)

    def get_supported_slot_modes(self, pm, slot, idx):
        return self.supported_slot_modes

    def get_use_slot_icon(self, pm, slot, idx):
        return self.use_slot_icon

    def draw_slot_modes(self, layout, pm, slot, idx):
        for mode, _, _ in EMODE_ITEMS:
            if mode in self.get_supported_slot_modes(pm, slot, idx):
                layout.prop_enum(slot, "mode", mode)

    def get_pmi_icon(self, pm, pmi, idx):
        return 'MOD_SKIN'

    def draw_edit_menu(self, menu, context):
        pm = prefs().selected_pm

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        for idx, pmi in enumerate(pm.pmis):
            text, *_ = pmi.parse()
            lh.operator(
                self.op.op_bl_idname, text,
                self.get_pmi_icon(pm, pmi, idx), pm_item=idx,
                mode=self.op.mode, text=self.op.text, name=self.op.name,
                add=False, new_script=False)

        lh.sep()

        lh.operator(
            self.op.op_bl_idname, "New Command", 'ZOOMIN',
            mode=self.op.mode, text=self.op.text, name=self.op.name,
            pm_item=-1, add=True, new_script=False)

        # lh.operator(
        #     self.operator, "New Stack Key", 'MOD_SKIN',
        #     pm_item=-1, add=False, new_script=True)
        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)

    def popup_edit_menu(self, pm, operator):
        self.op = operator
        bpy.context.window_manager.popup_menu(
            self.draw_edit_menu, title=pm.name)

    def use_scroll(self, pm):
        return False

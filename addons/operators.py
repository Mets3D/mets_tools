import bpy
import os
import traceback
from inspect import isclass
from math import pi as PI
from time import time
from .addon import prefs, uprefs, temp_prefs, ADDON_PATH, print_exc, ic, is_28
from .bl_utils import (
    bl_context, gen_prop_path,
    message_box, PME_OT_popup_close, PopupOperator, area_header_text_set)
from .layout_helper import lh, draw_pme_layout, operator
from .overlay import Timer, Overlay, TablePainter
from .ui import tag_redraw, utitle
from . import utils as U
from . import c_utils as CTU
from .panel_utils import (
    hide_panel, hidden_panel, is_panel_hidden, bl_panel_types,
    bl_panel_enum_items, panel)
from .constants import (
    I_DEBUG, SPACE_ITEMS, REGION_ITEMS, PM_ITEMS_M, MAX_STR_LEN, W_PMI_ADD_BTN,
    F_EXPAND, MODAL_CMD_MODES)
from . import constants as CC
from .debug_utils import *
from .macro_utils import execute_macro
from .modal_utils import decode_modal_data
from . import (
    pme,
    operator_utils,
    keymap_helper
)
from . import screen_utils as SU
from .property_utils import PropertyData
from .keymap_helper import (
    MOUSE_BUTTONS, is_key_pressed, StackKey, to_key_name, to_ui_hotkey)


def popup_dialog_pie(event, draw, title=""):
    pr = prefs()
    # pr.pie_menu_prefs.save()
    pr.pie_menu_radius.save()
    uprefs().view.pie_menu_radius = 0
    bpy.context.window_manager.popup_menu_pie(event, draw, title=title)
    pr.pie_menu_radius.restore()
    # pr.pie_menu_prefs.restore()


class WM_OT_pme_none(bpy.types.Operator):
    bl_idname = "wm.pme_none"
    bl_label = ""
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}


class WM_OT_pm_select(bpy.types.Operator):
    bl_idname = "wm.pm_select"
    bl_label = "Select Item"
    bl_description = "Select an item to edit"

    pm_name: bpy.props.StringProperty(options={'SKIP_SAVE'})
    use_mode_icons: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    mode: bpy.props.EnumProperty(
        items=PM_ITEMS_M,
        default=set(),
        options={'SKIP_SAVE', 'ENUM_FLAG'})

    def _draw(self, menu, context):
        lh.lt(menu.layout, 'INVOKE_DEFAULT')

        lh.menu("PME_MT_pm_new", "New", 'ZOOMIN')
        lh.operator(
            PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM',
            mode=self.mode)

        pr = prefs()
        if len(pr.pie_menus) == 0:
            return

        lh.sep()
        apm = pr.selected_pm

        keys = sorted(pr.pie_menus.keys())
        for k in keys:
            pm = pr.pie_menus[k]
            if self.mode and pm.mode not in self.mode:
                continue

            if self.use_mode_icons:
                icon = pm.ed.icon

            else:
                icon = 'SPACE3'
                if pm == apm:
                    icon = 'SPACE2'

            lh.operator(
                WM_OT_pm_select.bl_idname, k, icon,
                pm_name=k)

    def execute(self, context):
        if not self.pm_name:
            bpy.context.window_manager.popup_menu(
                self._draw, title=self.bl_label)
        else:
            pr = prefs()
            tpr = temp_prefs()
            pm = None
            idx = pr.pie_menus.find(self.pm_name)
            if idx >= 0:
                pr.active_pie_menu_idx = idx
                pm = pr.pie_menus[idx]

            if pr.tree_mode:
                for idx, link in enumerate(tpr.links):
                    if link.pm_name == self.pm_name and not link.path:
                        tpr.links_idx = idx
                        break
                else:
                    tpr["links_idx"] = -1

                if pm:
                    pr.tree.expand_km(pm.km_name)

        tag_redraw()
        return {'CANCELLED'}


class PME_OT_pm_search_and_select(bpy.types.Operator):
    bl_idname = "pme.pm_search_and_select"
    bl_label = "Search and Select Item"
    bl_description = "Search and select an item"
    bl_options = {'INTERNAL'}
    bl_property = "item"

    enum_items = None

    def get_items(self, context):
        pr = prefs()

        if not PME_OT_pm_search_and_select.enum_items:
            enum_items = []

            for k in sorted(pr.pie_menus.keys()):
                pm = pr.pie_menus[k]
                if self.mode and pm.mode not in self.mode:
                    continue
                enum_items.append(
                    (pm.name, "%s|%s" % (pm.name, to_ui_hotkey(pm)), ""))

            PME_OT_pm_search_and_select.enum_items = enum_items

        return PME_OT_pm_search_and_select.enum_items

    item: bpy.props.EnumProperty(items=get_items)
    mode: bpy.props.EnumProperty(
        items=PM_ITEMS_M,
        default=set(),
        options={'SKIP_SAVE', 'ENUM_FLAG'})

    def execute(self, context):
        bpy.ops.wm.pm_select(pm_name=self.item)
        PME_OT_pm_search_and_select.enum_items = None
        return {'FINISHED'}

    def invoke(self, context, event):
        PME_OT_pm_search_and_select.enum_items = None
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class WM_OT_pme_user_command_exec(bpy.types.Operator):
    bl_idname = "wm.pme_user_command_exec"
    bl_label = ""
    bl_description = "Execute python code"
    bl_options = {'INTERNAL'}

    cmds = []

    menu: bpy.props.StringProperty(options={'SKIP_SAVE', 'HIDDEN'})
    slot: bpy.props.StringProperty(options={'SKIP_SAVE', 'HIDDEN'})
    cmd: bpy.props.StringProperty(
        name="Python Code", description="Python Code",
        maxlen=MAX_STR_LEN, options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        pme.context.exec_operator = self
        exec_globals = pme.context.gen_globals()
        exec_globals.update(menu=self.menu, slot=self.slot)
        pme.context.exe(self.cmd, exec_globals)
        pme.context.exec_operator = None
        return exec_globals.get("return_value", {'FINISHED'})

    def invoke(self, context, event):
        pme.context.event = event
        return self.execute(context)


class PME_OT_exec(bpy.types.Operator):
    bl_idname = "pme.exec"
    bl_label = ""
    bl_description = "Execute python code"
    bl_options = {'INTERNAL'}

    cmds = []

    cmd: bpy.props.StringProperty(
        name="Python Code", description="Python Code",
        maxlen=MAX_STR_LEN, options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        exec_globals = pme.context.gen_globals()
        pme.context.exec_operator = self
        pme.context.exe(self.cmd, exec_globals)
        pme.context.exec_operator = None
        return exec_globals.get("return_value", {'FINISHED'})

    def invoke(self, context, event):
        pme.context.event = event
        return self.execute(context)


class PME_OT_panel_hide(bpy.types.Operator):
    bl_idname = "pme.panel_hide"
    bl_label = "Hide Panel"
    bl_description = "Hide panel"
    bl_options = {'INTERNAL'}
    bl_property = "item"

    enum_items = None

    def get_items(self, context):
        if not PME_OT_panel_hide.enum_items:
            PME_OT_panel_hide.enum_items = bl_panel_enum_items(False)

        return PME_OT_panel_hide.enum_items

    item: bpy.props.EnumProperty(items=get_items, options={'SKIP_SAVE'})
    panel: bpy.props.StringProperty(options={'SKIP_SAVE'})
    group: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def draw_menu(self, menu, context):
        lh.lt(menu.layout)
        pr = prefs()
        for pm in pr.pie_menus:
            if pm.mode == 'HPANEL':
                lh.operator(
                    PME_OT_panel_hide.bl_idname,
                    pm.name, pm.ed.icon,
                    group=pm.name, panel=self.panel)

        lh.sep(check=True)

        lh.operator(
            PME_OT_panel_hide.bl_idname,
            "New Hidden Panel Group", 'ZOOMIN',
            group=pr.unique_pm_name(pr.ed('HPANEL').default_name),
            panel=self.panel)

    def execute(self, context):
        if not self.panel:
            self.panel = self.item

        pr = prefs()

        if not self.group:
            context.window_manager.popup_menu(self.draw_menu, title="Group")
            return {'FINISHED'}
        else:
            if self.group not in pr.pie_menus:
                group = pr.add_pm('HPANEL', self.group)
                pr.update_tree()
            else:
                group = pr.pie_menus[self.group]

        tp = hidden_panel(self.panel) or \
            getattr(bpy.types, self.panel, None)

        if not tp:
            return {'CANCELLED'}

        for pmi in group.pmis:
            if pmi.text == self.panel:
                return {'CANCELLED'}

        pmi = group.pmis.add()
        pmi.mode = 'MENU'
        pmi.name = tp.bl_label if hasattr(tp, "bl_label") else self.panel
        pmi.text = self.panel

        hide_panel(self.panel)

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.panel:
            PME_OT_panel_hide.enum_items = None
            context.window_manager.invoke_search_popup(self)
        else:
            return self.execute(context)
        return {'FINISHED'}


class PME_OT_panel_hide_by(bpy.types.Operator):
    bl_idname = "pme.panel_hide_by"
    bl_label = "Hide Panels by ..."
    bl_description = "Hide panels by ..."
    bl_options = {'INTERNAL'}

    space_items = None
    region_items = None
    ctx_items = None
    cat_items = None

    def _get_space_items(self, context):
        if not PME_OT_panel_hide_by.space_items:
            enum_items = [("ANY", "Any Space", "", 'LAYER_ACTIVE', 0)]

            for i, item in enumerate(SPACE_ITEMS):
                enum_items.append((item[0], item[1], "", item[3], i + 1))

            PME_OT_panel_hide_by.space_items = enum_items

        return PME_OT_panel_hide_by.space_items

    def _get_region_items(self, context):
        if not PME_OT_panel_hide_by.region_items:
            enum_items = [("ANY", "Any Region", "", 'LAYER_ACTIVE', 0)]

            for i, item in enumerate(REGION_ITEMS):
                enum_items.append((item[0], item[1], "", item[3], i + 1))

            PME_OT_panel_hide_by.region_items = enum_items

        return PME_OT_panel_hide_by.region_items

    def _get_context_items(self, context):
        if not PME_OT_panel_hide_by.ctx_items:
            enum_items = [("ANY", "Any Context", "", 'LAYER_ACTIVE', 0)]

            contexts = set()
            for tp in bl_panel_types():
                if hasattr(tp, "bl_context"):
                    contexts.add(tp.bl_context)

            for i, c in enumerate(sorted(contexts)):
                enum_items.append((c, c, "", 'LAYER_USED', i + 1))

            PME_OT_panel_hide_by.ctx_items = enum_items

        return PME_OT_panel_hide_by.ctx_items

    def _get_category_items(self, context):
        if not PME_OT_panel_hide_by.cat_items:
            enum_items = [("ANY", "Any Category", "", 'LAYER_ACTIVE', 0)]

            categories = set()
            for tp in bl_panel_types():
                if hasattr(tp, "bl_category"):
                    categories.add(tp.bl_category)

            for i, c in enumerate(sorted(categories)):
                enum_items.append((c, c, "", 'LAYER_USED', i + 1))

            PME_OT_panel_hide_by.cat_items = enum_items

        return PME_OT_panel_hide_by.cat_items

    space: bpy.props.EnumProperty(
        items=_get_space_items,
        name="Space",
        description="Space",
        options={'SKIP_SAVE'})
    region: bpy.props.EnumProperty(
        items=_get_region_items,
        name="Region",
        description="Region",
        options={'SKIP_SAVE'})
    context: bpy.props.EnumProperty(
        items=_get_context_items,
        name="Context",
        description="Context",
        options={'SKIP_SAVE'})
    category: bpy.props.EnumProperty(
        items=_get_category_items,
        name="Category",
        description="Category",
        options={'SKIP_SAVE'})
    mask: bpy.props.StringProperty(
        name="Mask",
        description="Mask",
        options={'SKIP_SAVE'})

    def _filtered_panels(self, num=False):
        if num:
            num_panels = 0
        else:
            panels = []

        for tp in self.panel_types:
            if (
                    tp.bl_space_type != CC.UPREFS and
                    (self.space == 'ANY' or
                        tp.bl_space_type == self.space) and
                    (self.region == 'ANY' or
                        tp.bl_region_type == self.region) and
                    (self.context == 'ANY' or hasattr(tp, "bl_context") and
                        tp.bl_context == self.context) and
                    (self.category == 'ANY' or hasattr(tp, "bl_category") and
                        tp.bl_category == self.category) and
                    (not self.mask or hasattr(tp, "bl_label") and
                        self.mask.lower() in tp.bl_label.lower())):
                if is_panel_hidden(tp.__name__):
                    continue

                if num:
                    num_panels += 1
                else:
                    panels.append(tp)

        return num_panels if num else panels

    def check(self, context):
        return True

    def draw(self, context):
        col = self.layout.column(align=True)
        lh.row(col)
        lh.prop(self, "space", "")
        lh.prop(self, "region", "")
        lh.row(col)
        lh.prop(self, "context", "")
        lh.prop(self, "category", "")
        lh.lt(col)
        lh.prop(self, "mask", "", 'FILTER')
        lh.sep()
        lh.row(col)
        lh.layout.alignment = 'CENTER'
        lh.label("%d panel(s) will be hidden" % self._filtered_panels(True))

    def execute(self, context):
        pm = prefs().selected_pm

        for tp in self._filtered_panels():
            tp_name = tp.__name__
            if hasattr(tp, "bl_idname"):
                tp_name = tp.bl_idname

            pmi = pm.pmis.add()
            pmi.mode = 'MENU'
            pmi.name = tp.bl_label if hasattr(tp, "bl_label") else tp.__name__
            pmi.text = tp_name

            hide_panel(tp_name)

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        PME_OT_panel_hide_by.space_items = None
        PME_OT_panel_hide_by.region_items = None
        PME_OT_panel_hide_by.ctx_items = None
        PME_OT_panel_hide_by.cat_items = None
        self.panel_types = bl_panel_types()
        return context.window_manager.invoke_props_dialog(self)


class PME_OT_sticky_key_base:
    bl_idname = "pme.sticky_key"
    bl_label = "Sticky Key (PME)"

    exec_globals = {}
    root_instance = None
    active_instance = None
    idx = 0

    pm_name: bpy.props.StringProperty(
        name="Menu Name", maxlen=MAX_STR_LEN, options={'SKIP_SAVE', 'HIDDEN'})

    @property
    def is_root_instance(self):
        return self == self.root_instance

    def add_timer(self, step=0):
        if self.timer:
            bpy.context.window_manager.event_timer_remove(self.timer)
        self.timer = bpy.context.window_manager.event_timer_add(
            step, window=bpy.context.window)

    def remove_timer(self):
        if self.timer:
            bpy.context.window_manager.event_timer_remove(self.timer)
            self.timer = None

    def stop(self, cancel=False):
        DBG_STICKY and logw("Stop %d" % self.idx)
        self.result = {'CANCELLED'} if cancel else {'FINISHED'}
        self.add_timer()

    def restart(self):
        DBG_STICKY and logw("Restart %d" % self.idx)
        self.restart_flag = True
        self.add_timer()

    def modal(self, context, event):
        if event.type == 'TIMER' and self.timer:
            if self.result:
                self.remove_timer()

                if self.is_root_instance:
                    PME_OT_sticky_key.root_instance = None
                    self.execute_pmi(1)

                self.root_instance = None

                PME_OT_sticky_key.idx -= 1
                return {'FINISHED'}

            elif self.restart_flag:
                self.remove_timer()
                bpy.ops.pme.sticky_key('INVOKE_DEFAULT')
                self.restart_flag = False

                if self.is_root_instance:
                    return {'PASS_THROUGH'}

                PME_OT_sticky_key.idx -= 1
                return {'FINISHED'}

            return {'PASS_THROUGH'}

        if event.type == 'WINDOW_DEACTIVATE':
            self.stop(cancel=True)

        ret = {'RUNNING_MODAL'} if self.block_ui else {'PASS_THROUGH'}

        if not PME_OT_sticky_key.root_instance:
            DBG_STICKY and loge("BUG")
            return ret

        if self.restart_flag:
            return ret

        elif event.type == 'MOUSEMOVE' or \
                event.type == 'INBETWEEN_MOUSEMOVE':
            return ret

        if event.type == self.root_instance.key:
            if event.value == 'RELEASE':
                if self.root_instance:
                    self.root_instance.stop()
                self.stop()

            elif event.value == 'PRESS':
                self.is_pressed = True
                if self.root_instance and self.timer:
                    self.remove_timer()

            return ret

        if not self.block_ui and \
                event.value != 'ANY' and event.value != 'NOTHING':
            self.restart()
            return ret

        return ret

    def execute_pmi(self, idx):
        try:
            pm = prefs().pie_menus[self.root_instance.pm_name]
            pmi = pm.pmis[idx]
            if pmi.mode == 'HOTKEY':
                keymap_helper.run_operator_by_hotkey(bpy.context, pmi.text)
            elif pmi.mode == 'COMMAND':
                if idx == 0:
                    PME_OT_sticky_key.exec_globals = pme.context.gen_globals()

                PME_OT_sticky_key.exec_globals.update(
                    menu=pm.name, slot=pmi.name)
                # pme.context.exec_globals = PME_OT_sticky_key.exec_globals
                pme.context.exe(
                    operator_utils.add_default_args(pmi.text),
                    PME_OT_sticky_key.exec_globals)
        except:
            print_exc()

    def invoke(self, context, event):
        pr = prefs()

        if self.pm_name not in pr.pie_menus:
            return {'CANCELLED'}

        if not PME_OT_sticky_key.root_instance:
            if event.value != 'PRESS':
                return {'CANCELLED'}

            PME_OT_sticky_key.root_instance = self
            self.key = event.type
        else:
            if not PME_OT_sticky_key.root_instance.restart_flag and \
                    event.value == 'PRESS' and \
                    event.type == PME_OT_sticky_key.root_instance.key:
                return {'PASS_THROUGH'}

        pm = pr.pie_menus[self.pm_name]
        prop = pme.props.parse(pm.data)
        self.block_ui = prop.sk_block_ui
        self.restart_flag = False
        self.result = None
        self.timer = None
        self.is_pressed = True
        self.idx = PME_OT_sticky_key.idx
        PME_OT_sticky_key.idx += 1

        DBG_STICKY and logh("Sticky Key %d" % self.idx)

        self.root_instance = PME_OT_sticky_key.root_instance

        ret = {'RUNNING_MODAL'}
        if self.is_root_instance:
            self.execute_pmi(0)
            if "return_value" in PME_OT_sticky_key.exec_globals:
                ret = PME_OT_sticky_key.exec_globals["return_value"]
        else:
            # self.is_pressed = False
            self.add_timer(0.02)

        if 'RUNNING_MODAL' in ret:
            context.window_manager.modal_handler_add(self)
        else:
            PME_OT_sticky_key.root_instance = None

        return ret


class PME_OT_sticky_key(PME_OT_sticky_key_base, bpy.types.Operator):
    pass


class PME_OT_timeout(bpy.types.Operator):
    bl_idname = "pme.timeout"
    bl_label = "Timeout"

    cmd: bpy.props.StringProperty(
        name="Python code", description="Python code",
        maxlen=MAX_STR_LEN, options={'SKIP_SAVE', 'HIDDEN'})
    delay: bpy.props.FloatProperty(
        name="Delay (s)", description="Delay in seconds",
        default=0.0001, options={'SKIP_SAVE', 'HIDDEN'})
    # area: bpy.props.EnumProperty(
    #     name="Area",
    #     items=CC.area_type_enum_items(),
    #     options={'SKIP_SAVE'})

    def modal(self, context, event):
        if event.type == 'TIMER':
            if self.cancelled:
                context.window_manager.event_timer_remove(self.timer)
                self.timer = None
                return {'FINISHED'}

            if self.timer.time_duration >= self.delay:
                self.cancelled = True
                if False:
                    pass
                # if self.area != 'CURRENT':
                #     bpy.ops.pme.timeout(
                #         SU.override_context(self.area),
                #         'INVOKE_DEFAULT', cmd=self.cmd, delay=self.delay)
                else:
                    pme.context.exec_operator = self
                    pme.context.exe(self.cmd)
                    pme.context.exec_operator = None
        return {'PASS_THROUGH'}

    def execute(self, context):
        self.cancelled = False

        context.window_manager.modal_handler_add(self)
        self.timer = context.window_manager.event_timer_add(
            self.delay, window=context.window)
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        # if self.area != 'CURRENT':
        #     a = SU.find_area(self.area)
        #     if a:
        #         x, y = event.mouse_x, event.mouse_y
        #         dx = a.x + 20 - x
        #         if dx < 0:
        #             dx += a.width - 40
        #             if dx > 0:
        #                 dx = 0

        #         dy = a.y + 20 - y
        #         if dy < 0:
        #             dy += a.height - 40
        #             if dy > 0:
        #                 dy = 0

        #         context.window.cursor_warp(x + dx, y + dy)

        return self.execute(context)


class PME_OT_restore_mouse_pos(bpy.types.Operator):
    bl_idname = "pme.restore_mouse_pos"
    bl_label = ""
    bl_options = {'INTERNAL'}

    inst = None

    key: bpy.props.StringProperty(options={'SKIP_SAVE'})
    x: bpy.props.IntProperty(options={'SKIP_SAVE'})
    y: bpy.props.IntProperty(options={'SKIP_SAVE'})
    mode: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def modal(self, context, event):
        # prop = pp.parse(pme.context.pm.data)
        # if not prop.pm_flick:
        #     context.window.cursor_warp(self.x, self.y)

        if event.type == 'WINDOW_DEACTIVATE':
            self.stop()
            return {'PASS_THROUGH'}

        if event.type == 'TIMER':
            if self.cancelled:
                if self.__class__.inst == self:
                    self.__class__.inst = None
                context.window_manager.event_timer_remove(self.timer)
                return {'CANCELLED'}

            if self.mode == 0:
                bpy.ops.pme.restore_mouse_pos(
                    'INVOKE_DEFAULT', key=self.key, x=self.x, y=self.y, mode=1)
                context.window_manager.event_timer_remove(self.timer)
                return {'CANCELLED'}

        if self.mode == 1:
            if event.value == 'RELEASE':
                if event.type == self.key:
                    context.window.cursor_warp(self.x, self.y)
                    self.stop()
                    return {'PASS_THROUGH'}

            elif event.value == 'PRESS':
                if event.type == 'ESC' or event.type == 'RIGHTMOUSE':
                    self.stop()
                    return {'PASS_THROUGH'}

        # if not prop.pm_flick:
        #     return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        inst = self.__class__.inst
        if inst:
            inst.stop()

        self.cancelled = False
        self.__class__.inst = self

        context.window_manager.modal_handler_add(self)
        time_step = 0.0001 if self.mode == 0 else 0.05
        self.timer = context.window_manager.event_timer_add(
            time_step, window=context.window)
        return {'RUNNING_MODAL'}

    def stop(self):
        self.cancelled = True


class PME_OT_modal_base:
    bl_idname = "pme.modal"
    bl_label = "PME Modal"
    bl_options = {'REGISTER', 'GRAB_CURSOR', 'BLOCKING'}

    prop_data = PropertyData()
    active = None

    pm_name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def draw(self, context):
        pass

    def execute_pm(self, pm, mode=None):
        update_flag = None
        if mode == 'UPDATE':
            global_update_pmis = []

        for pmi in pm.pmis:
            if not pmi.enabled:
                continue

            if mode == 'UPDATE':
                if pmi == self.update_pmi:
                    update_flag = True
                elif pmi.mode == 'COMMAND' or pmi.mode == 'PROP':
                    update_flag = False

                if pmi.mode == 'UPDATE' and self.update_pmi:
                    if update_flag == False:
                        continue
                    elif update_flag is None:
                        global_update_pmis.append(pmi)
                        continue

            if mode and pmi.mode != mode:
                continue

            # data = pmi.icon.split(",")
            # if key and data[0] != key:
            #     continue

            self.execute_pmi(pmi, mode)

        if mode == 'UPDATE':
            for pmi in global_update_pmis:
                self.execute_pmi(pmi, mode)

        if self.overlay:
            self.overlay.tag_redraw()

    def execute_pmi(self, pmi, mode=None):
        self.exec_globals.update(slot=pmi.name)
        pme.context.exe(
            operator_utils.add_default_args(pmi.text),
            self.exec_globals)

        if mode is None:
            self.update_pmi = pmi
            self.do_update()

    def execute_prop_pmi(self, pmi, delta, data=None):
        pr = prefs()
        self.update_prop_data(pmi)

        delta *= self.prop_data.step

        value, new_value = None, None
        value = pme.context.eval(pmi.text, self.exec_globals)

        if self.prop_data.rna_prop:
            if value is None:
                value = self.prop_data.rna_prop.default

            if self.prop_data.rna_prop:
                if self.prop_data.rna_type == bpy.types.EnumProperty:
                    enums = self.prop_data.rna_prop.enum_items.keys()
                    if value not in enums:
                        message_box(
                            "Can't change '%s' value" %
                            self.prop_data.identifier)
                        return
                    index = enums.index(value) + delta
                    if pr.use_mouse_threshold_enum:
                        index = round(max(0, min(index, len(enums) - 1)))
                    else:
                        index %= len(enums)
                    new_value = enums[index]

                elif self.prop_data.rna_type == bpy.types.IntProperty:
                    new_value = value + delta

                elif self.prop_data.rna_type == bpy.types.FloatProperty:
                    new_value = value + delta

                elif self.prop_data.rna_type == bpy.types.BoolProperty:
                    new_value = delta > 0 \
                        if pr.use_mouse_threshold_bool else not value

        if value is None:
            return

        if new_value is None:
            value_type = type(value)
            if value_type == int:
                new_value = value + delta

            elif value_type == float:
                new_value = value + delta

            elif value_type == bool:
                new_value = delta > 0 \
                    if pr.use_mouse_threshold_bool else not value

        if new_value is not None:
            if isinstance(new_value, (int, float)):
                if new_value > self.prop_data.max:
                    new_value = self.prop_data.max
                elif new_value < self.prop_data.min:
                    new_value = self.prop_data.min

        text = "%s = %s" % (pmi.text, repr(new_value))
        self.exec_globals.update(slot=pmi.name)
        pme.context.exe(text, self.exec_globals)

        self.update_pmi = pmi
        self.do_update()

    def execute(self, context):
        PME_OT_modal_base.active = None
        return {'FINISHED'}

    def stop(self):
        self.overlay.hide()
        area_header_text_set()

    def do_confirm(self, delay=False):
        if delay:
            self.delayed_finish_mode = 'FINISH'
            if not self.timer:
                self.timer = bpy.context.window_manager.event_timer_add(
                    0.01, window=bpy.context.window)

        self.execute_pm(self.pm, 'FINISH')
        self.stop()
        self.finished = True
        return True

    def do_cancel(self, delay=False):
        if delay:
            self.delayed_finish_mode = 'CANCEL'
            if not self.timer:
                self.timer = bpy.context.window_manager.event_timer_add(
                    0.01, window=bpy.context.window)

        self.execute_pm(self.pm, 'CANCEL')
        self.stop()
        self.cancelled = True
        return True

    def do_update(self, update_pmi=None):
        self.execute_pm(self.pm, 'UPDATE')

        cell_idx = 0
        for pmi in self.pm.pmis:
            if not pmi.enabled:
                continue

            if pmi.icon and pmi.icon != 'NONE':
                value, show = self.gen_value(pmi)
                if not show:
                    continue

                self.table.cols[2].cells[cell_idx].update(value)
                cell_idx += 1

        self.table.update()

    def modal(self, context, event):
        pr = prefs()
        self.update_pmi = None
        block_ui = self.pm.mo_block_ui

        pme.context.event = event

        # if not self.has_middle_pmis and event.type == 'MIDDLEMOUSE':
        #     return {'PASS_THROUGH'}
        # elif not self.wheel_pmis and event.type in {
        if not self.wheel_pmis and event.type in {
                'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}

        if event.type == 'TIMER' and self.timer:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None

            if self.delayed_finish_mode:
                self.execute_pm(self.pm, self.delayed_finish_mode)
            else:
                self.execute_pm(self.pm, 'INVOKE')

            if self.finished:
                PME_OT_modal_base.active = None
                return {'FINISHED'}

            elif self.cancelled:
                PME_OT_modal_base.active = None
                return {'CANCELLED'}

            self.update_overlay()
            self.overlay.add_painter(self.table)

        if event.value == 'RELEASE':
            if event.type == self.confirm_key:
                if self.timer:
                    context.window_manager.event_timer_remove(self.timer)
                    self.timer = None

                    if not self.delayed_finish_mode:
                        self.execute_pm(self.pm, 'INVOKE')

                self.do_confirm()
                PME_OT_modal_base.active = None
                return {'FINISHED'}

        if self.timer:
            return {'RUNNING_MODAL'}

        if event.value == 'PRESS' and event.type != 'MOUSEMOVE':
            if self.key:
                return {'RUNNING_MODAL'}

            event_mods = keymap_helper.encode_mods(
                event.ctrl, event.shift, event.alt, event.oskey)
            has_pmi = False
            for pmi, pmi_key, pmi_mods in self.key_pmis:
                # key, _, _, _ = decode_modal_data(pmi)
                if pmi_key != event.type or \
                        pmi_mods != event_mods or \
                        event.type == 'WHEELUPMOUSE' or \
                        event.type == 'WHEELDOWNMOUSE':
                    continue

                has_pmi = True

                if pmi.mode == 'PROP':
                    self.prop_data.clear()
                    if not pr.use_mouse_threshold_bool or \
                            not pr.use_mouse_threshold_enum:
                        self.update_prop_data(pmi)
                        if not pr.use_mouse_threshold_bool and \
                                self.prop_data.rna_type == \
                                bpy.types.BoolProperty or \
                                not pr.use_mouse_threshold_enum and \
                                self.prop_data.rna_type == \
                                bpy.types.EnumProperty:
                            self.execute_prop_pmi(pmi, 1)
                            return {'RUNNING_MODAL'}

                    self.key = event.type
                    self.key_pmi = pmi
                    self.last_mouse = \
                        event.mouse_x if pr.mouse_dir_mode == 'H' else \
                        event.mouse_y

                elif pmi.mode == 'COMMAND':
                    self.execute_pmi(pmi)
                    if self.finished:
                        PME_OT_modal_base.active = None
                        return {'FINISHED'}

                    elif self.cancelled:
                        PME_OT_modal_base.active = None
                        return {'CANCELLED'}

                break

            # if self.move_pmi:
            #     pass

            if has_pmi:
                pass

            elif event.type == 'WHEELUPMOUSE' or \
                    event.type == 'WHEELDOWNMOUSE':
                delta = 1 if event.type == 'WHEELUPMOUSE' else -1
                has_wheel_pmi = False
                for pmi, pmi_mods in self.wheel_pmis:
                    if event_mods == pmi_mods:
                        has_wheel_pmi = True
                        self.prop_data.clear()
                        self.execute_prop_pmi(pmi, delta)

                if not has_wheel_pmi:
                    # self.do_cancel(True)
                    return {'PASS_THROUGH'}

            elif block_ui and event.type in self.confirm_keys:
                self.do_confirm()
                PME_OT_modal_base.active = None
                return {'FINISHED'}

            elif block_ui and event.type in self.cancel_keys:
                self.do_cancel()
                PME_OT_modal_base.active = None
                return {'CANCELLED'}

            elif not block_ui:
                if event.type not in self.skip_event_types:
                    if event.type in self.confirm_keys:
                        self.do_confirm(True)
                    elif event.type in self.cancel_keys:
                        self.do_cancel(True)
                    return {'PASS_THROUGH'}

        if event.value == 'RELEASE':
            if event.type == self.key:
                self.key = None
                self.key_pmi = None

        pmi = self.key_pmi or self.move_pmi
        if event.type == 'MOUSEMOVE' and pmi:
            mouse = \
                event.mouse_x if pr.mouse_dir_mode == 'H' else \
                event.mouse_y

            self.update_prop_data(pmi)
            delta = mouse - self.last_mouse
            if event.ctrl and self.prop_data.is_float:
                delta /= self.prop_data.threshold
                self.last_mouse = mouse
            else:
                if abs(delta) > self.prop_data.threshold:
                    delta = 1 if mouse > self.last_mouse else -1
                    self.last_mouse = mouse
                else:
                    delta = 0

            if delta:
                self.execute_prop_pmi(pmi, delta)

        return {'RUNNING_MODAL'}

    def update_prop_data(self, pmi):
        if self.prop_data.path != pmi.text:
            self.prop_data.init(pmi.text, self.exec_globals)

        if self.prop_data.icon != pmi.icon:
            decode_modal_data(pmi, self.prop_data)

    def gen_value(self, pmi):
        value = " "
        if pmi.mode == 'PROP':
            self.update_prop_data(pmi)
            try:
                if self.prop_data.custom:
                    if self.prop_data.custom == 'HIDDEN':
                        return None, False

                    value = pme.context.eval(
                        self.prop_data.custom, self.exec_globals)
                else:
                    value = pme.context.eval(
                        pmi.text, self.exec_globals)
                    if self.prop_data.rna_prop and \
                            self.prop_data.rna_prop.subtype == 'ANGLE':
                        value = 180 * value / PI
                    if isinstance(value, float):
                        value = "{0:.4f}".format(value).rstrip("0").rstrip(".")
                    if self.prop_data.rna_prop and \
                            self.prop_data.rna_prop.subtype == 'ANGLE':
                        value += "°"
            except:
                print_exc()

        elif pmi.mode == 'COMMAND':
            try:
                _, _, _, _, custom = decode_modal_data(pmi)
                if custom:
                    if custom == 'HIDDEN':
                        return None, False
                    value = pme.context.eval(custom, self.exec_globals)
            except:
                print_exc()

        return str(value), True

    def update_overlay(self):
        self.cells.clear()
        self.cell_indices.clear()

        for i, pmi in enumerate(self.pm.pmis):
            if not pmi.enabled:
                continue

            if pmi.icon and pmi.icon != 'NONE':
                value, show = self.gen_value(pmi)
                if not show:
                    continue

                self.cell_indices.append(len(self.cells) // 3)

                key, _, _, _, _ = decode_modal_data(pmi)
                key, ctrl, shift, alt, oskey, any, _, _ = \
                    keymap_helper.parse_hotkey(key)
                if key == 'WHEELUPMOUSE' and pmi.mode == 'PROP':
                    key = "Wheel"
                elif key == 'MOUSEMOVE' and pmi.mode == 'PROP':
                    key = "Move"
                else:
                    key = to_key_name(key)

                hotkey = ""
                if any:
                    hotkey += "?"
                else:
                    if ctrl:
                        hotkey += "c"
                    if shift:
                        hotkey += "s"
                    if alt:
                        hotkey += "a"
                    if oskey:
                        hotkey += "o"
                if hotkey:
                    hotkey += "+"
                hotkey += key

                self.cells.append(hotkey)
                self.cells.append(pmi.name)
                self.cells.append(value)
            else:
                self.cell_indices.append(None)

        if not self.table:
            self.table = TablePainter(3, self.cells, self.pm.name)
        else:
            self.table.update(self.cells)

    def invoke(self, context, event):
        pr = prefs()
        if self.pm_name not in pr.pie_menus:
            return {'CANCELLED'}

        if PME_OT_modal_base.active:
            return {'CANCELLED'}

        PME_OT_modal_base.active = self
        self.pm = pr.pie_menus[self.pm_name]
        self.key = None
        self.key_pmi = None
        self.key_pmis = []
        self.skip_event_types = {
            'LEFT_CTRL', 'LEFT_SHIFT', 'LEFT_ALT',
            'RIGHT_CTRL', 'RIGHT_SHIFT', 'RIGHT_ALT',
            'OSKEY',
            'INBETWEEN_MOUSEMOVE'
        }
        self.wheel_pmis = []
        self.update_pmis = []
        self.update_pmi = None
        self.move_pmi = None
        self.has_middle_pmis = False
        self.table = None
        self.cells = []
        self.cell_indices = []
        self.overlay = None
        self.finished = False
        self.cancelled = False
        self.delayed_finish_mode = None
        self.confirm_keys = {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}
        self.cancel_keys = {'RIGHTMOUSE', 'ESC'}

        self.prop_data.clear()

        self.confirm_key = None
        prop = pme.props.parse(self.pm.data)
        if prop.confirm and event.value in {'PRESS', 'DOUBLE_CLICK'}:
            self.confirm_key = event.type

        self.last_mouse = \
            event.mouse_x if pr.mouse_dir_mode == 'H' else \
            event.mouse_y

        self.exec_globals = pme.context.gen_globals()
        self.exec_globals.update(
            menu=self.pm.name,
            self=self,
            confirm=self.do_confirm,
            cancel=self.do_cancel,
        )
        pme.context.event = event

        self.timer = context.window_manager.event_timer_add(
            0.01, window=context.window)

        for pmi in self.pm.pmis:
            if not pmi.enabled:
                continue

            if pmi.icon and pmi.icon != 'NONE':
                key, _, _, _, _ = decode_modal_data(pmi)
                key, ctrl, shift, alt, oskey, any, _, _ = \
                    keymap_helper.parse_hotkey(key)
                mods = keymap_helper.encode_mods(ctrl, shift, alt, oskey)
                self.key_pmis.append((pmi, key, mods))
                if not self.move_pmi and key == 'MOUSEMOVE':
                    self.move_pmi = pmi
                elif pmi.mode == 'PROP' and key == 'WHEELUPMOUSE':
                    self.wheel_pmis.append((pmi, mods))
                elif key == 'MIDDLEMOUSE':
                    self.has_middle_pmis = True
                elif pmi.mode == 'UPDATE':
                    self.update_pmis.append((pmi, None))

        self.overlay = Overlay(context.area.type)
        self.overlay.show()

        if prop.lock:
            area_header_text_set(
                self.pm_name +
                ", Confirm: Enter/LMB, Cancel: Esc/RMB")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class PME_OT_modal_grab(PME_OT_modal_base, bpy.types.Operator):
    bl_idname = "pme.modal_grab"


class PME_OT_modal(PME_OT_modal_base, bpy.types.Operator):
    bl_options = {'REGISTER'}


class PME_OT_restore_pie_prefs(bpy.types.Operator, CTU.HeadModalHandler):
    bl_idname = "pme.restore_pie_prefs"
    bl_label = "Internal (PME)"
    bl_options = {'REGISTER'}

    def finish(self):
        prefs().pie_menu_prefs.restore()


class PME_OT_restore_pie_radius(bpy.types.Operator):
    bl_idname = "pme.restore_pie_radius"
    bl_label = "Internal (PME)"
    bl_options = {'INTERNAL'}

    def modal(self, context, event):
        if event.type == 'TIMER':
            if self.timer and self.timer.time_duration > 0:
                context.window_manager.event_timer_remove(self.timer)
                self.timer = None
                prefs().pie_menu_radius.restore()
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        self.timer = context.window_manager.event_timer_add(
            CC.BL_TIMER_STEP, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class WM_OT_pme_user_pie_menu_call(bpy.types.Operator):
    bl_idname = "wm.pme_user_pie_menu_call"
    bl_label = "Call Menu (PME)"
    bl_description = "Call PME menu"
    bl_options = {'INTERNAL'}

    hold_inst = None
    active_ops = {}
    pressed_key = None
    # pm_handler = None
    # pm_handler_type = None
    # pm_handler_time = None

    pie_menu_name: bpy.props.StringProperty(options={'SKIP_SAVE'})
    invoke_mode: bpy.props.StringProperty(options={'SKIP_SAVE'})
    keymap: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    slot: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})

    # @staticmethod
    # def restore_pie_menu_prefs():
    #     tp = WM_OT_pme_user_pie_menu_call
    #     for a in bpy.context.screen.areas:
    #         a.tag_redraw()

    #     if time() > tp.pm_handler_time:
    #         prefs().pie_menu_prefs.restore()

    #         tp.pm_handler_type.draw_handler_remove(
    #             tp.pm_handler, 'WINDOW')
    #         tp.pm_handler = None
    #         tp.pm_handler_type = None

    @staticmethod
    def _draw_item(pr, pm, pmi, idx):
        hidden = pmi.extract_flags()[2]
        pme.context.pm = pm
        pme.context.pmi = pmi
        pme.context.idx = idx

        if not pmi.enabled:
            pass

        elif hidden:
            text, icon, *_ = pmi.parse()
            lh.operator(
                WM_OT_pme_none.bl_idname,
                text, icon, emboss=False)

        elif pmi.mode == 'COMMAND':
            op_bl_idname, args, pos_args = \
                operator_utils.find_operator(pmi.text)

            if op_bl_idname and not pos_args:
                # for i, arg in enumerate(args):
                #     args[i] = "p.%s;" % arg
                # args = "".join(args)

                # p = None
                text, icon, *_ = pmi.parse()
                try:
                    exec("str(bpy.ops.%s.idname)" % op_bl_idname)
                    p = lh.operator(op_bl_idname, text, icon)
                    operator_utils.apply_properties(p, args, pm, pmi)
                except:
                    msg = U.format_exception(0)
                    if msg.startswith(
                            "AttributeError: _bpy.ops.as_string: operator"):
                        msg = msg[36:].capitalize()
                    lh.error(text, msg)
                    # if pm.mode == 'DIALOG':
                    #     text and lh.spacer() or lh.blank()
                    # elif pm.mode == 'PMENU':
                    #     lh.sep()

            else:
                text, icon, *_ = pmi.parse()
                lh.operator(
                    WM_OT_pme_user_command_exec.bl_idname,
                    text, icon, cmd=pmi.text, menu=pm.name, slot=pmi.name)

        elif pmi.mode == 'MENU':
            menu_name, expand_menu, use_frame = U.extract_str_flags(
                pmi.text, F_EXPAND, F_EXPAND)

            if menu_name in pr.pie_menus:
                sub_pm = pr.pie_menus[menu_name]
                if expand_menu:
                    if sub_pm.mode == 'RMENU':
                        text, icon, *_ = pmi.parse()
                        lh.menu(
                            pmi.rm_class, text, icon, use_mouse_over_open=True)

                    elif sub_pm.mode == 'DIALOG':
                        if pm.mode == 'PMENU':
                            if sub_pm.poll(
                                    WM_OT_pme_user_pie_menu_call, bl_context):
                                WM_OT_pme_user_pie_menu_call._draw_slot(
                                    menu_name, use_frame)
                            else:
                                lh.sep()

                        elif sub_pm.poll(
                                WM_OT_pme_user_pie_menu_call, bl_context):
                            lh.save()
                            lh.column()

                            draw_pme_layout(
                                sub_pm, lh.layout,
                                WM_OT_pme_user_pie_menu_call._draw_item)

                            lh.restore()

                elif sub_pm.mode == 'PROPERTY':
                    is_enum = sub_pm.poll_cmd == 'ENUM'
                    # enum_flag = sub_pm.get_data("mulsel")
                    hor_exp = sub_pm.get_data("hor_exp")
                    is_array = sub_pm.get_data("vector") > 1
                    if (is_enum or is_array) and hor_exp:
                        lh.save()
                        sy = lh.layout.scale_y
                        lh.layout.scale_y = 1
                        lh.row()
                        lh.layout.scale_y = sy

                    text, icon, *_ = pmi.parse()
                    lh.prop_compact(
                        pr.props, sub_pm.name, text, icon, toggle=True,
                        expand=sub_pm.get_data("exp"))
                    # if is_enum and not enum_flag:
                    #     lh.prop(pr.props, sub_pm.name, "")
                    # else:
                    #     lh.prop(pr.props, sub_pm.name)

                    if (is_enum or is_array) and hor_exp:
                        lh.restore()

                else:
                    invoke_mode = 'SUB' \
                        if pm.mode == 'PMENU' and sub_pm.mode == 'PMENU' \
                        else 'RELEASE'
                    text, icon, *_ = pmi.parse()
                    lh.operator(
                        WM_OT_pme_user_pie_menu_call.bl_idname,
                        text, icon,
                        pie_menu_name=sub_pm.name, invoke_mode=invoke_mode)

            else:
                text, *_ = pmi.parse()
                lh.error(text, "Menu not found: " + menu_name)
                # if pm.mode == 'DIALOG':
                #     text, icon, *_ = pmi.parse()
                #     text and lh.spacer() or lh.blank()
                # elif pm.mode == 'PMENU':
                #     lh.sep()

        elif pmi.mode == 'PROP':
            text, _, prop = pmi.text.rpartition(".")
            more_text, bracket, custom_prop = prop.rpartition("[")
            if bracket:
                text += "." + more_text
                custom_prop.replace("'", "\"")
                prop = bracket + custom_prop

            obj = None
            bl_icon = None
            exec_globals = pme.context.gen_globals()
            exec_globals.update(menu=pm.name, slot=pmi.name)
            try:
                obj = eval(text, exec_globals)
            except:
                print_exc(text)

            try:
                bl_icon = obj.bl_rna.properties[prop].icon
            except:
                pass

            text, icon, *_, use_cb = pmi.parse()
            toggle = not use_cb
            try:
                if bl_icon != 'NONE' or icon == 'NONE':
                    lh.prop(obj, prop, text, toggle=toggle)
                else:
                    lh.prop(obj, prop, text, icon, toggle=toggle)
            except:
                # lh.error(text)
                print_exc(pmi.text)
                if pm.mode == 'DIALOG':
                    pass
                    # text and lh.spacer() or lh.blank()
                elif pm.mode == 'PMENU':
                    lh.sep()

        elif pmi.mode == 'HOTKEY':
            text, icon, *_ = pmi.parse()
            lh.operator(
                WM_OT_pme_hotkey_call.bl_idname,
                text, icon,
                hotkey=pmi.text)

        elif pmi.mode == 'CUSTOM':
            text, icon, *_ = pmi.parse()
            icon, icon_value = lh.parse_icon(icon)
            pme.context.layout = lh.layout
            pme.context.text = text
            pme.context.icon = icon
            pme.context.icon_value = icon_value

            exec_globals = pme.context.gen_globals()
            exec_globals.update(menu=pm.name, slot=pmi.name)

            try:
                pme.context.exe(pmi.text, exec_globals, use_try=False)
            except:
                lh.error(text)
                # print_exc()
                # if pm.mode == 'DIALOG':
                #     text and lh.spacer() or lh.blank()
                # elif pm.mode == 'PMENU':
                #     lh.sep()

    def _draw_pm(self, menu, context):
        pr = prefs()
        pm = pr.pie_menus[self.pie_menu_name]

        layout = menu.layout.menu_pie()
        # CTU.keep_pie_open(layout)

        lh.lt(
            layout,
            operator_context='INVOKE_DEFAULT')

        for idx in range(0, 8):
            pmi = pm.pmis[idx]
            if not pmi.enabled or pmi.mode == 'EMPTY':
                lh.sep()
                continue

            WM_OT_pme_user_pie_menu_call._draw_item(pr, pm, pmi, idx)

        pmi8 = pm.pmis[8]
        pmi9 = pm.pmis[9]
        if pmi8.mode != 'EMPTY' or pmi9.mode != 'EMPTY':
            layout.separator()
            layout.separator()

        if pmi8.mode != 'EMPTY':
            col = layout.column()
            gap = col.column()
            gap.separator()
            gap.scale_y = pr.pie_extra_slot_gap_size
            lh.lt(
                col.column(),
                operator_context='INVOKE_DEFAULT')
            if pmi8.mode == 'COMMAND':
                lh.layout.scale_y = 1.5
            elif pmi8.mode == 'MENU':
                _, expand_menu, _ = U.extract_str_flags(
                    pmi8.text, F_EXPAND, F_EXPAND)

                if not expand_menu:
                    lh.layout.scale_y = 1.5

            WM_OT_pme_user_pie_menu_call._draw_item(pr, pm, pmi8, 8)
        elif pmi9.mode != 'EMPTY':
            layout.separator()

        if pmi9.mode != 'EMPTY':
            col = layout.column()
            lh.lt(
                col.column(),
                operator_context='INVOKE_DEFAULT')
            if pmi9.mode == 'COMMAND':
                lh.layout.scale_y = 1.5
            elif pmi9.mode == 'MENU':
                _, expand_menu, _ = U.extract_str_flags(
                    pmi9.text, F_EXPAND, F_EXPAND)

                if not expand_menu:
                    lh.layout.scale_y = 1.5

            WM_OT_pme_user_pie_menu_call._draw_item(pr, pm, pmi9, 9)
            gap = col.column()
            gap.separator()
            gap.scale_y = pr.pie_extra_slot_gap_size

    @staticmethod
    def draw_rm(pm, layout):
        pr = prefs()

        tp_name, _, _ = U.extract_str_flags_b(pm.name, CC.F_RIGHT, CC.F_PRE)

        is_header = hasattr(bpy.types, tp_name) and \
            ('_HT_' in tp_name or tp_name.endswith("_editor_menus"))

        if is_header:
            row = layout.row(align=True)
            lh.lt(row, operator_context='INVOKE_DEFAULT')
        else:
            row = layout.row()
            lh.column(row, operator_context='INVOKE_DEFAULT')

        for idx, pmi in enumerate(pm.pmis):
            if not pmi.enabled:
                continue

            if pmi.mode == 'EMPTY':
                if pmi.text == "":
                    lh.sep()
                elif pmi.text == "spacer":
                    lh.label(" ")
                elif pmi.text == "column" and not is_header:
                    lh.column(row, operator_context='INVOKE_DEFAULT')
                elif pmi.text == "label":
                    text, icon, *_ = pmi.parse()
                    lh.label(text, icon)
                continue

            WM_OT_pme_user_pie_menu_call._draw_item(pr, pm, pmi, idx)

    def _draw_rm(self, menu, context):
        pr = prefs()
        self.__class__.draw_rm(pr.pie_menus[self.pie_menu_name], menu.layout)

    @staticmethod
    def _draw_slot(name, use_frame=None):
        pm = prefs().pie_menus[name]
        # prop = pme.props.parse(pm.data)

        lh.save()
        layout = lh.layout
        # if prop.pd_box:
        if use_frame:
            column = layout.box()
        else:
            column = layout
        layout = lh.column(column)

        draw_pme_layout(pm, layout, WM_OT_pme_user_pie_menu_call._draw_item)

        lh.restore()

    def _draw_popup_dialog(self, menu, context):
        pm = prefs().pie_menus[self.pie_menu_name]
        prop = pme.props.parse(pm.data)

        layout = menu.layout.menu_pie()
        layout.separator()
        layout.separator()

        if prop.pd_box:
            column = layout.box()
        else:
            column = layout
        column = column.column(align=True)
        lh.lt(column)

        draw_pme_layout(pm, column, WM_OT_pme_user_pie_menu_call._draw_item)

    def cancel(self, context):
        pass

    def check(self, context):
        return True

    def modal(self, context, event):
        pr = prefs()
        pm = pr.pie_menus[self.pie_menu_name]

        if pm.mode == 'PMENU' and not pm.get_data("pm_flick"):
            ret = {'PASS_THROUGH'}
        else:
            ret = {'RUNNING_MODAL'}

        if event.type != 'TIMER' and (
                event.value == 'PRESS' or event.value == 'NOTHING'):
            if self.pm_chord and not self.cancelled and \
                    event.type not in \
                    {'MOUSEMOVE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                for v in self.chord_pms:
                    if v.chord == event.type:
                        self.modal_stop()
                        if pr.use_chord_hint:
                            area_header_text_set()

                        bpy.ops.wm.pme_user_pie_menu_call(
                            'INVOKE_DEFAULT', pie_menu_name=v.name,
                            invoke_mode='CHORDS')
                        return {'CANCELLED'}
                else:
                    self.cancelled = True
                    if pr.use_chord_hint:
                        area_header_text_set()

                    return {'PASS_THROUGH'}

            if self.pm_tweak and event.type == 'MOUSEMOVE' and \
                    self.invoke_mode == 'HOTKEY':
                tt = getattr(
                    uprefs().inputs,
                    "drag_threshold" if is_28() else "tweak_threshold")
                if abs(self.x - event.mouse_x) > tt or \
                        abs(self.y - event.mouse_y) > tt:
                    self.modal_stop()
                    self.executed = True
                    if not self.cancelled:
                        context.window.cursor_warp(self.mouse_x, self.mouse_y)
                        pme.context.add_global(
                            "drag_x", event.mouse_x - self.x)
                        pme.context.add_global(
                            "drag_y", event.mouse_y - self.y)
                        bpy.ops.wm.pme_user_pie_menu_call(
                            'INVOKE_DEFAULT', pie_menu_name=self.pm_tweak.name,
                            invoke_mode='TWEAK')
                        context.window.cursor_warp(
                            event.mouse_x, event.mouse_y)
                    return {'CANCELLED'}

        elif event.value == 'RELEASE' and \
                event.type == self.__class__.pressed_key:
            if self.hold_timer or self.pm_tweak:
                if self.pm_press:
                    DBG_PM and logi("HOLD - RELEASE", self)

                    if self.pm_press.mode == 'SCRIPT':
                        StackKey.next(self.pm_press)

                    elif self.pm_press.mode == 'STICKY':
                        self.pm_press = None

                    elif self.pm_press.mode == 'MACRO':
                        execute_macro(self.pm_press)

                    else:
                        bpy.ops.wm.pme_user_pie_menu_call(
                            'INVOKE_DEFAULT', pie_menu_name=self.pm_press.name,
                            invoke_mode='RELEASE')
                else:
                    DBG_PM and logi("HOLD - DEFAULT", self)
                    keymap_helper.run_operator(
                        context, pm.key,
                        pm.ctrl, pm.shift, pm.alt, pm.oskey, pm.key_mod)

                self.hold_timer = None
                self.__class__.hold_inst = None
                return self.modal_stop()

            self.key_is_released = True
            self.__class__.pressed_key = None
            return ret

        elif event.type == 'TIMER':
            if self.chord_timer and (
                    self.cancelled or
                    self.chord_timer.finished() or self.chord_timer.update()):
                self.chord_timer = None
                if pr.use_chord_hint:
                    area_header_text_set()

                return self.modal_stop()

            if self.hold_timer and (
                    self.hold_timer.finished() or self.hold_timer.update()):

                if self.__class__.hold_inst == self:
                    self.__class__.hold_inst = None

                self.hold_timer = None
                self.modal_stop()
                self.executed = True
                if not self.cancelled:
                    context.window.cursor_warp(self.mouse_x, self.mouse_y)
                    bpy.ops.wm.pme_user_pie_menu_call(
                        'INVOKE_DEFAULT', pie_menu_name=self.pm_hold.name,
                        invoke_mode='HOLD')
                    context.window.cursor_warp(event.mouse_x, event.mouse_y)
                return {'CANCELLED'}

            if self.pm_timer and (
                    self.pm_timer.finished() or self.pm_timer.update()):
                if self.key_is_released:
                    DBG_PM and logi("RELEASE", self)
                    for op in self.__class__.active_ops.values():
                        DBG_PM and logi("-", op.pie_menu_name)
                        op.key_is_released = True

                if self.key_is_released or self.cancelled:
                    if self.cancelled:
                        DBG_PM and logi("CANCELLED", self)
                    self.pm_timer = None
                    return self.modal_stop()

            if self.bl_timer and self.bl_timer.time_duration > 5:
                if self.pm_timer:
                    self.pm_timer = None
                return self.modal_stop()

        if pm.mode == 'PMENU' and not pme.props.parse(pm.data).pm_flick and (
                self.invoke_mode == 'HOTKEY' or self.invoke_mode == 'HOLD' or
                self.invoke_mode == 'TWEAK'):
            return {'RUNNING_MODAL'}

        return ret

    def modal_start(self, add_timer=True):
        wm = bpy.context.window_manager
        if add_timer:
            self.bl_timer = wm.event_timer_add(
                0.05, window=bpy.context.window)
        wm.modal_handler_add(self)
        DBG_PM and logi("START", self)
        if self.pie_menu_name in self.__class__.active_ops:
            self.__class__.active_ops[self.pie_menu_name].cancelled = True
        self.__class__.active_ops[self.pie_menu_name] = self
        return {'RUNNING_MODAL'}

    def modal_stop(self):
        DBG_PM and logi("STOP", self)
        if self.bl_timer:
            bpy.context.window_manager.event_timer_remove(self.bl_timer)
        self.bl_timer = None
        if self.pie_menu_name in self.__class__.active_ops and \
                self.__class__.active_ops[self.pie_menu_name] == self:
            del self.__class__.active_ops[self.pie_menu_name]
        return {'CANCELLED'}

    def stop(self):
        self.cancelled = True

    def execute(self, context):
        return {'CANCELLED'}

    def execute_menu(self, context, event):
        self.executed = True
        pme.context.reset()
        bl_context.reset(context)

        wm = context.window_manager
        pr = prefs()
        pm = pr.pie_menus[self.pie_menu_name]
        DBG_PM and logi("EXE_MENU", pm)

        if pm.mode == 'PMENU':
            flick = pme.props.parse(pm.data).pm_flick
            view = uprefs().view
            if context.space_data:
                prop = pme.props.parse(pm.data)
                radius = int(prop.pm_radius)
                confirm = int(prop.pm_confirm)
                threshold = int(prop.pm_threshold)

                if not flick:
                    confirm = -1
                    threshold = -1

                if radius == -1:
                    radius = view.pie_menu_radius
                if confirm == -1:
                    confirm = pr.pie_menu_prefs.confirm
                if threshold == -1:
                    threshold = pr.pie_menu_prefs.threshold

                self.restore_radius = False
                if view.pie_menu_radius != radius:
                    pr.pie_menu_radius.save()
                    self.restore_radius = True
                    view.pie_animation_timeout = 0
                    view.pie_menu_radius = radius

                restore_prefs = False
                if self.invoke_mode == 'HOTKEY' and (
                        view.pie_menu_confirm != confirm or
                        view.pie_menu_threshold != threshold):
                    pr.pie_menu_prefs.save()
                    view.pie_menu_confirm = confirm
                    view.pie_menu_threshold = threshold
                    restore_prefs = True

            DBG_PM and logi("SHOW", self)
            wm.popup_menu_pie(
                event, self._draw_pm,
                title=pm.name if pr.show_pm_title else "")

            if context.space_data:
                if restore_prefs:
                    bpy.ops.pme.restore_pie_prefs(
                        'INVOKE_DEFAULT', key=event.type)

                if self.restore_radius:
                    bpy.ops.pme.timeout(
                        'INVOKE_DEFAULT',
                        delay=0.05 if flick else 0.1,
                        cmd="prefs().pie_menu_radius.restore()")

                if not flick:
                    self.pm_timer = Timer(
                        0.05 + view.pie_animation_timeout / 100)
                    return self.modal_start()

            return {'CANCELLED'}

        elif pm.mode == 'RMENU':
            prop = pme.props.parse(pm.data)
            if prop.rm_title:
                context.window_manager.popup_menu(self._draw_rm, title=pm.name)
            else:
                context.window_manager.popup_menu(self._draw_rm)

        elif pm.mode == 'DIALOG':
            prop = pme.props.parse(pm.data)
            if prop.pd_panel:
                bpy.ops.wm.pme_user_dialog_call(
                    'INVOKE_DEFAULT',
                    pie_menu_name=self.pie_menu_name,
                    auto_close=prop.pd_panel == 2,
                    hide_title=not prop.pd_title,
                    width=int(prop.pd_width))
            else:
                popup_dialog_pie(event, self._draw_popup_dialog)

        elif pm.mode == 'SCRIPT':
            StackKey.next(pm, self.slot)

        elif pm.mode == 'STICKY':
            bpy.ops.pme.sticky_key('INVOKE_DEFAULT', pm_name=pm.name)

        elif pm.mode == 'MACRO':
            execute_macro(pm)

        elif pm.mode == 'MODAL':
            prop = pme.props.parse(pm.data)
            if prop.lock:
                bpy.ops.pme.modal_grab('INVOKE_DEFAULT', pm_name=pm.name)
            else:
                bpy.ops.pme.modal('INVOKE_DEFAULT', pm_name=pm.name)

        return {'CANCELLED'}

    def __str__(self):
        return "%s (%s)" % (self.pie_menu_name, self.invoke_mode)

    def _parse_open_mode(self, pm):
        if pm.open_mode == 'HOLD':
            self.pm_hold = pm
        elif pm.open_mode == 'PRESS':
            self.pm_press = pm
        elif pm.open_mode == 'CHORDS':
            self.pm_chord = pm
            self.chord_pms = []
            for v in prefs().pie_menus:
                if v.chord and \
                        keymap_helper.compare_km_names(
                            self.keymap, v.km_name) and \
                        v.open_mode == 'CHORDS' and \
                        v.chord != 'NONE' and \
                        pm.key == v.key and \
                        pm.any == v.any and \
                        pm.ctrl == v.ctrl and \
                        pm.shift == v.shift and \
                        pm.alt == v.alt and \
                        pm.oskey == v.oskey:
                    self.chord_pms.append(v)

        elif pm.open_mode == 'TWEAK' and self.invoke_mode == 'HOTKEY':
            self.pm_tweak = pm

    def invoke(self, context, event):
        pr = prefs()
        pme.context.last_operator = self
        pme.context.event = event

        DBG_PM and logh(self.pie_menu_name)

        if self.pie_menu_name not in pr.pie_menus:
            DBG_PM and loge("!PM")
            return {'CANCELLED'}

        cpm = pr.pie_menus[self.pie_menu_name]
        pme.context.pm = cpm

        self.bl_timer = None
        self.pm_press, self.pm_hold, self.pm_tweak, self.pm_chord = \
            None, None, None, None

        if self.invoke_mode == 'HOTKEY' and \
                not cpm.poll(self.__class__, context):
            return {'PASS_THROUGH'}

        if cpm.open_mode == 'HOLD' and cpm.mode == 'STICKY' and \
                PME_OT_sticky_key.root_instance:
            return {'CANCELLED'}

        self.mouse_x, self.mouse_y = event.mouse_x, event.mouse_y

        if self.invoke_mode == 'HOTKEY' and cpm.key_mod == 'NONE':
            cpm_key = keymap_helper.to_system_mouse_key(cpm.key, context)
            for pm in reversed(pr.pie_menus):
                if pm == cpm:
                    continue

                pm_key = keymap_helper.to_system_mouse_key(pm.key, context)
                if pm.enabled and \
                        pm_key == cpm_key and pm.ctrl == cpm.ctrl and \
                        pm.shift == cpm.shift and pm.alt == cpm.alt and \
                        pm.oskey == cpm.oskey and \
                        pm.key_mod in MOUSE_BUTTONS and \
                        is_key_pressed(pm.key_mod):
                    self.pie_menu_name = pm.name
                    cpm = pm
                    break

        self.mouse_button_mod = cpm.key_mod in MOUSE_BUTTONS and cpm.key_mod
        if self.mouse_button_mod:
            if cpm.key == self.mouse_button_mod:
                return {'CANCELLED'}

            if not is_key_pressed(cpm.key_mod):
                return {'PASS_THROUGH'}

            if self.__class__.hold_inst:
                self.__class__.hold_inst.stop()

        if self.invoke_mode == 'RELEASE':
            self.__class__.pressed_key = None
            for op in self.__class__.active_ops.values():
                op.key_is_released = True

        elif self.invoke_mode == 'HOTKEY':
            self.__class__.pressed_key = \
                keymap_helper.to_system_mouse_key(
                    event.type, context)

            if self.pie_menu_name in self.__class__.active_ops:
                apm = self.__class__.active_ops[self.pie_menu_name]
                if not apm.executed:
                    return {'CANCELLED'}

                self.__class__.active_ops[
                    self.pie_menu_name].cancelled = True

        self._parse_open_mode(cpm)

        if self.invoke_mode == 'HOTKEY':
            for pm in pr.pie_menus:
                if pm != cpm and pm.enabled and \
                        keymap_helper.compare_km_names(
                            self.keymap, pm.km_name) and \
                        pm.key == cpm.key and \
                        pm.ctrl == cpm.ctrl and \
                        pm.shift == cpm.shift and \
                        pm.alt == cpm.alt and \
                        pm.oskey == cpm.oskey and \
                        pm.key_mod == cpm.key_mod and \
                        pm.open_mode != cpm.open_mode:
                    self._parse_open_mode(pm)

        if cpm.mode == 'PMENU' and pr.restore_mouse_pos:
            if self.invoke_mode == 'TWEAK' and cpm.open_mode == 'TWEAK' or \
                    self.invoke_mode == 'HOLD' and cpm.open_mode == 'HOLD' or \
                    not PME_OT_restore_mouse_pos.inst:
                bpy.ops.pme.restore_mouse_pos(
                    'INVOKE_DEFAULT',
                    key=event.type, x=event.mouse_x, y=event.mouse_y)
            elif self.invoke_mode == 'SUB':
                inst = PME_OT_restore_mouse_pos.inst
                if inst:
                    bpy.ops.pme.restore_mouse_pos(
                        'INVOKE_DEFAULT',
                        key=inst.key, x=inst.x, y=inst.y)

        if self.pm_hold and cpm.open_mode in {'PRESS', 'TWEAK'}:
            cpm = self.pm_hold
            self.pie_menu_name = self.pm_hold.name

        elif self.pm_tweak and cpm.open_mode == 'PRESS':
            cpm = self.pm_tweak
            self.pie_menu_name = self.pm_tweak.name

        if self.invoke_mode == 'HOTKEY':
            if self.pie_menu_name in self.__class__.active_ops:
                return {'PASS_THROUGH'}

        DBG_PM and logi("INVOKE", self, cpm.open_mode)

        if self.invoke_mode == 'RELEASE':
            if self.pie_menu_name in self.__class__.active_ops:
                self.__class__.active_ops[self.pie_menu_name].cancelled = True

        self.executed = False
        self.pm_timer = None
        self.hold_timer = None
        self.chord_timer = None
        self.cancelled = False
        self.key_is_released = self.__class__.pressed_key is None
        self.release_timer = None

        self.x = event.mouse_x
        self.y = event.mouse_y

        if self.invoke_mode == 'HOTKEY':
            if cpm.open_mode == 'HOLD':
                self.hold_timer = Timer(pr.hold_time / 1000)
                self.__class__.hold_inst = self
                return self.modal_start()

            elif cpm.open_mode == 'TWEAK':
                return self.modal_start(False)

            elif cpm.open_mode == 'CHORDS':
                self.chord_timer = Timer(pr.chord_time / 1000)
                if pr.use_chord_hint:
                    area_header_text_set(
                        "Waiting next key chord in the sequence: " +
                        ", ".join(sorted(
                            {keymap_helper.key_names[v.chord]
                                for v in self.chord_pms})))
                return self.modal_start()

        return self.execute_menu(context, event)


class WM_OT_pme_user_dialog_call(bpy.types.Operator, PopupOperator):
    bl_idname = "wm.pme_user_dialog_call"
    bl_label = ""
    bl_options = {'INTERNAL'}

    pie_menu_name: bpy.props.StringProperty(
        name="Popup Dialog Name",
        description="Popup Dialog name")

    def draw(self, context):
        pm = prefs().pie_menus[self.pie_menu_name]
        layout = PopupOperator.draw(self, context, pm.name)

        column = layout.column(align=True)
        lh.lt(column)

        draw_pme_layout(pm, column, WM_OT_pme_user_pie_menu_call._draw_item)

    def invoke(self, context, event):
        pr = prefs()
        if self.pie_menu_name not in pr.pie_menus:
            return {'CANCELLED'}

        pme.context.event = event

        return PopupOperator.invoke(self, context, event)


class WM_OT_pme_keyconfig_wait(bpy.types.Operator):
    bl_idname = "wm.pme_keyconfig_wait"
    bl_label = ""
    bl_options = {'INTERNAL'}

    def modal(self, context, event):
        pr = prefs()
        if event.type == 'TIMER':
            keymaps = bpy.context.window_manager.keyconfigs.user.keymaps
            registered_kms = []
            for km in pr.missing_kms:
                if km in keymaps:
                    registered_kms.append(km)
            for km in registered_kms:
                pr.missing_kms.remove(km)

            if not pr.missing_kms or self.t.update():
                while pr.unregistered_pms:
                    pr.unregistered_pms.pop().register_hotkey()
                context.window_manager.event_timer_remove(self.timer)
                self.timer = None
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        self.t = Timer(10)
        self.timer = context.window_manager.event_timer_add(
            0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class WM_OT_pmi_submenu_select(bpy.types.Operator):
    bl_idname = "wm.pmi_submenu_select"
    bl_label = ""
    bl_description = "Select a menu"
    bl_options = {'INTERNAL'}
    bl_property = "enumprop"

    def get_items(self, context):
        pr = prefs()
        return [(k, k, "") for k in sorted(pr.pie_menus.keys())]

    pm_item: bpy.props.IntProperty()
    enumprop: bpy.props.EnumProperty(items=get_items)

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.pm_item]
        pmi.mode = 'MENU'
        pmi.name = self.enumprop
        pmi.text = self.enumprop

        tag_redraw()

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_addonpref_search(bpy.types.Operator):
    bl_idname = "pme.addonpref_search"
    bl_label = ""
    bl_description = "Open addon preferences in a popup"
    bl_options = {'INTERNAL'}
    bl_property = "enumprop"

    items = None

    def get_items(self, context):
        cl = PME_OT_addonpref_search
        if not cl.items:
            cl.items = []
            import addon_utils
            for addon in uprefs().addons:
                if hasattr(addon.preferences, "draw"):
                    mod = addon_utils.addons_fake_modules.get(addon.module)
                    if not mod:
                        continue
                    info = addon_utils.module_bl_info(mod)
                    cl.items.append((addon.module, info["name"], ""))

        return cl.items

    enumprop: bpy.props.EnumProperty(items=get_items)

    def execute(self, context):
        pr = prefs()
        if pr.pmi_data.mode not in MODAL_CMD_MODES:
            pr.pmi_data.mode = 'COMMAND'
        pr.pmi_data.cmd = ""
        pr.pmi_data.cmd += (
            "bpy.ops.pme.popup_addon_preferences("
            "addon='%s', center=True)"
        ) % self.enumprop

        sname = ""
        for item in PME_OT_addonpref_search.items:
            if item[0] == self.enumprop:
                sname = item[1]
                break

        pr.pmi_data.sname = sname

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        self.__class__.items = None
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_pmi_custom_set(bpy.types.Operator):
    bl_idname = "pme.pmi_custom_set"
    bl_label = ""
    bl_description = (
        "Draw custom layout of widgets"
    )
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(items=(
        ('LABEL', "Label", "", 'SYNTAX_OFF', 0),
        ('PALETTES', "Palettes", "", 'COLOR', 1),
        ('ACTIVE_PALETTE', "Active Palette", "", 'COLOR', 2),
        ('COLOR_PICKER', "Color Picker", "", 'COLOR', 3),
        ('BRUSH', "Brush", "", 'BRUSH_DATA', 4),
        ('BRUSH_COLOR', "Brush Color", "", 'COLOR', 5),
        ('BRUSH_COLOR2', "Brush Color 2", "", 'COLOR', 6),
        ('OBJ_DATA', "Object Data", "", 'OUTLINER_OB_MESH', 7),
        ('TEXTURE', "Texture", "", 'TEXTURE', 8),
        ('TEXTURE_MASK', "Texture Mask", "", 'TEXTURE', 9),
        ('RECENT_FILES', "Recent Files", "", 'FILE_FOLDER', 10),
        ('MODIFIERS', "Modifiers Panel", "", 'MODIFIER', 11),
    ))

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        lt = "L.box()" if pm.mode == 'PMENU' else "L"
        sep = "L.separator()" if pm.mode == 'PMENU' else "None"

        pr.pmi_data.mode = 'CUSTOM'

        if self.mode == 'LABEL':
            pr.pmi_data.custom = (
                "%s.label(text=text, icon=icon, icon_value=icon_value)"
            ) % lt

        if self.mode == 'PALETTES':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "%s.template_ID(ps, 'palette', new='palette.new') "
                "if ps else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Palettes"

        elif self.mode == 'ACTIVE_PALETTE':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "%s.template_palette(ps, 'palette', color=True) "
                "if ps else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Active Palette"

        elif self.mode == 'COLOR_PICKER':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "unified_paint_panel().prop_unified_color_picker("
                "%s, bl_context, ps.brush, 'color') "
                "if ps and ps.brush else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Color Picker"

        elif self.mode == 'BRUSH':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "%s.template_ID_preview(ps, "
                "'brush', new='brush.add', rows=3, cols=8) "
                "if ps else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Brush"

        elif self.mode == 'BRUSH_COLOR':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "unified_paint_panel().prop_unified_color("
                "%s, bl_context, ps.brush, 'color') "
                "if ps and ps.brush else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Color"

        elif self.mode == 'BRUSH_COLOR2':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "unified_paint_panel().prop_unified_color("
                "%s, bl_context, ps.brush, 'secondary_color') "
                "if ps and ps.brush else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Secondary Color"

        elif self.mode == 'OBJ_DATA':
            pr.pmi_data.custom = (
                "ao = C.active_object; "
                "%s.template_ID(ao, 'data') "
                "if ao else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Object Data"

        elif self.mode == 'TEXTURE':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "%s.template_ID_preview(ps.brush, "
                "'texture', new='texture.new', rows=3, cols=8) "
                "if ps and ps.brush else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Texture"

        elif self.mode == 'TEXTURE_MASK':
            pr.pmi_data.custom = (
                "ps = paint_settings(); "
                "%s.template_ID_preview(ps.brush, "
                "'mask_texture', new='texture.new', rows=3, cols=8) "
                "if ps and ps.brush else %s"
            ) % (lt, sep)
            pr.pmi_data.sname = "Texture Mask"

        elif self.mode == 'RECENT_FILES':
            recent_files_menu = "INFO_MT_file_open_recent"
            if is_28():
                recent_files_menu = "TOPBAR_MT_file_open_recent"

            pr.pmi_data.custom = (
                "L.menu('%s', "
                "text=text, icon=icon, icon_value=icon_value)"
            ) % recent_files_menu
            pr.pmi_data.icon = 'FILE_FOLDER'
            pr.pmi_data.sname = "Recent Files"

        elif self.mode == 'MODIFIERS':
            pr.pmi_data.custom = (
                "panel(\"DATA_PT_modifiers\", frame=True, header=True)"
            )
            pr.pmi_data.sname = "Modifiers Panel"
            pr.pmi_data.icon = 'MODIFIER'

        return {'FINISHED'}


class PME_OT_preview(bpy.types.Operator):
    bl_idname = "pme.preview"
    bl_label = ""
    bl_description = "Preview"
    bl_options = {'INTERNAL'}

    pie_menu_name: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.wm.pme_user_pie_menu_call(
            'INVOKE_DEFAULT', pie_menu_name=self.pie_menu_name,
            invoke_mode='RELEASE')
        return {'FINISHED'}


class PME_OT_docs(bpy.types.Operator):
    bl_idname = "pme.docs"
    bl_label = "Pie Menu Editor Documentation"
    bl_description = "Documentation"
    bl_options = {'INTERNAL'}

    id: bpy.props.StringProperty(options={'SKIP_SAVE'})
    url: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        if self.id:
            self.url = (
                "https://en.blender.org/index.php/User:Raa/"
                "Addons/Pie_Menu_Editor"
            ) + self.id
        bpy.ops.wm.url_open(url=self.url)
        return {'FINISHED'}


class PME_OT_pmi_pm_search(bpy.types.Operator):
    bl_idname = "pme.pmi_pm_search"
    bl_label = ""
    bl_description = "Open/execute/draw a menu, popup or operator"
    bl_options = {'INTERNAL'}
    bl_property = "enumprop"

    items = None

    def get_items(self, context):
        pr = prefs()
        if not PME_OT_pmi_pm_search.items:
            if PME_OT_pmi_pm_search.items is None:
                PME_OT_pmi_pm_search.items = []

            items = PME_OT_pmi_pm_search.items
            for pm in sorted(pr.pie_menus.keys()):
                if self.custom and pr.pie_menus[pm].mode != 'DIALOG':
                    continue
                items.append((pm, pm, ""))

            PME_OT_pmi_pm_search.items = items

        return PME_OT_pmi_pm_search.items

    enumprop: bpy.props.EnumProperty(items=get_items)
    custom: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()

        if self.custom:
            pr.pmi_data.mode = 'CUSTOM'
            pr.pmi_data.custom = "draw_menu(\"%s\")" % self.enumprop
        else:
            if pr.pmi_data.mode not in MODAL_CMD_MODES:
                pr.pmi_data.mode = 'COMMAND'
            pr.pmi_data.cmd = "open_menu(\"%s\")" % self.enumprop

        pr.pmi_data.sname = self.enumprop

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        if PME_OT_pmi_pm_search.items:
            PME_OT_pmi_pm_search.items.clear()
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_pmi_operator_search(bpy.types.Operator):
    bl_idname = "pme.pmi_operator_search"
    bl_label = ""
    bl_description = (
        "Command tab:\n"
        "  Execute operator when the user clicks the button"
    )
    bl_options = {'INTERNAL'}
    bl_property = "operator"

    idx: bpy.props.IntProperty(options={'SKIP_SAVE'})

    items = []

    def get_items(self, context):
        if not PME_OT_pmi_operator_search.items:
            items = []
            for op_module_name in dir(bpy.ops):
                op_module = getattr(bpy.ops, op_module_name)
                for op_submodule_name in dir(op_module):
                    op = getattr(op_module, op_submodule_name)
                    op_name = operator_utils.get_rna_type(op).bl_rna.name

                    label = op_name or op_submodule_name
                    label = "%s|%s" % (utitle(label), op_module_name.upper())

                    items.append((
                        "%s.%s" % (op_module_name, op_submodule_name),
                        label, ""))

            PME_OT_pmi_operator_search.items = items

        return PME_OT_pmi_operator_search.items

    operator: bpy.props.EnumProperty(items=get_items)

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.idx]

        op_name = operator_utils.operator_label(self.operator)

        if pr.mode == 'PMI':
            if pr.pmi_data.mode not in MODAL_CMD_MODES:
                pr.pmi_data.mode = 'COMMAND'

            pr.pmi_data.cmd = "bpy.ops.%s()" % self.operator
            pr.pmi_data.sname = op_name or self.operator
        else:
            if pmi.mode not in MODAL_CMD_MODES:
                pmi.mode = 'COMMAND'

            pmi.text = "bpy.ops.%s()" % self.operator
            pmi.name = op_name or self.operator

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_pmi_panel_search(bpy.types.Operator):
    bl_idname = "pme.pmi_panel_search"
    bl_label = "Panel"
    bl_description = "Open or draw the panel in a popup"
    bl_options = {'INTERNAL'}
    bl_property = "enumprop"

    items = None

    def get_items(self, context):
        if not PME_OT_pmi_panel_search.items:
            PME_OT_pmi_panel_search.items = bl_panel_enum_items()

        return PME_OT_pmi_panel_search.items

    enumprop: bpy.props.EnumProperty(items=get_items)
    custom: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    popover: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        tp = hidden_panel(self.enumprop) or \
            getattr(bpy.types, self.enumprop, None)

        if not tp:
            return {'CANCELLED'}

        pr.pmi_data.mode = 'CUSTOM' if self.custom or self.popover \
            else 'COMMAND'

        if self.popover:
            pr.pmi_data.custom = (
                "L.popover("
                "panel='%s', "
                "text=slot, icon=icon, icon_value=icon_value)"
            ) % self.enumprop

        elif pr.pmi_data.mode == 'COMMAND':
            pr.pmi_data.cmd = (
                "bpy.ops.pme.popup_panel("
                "panel='%s')"
            ) % self.enumprop

        elif pr.pmi_data.mode == 'CUSTOM':
            frame = header = True
            if self.enumprop == "DATA_PT_modifiers" or \
                    self.enumprop == "OBJECT_PT_constraints" or \
                    self.enumprop == "BONE_PT_constraints":
                frame = header = False

            pr.pmi_data.custom = \
                "panel(\"%s\", frame=%r, header=%r, expand=None)" % (
                    self.enumprop, frame, header)

        sname = tp.bl_label if hasattr(
            tp, "bl_label") and tp.bl_label else self.enumprop
        if "_PT_" in sname:
            _, _, sname = sname.partition("_PT_")
            sname = utitle(sname)
        pr.pmi_data.sname = sname

        return {'CANCELLED'}

    def invoke(self, context, event):
        PME_OT_pmi_panel_search.items = None
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_pmi_area_search(bpy.types.Operator):
    bl_idname = "pme.pmi_area_search"
    bl_label = "Area"
    bl_description = "Open/toggle area"
    bl_options = {'INTERNAL'}

    area: bpy.props.EnumProperty(
        items=CC.area_type_enum_items(),
        options={'SKIP_SAVE'})
    cmd: bpy.props.StringProperty(
        default="bpy.ops.pme.popup_area(area='%s')",
        options={'SKIP_SAVE'})

    def draw_pmi_area_search(self, menu, context):
        for item in CC.area_type_enum_items(current=False):
            operator(
                menu.layout, self.bl_idname, item[1], item[3],
                area=item[0], cmd=self.cmd)

    def execute(self, context):
        pr = prefs()

        for item in CC.area_type_enum_items():
            if item[0] == self.area:
                break

        pr.pmi_data.mode = 'COMMAND'
        pr.pmi_data.cmd = self.cmd % self.area

        pr.pmi_data.sname = item[1]

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.popup_menu(
            self.draw_pmi_area_search, title="Area")
        return {'FINISHED'}


class WM_OT_pmidata_hints_show(bpy.types.Operator):
    bl_idname = "wm.pmidata_hints_show"
    bl_label = ""
    bl_description = "Hints"
    bl_options = {'INTERNAL'}

    def _draw(self, menu, context):
        pr = prefs()
        lh.lt(menu.layout)
        row = lh.row()

        pm = pr.selected_pm
        mode = 'COMMAND' if pm.mode in {'SCRIPT', 'STICKY', 'MACRO'} else \
            pr.pmi_data.mode

        lh.column(row)
        lh.label("Variables", 'INFO')
        lh.sep()
        lh.label("C = bpy.context", 'LAYER_USED')
        lh.label("D = bpy.data", 'LAYER_USED')
        lh.label("T = bpy.types", 'LAYER_USED')
        lh.label("P = bpy.props", 'LAYER_USED')

        if mode == 'CUSTOM':
            lh.label("L = layout", 'LAYER_USED')
            lh.label("text", 'LAYER_USED')
            lh.label("icon", 'LAYER_USED')
            lh.label("icon_value", 'LAYER_USED')
        else:
            lh.label("O = bpy.ops", 'LAYER_USED')

        lh.column(row)
        lh.label("Functions", 'INFO')
        lh.sep()
        lh.label("execute_script(filepath)", 'LAYER_ACTIVE')

        if mode != 'CUSTOM':
            lh.label("open_menu(name)", 'LAYER_ACTIVE')

        if mode == 'CUSTOM':
            lh.label("paint_settings(context)", 'LAYER_ACTIVE')
            lh.label("panel(type, frame=True, header=True)", 'LAYER_ACTIVE')

    def execute(self, context):
        context.window_manager.popup_menu(self._draw)

        return {'FINISHED'}


class PME_OT_pmidata_specials_call(bpy.types.Operator):
    bl_idname = "pme.pmidata_specials_call"
    bl_label = ""
    bl_description = "Examples"
    bl_options = {'INTERNAL'}

    def _draw(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        # lh.operator(
        #     WM_OT_pmidata_hints_show.bl_idname, "Hints", 'QUESTION')

        # lh.sep()

        pr = prefs()
        pm = pr.selected_pm
        mode = pr.pmi_data.mode

        row = lh.row(align=False)
        lh.column(align=False)

        lh.label(text="Examples:", icon='HELP')
        lh.label(text="Command Tab")
        lh.sep()

        lh.operator(
            PME_OT_script_open.bl_idname,
            "Call External Script", 'FILE_FOLDER',
            idx=pme.context.edit_item_idx,
            mode='CUSTOM' if mode == 'CUSTOM' else 'COMMAND')

        lh.operator(
            PME_OT_pmi_pm_search.bl_idname,
            "Call PME Menu", 'COLOR')

        lh.sep()

        lh.operator(
            PME_OT_pmi_operator_search.bl_idname,
            "Call Operator", 'BLENDER',
            idx=pme.context.edit_item_idx)

        lh.operator(
            PME_OT_pmi_menu_search.bl_idname,
            "Call Menu", 'WORDWRAP_ON',
            idx=pme.context.edit_item_idx,
            mouse_over=False)

        if pm.mode == 'DIALOG':
            lh.operator(
                PME_OT_pmi_menu_search.bl_idname,
                "Call Menu (Open on Mouse Over)", 'WORDWRAP_ON',
                idx=pme.context.edit_item_idx,
                mouse_over=True)

        lh.operator(
            PME_OT_pmi_menu_search.bl_idname,
            "Call Pie Menu", 'MESH_CIRCLE',
            idx=pme.context.edit_item_idx,
            pie=True,
            mouse_over=False)

        lh.sep()

        if is_28():
            lh.operator(
                PME_OT_pmi_panel_search.bl_idname,
                "Popover Panel", 'WINDOW', popover=True)

        lh.operator(
            PME_OT_pmi_panel_search.bl_idname,
            "Popup Panel", 'WINDOW')

        lh.operator(
            PME_OT_pmi_area_search.bl_idname,
            "Popup Area", 'WINDOW')

        lh.operator(
            PME_OT_pmi_area_search.bl_idname,
            "Toggle Side-Area", 'WINDOW',
            cmd="bpy.ops.pme.sidearea_toggle("
            "area='%s', side='LEFT', main_area='VIEW_3D')")

        lh.operator(
            PME_OT_addonpref_search.bl_idname,
            "Popup Addon Preferences", 'PREFERENCES')

        lh.sep()

        lh.menu("PME_MT_screen_set", "Set Workspace", icon=ic('SPLITSCREEN'))
        lh.menu("PME_MT_brush_set", "Set Brush", icon=ic('BRUSH_DATA'))

        if pm and pm.mode in {'PMENU', 'DIALOG'}:
            lh.column(row, align=False)
            lh.label(text="")
            lh.label(text="Custom Tab")
            lh.sep()

            lh.operator(
                PME_OT_pmi_pm_search.bl_idname,
                "Draw PME Popup Dialog", 'COLOR', custom=True)

            lh.operator(
                PME_OT_pmi_panel_search.bl_idname,
                "Draw Panel", 'WINDOW', custom=True)

            lh.menu(
                "PME_MT_header_menu_set",
                "Draw Header Menu", icon=ic('WINDOW'))

            lh.sep()

            lh.layout.operator_menu_enum(
                PME_OT_pmi_custom_set.bl_idname, "mode",
                text="More", icon=ic('COLLAPSEMENU'))

    def _draw_menu(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        pr = prefs()
        pm = pr.selected_pm
        data = pr.pmi_data
        sub_pm = data.menu and data.menu in pr.pie_menus and \
            pr.pie_menus[data.menu]
        if sub_pm:
            label = None
            if sub_pm.mode == 'RMENU' and pm.mode != 'DIALOG':
                label = "Open on Mouse Over"
            elif sub_pm.mode == 'DIALOG' and pm.mode != 'RMENU':
                label = "Expand Popup Dialog"
            if label:
                lh.prop(data, "expand_menu", label)

        lh.sep(check=True)

    # def _draw_custom(self, menu, context):
    #     lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

    #     lh.operator(
    #         WM_OT_pmidata_hints_show.bl_idname, "Hints", 'QUESTION')

    #     lh.sep()

    #     lh.operator(
    #         PME_OT_script_open.bl_idname,
    #         "External Script", 'FILE_FOLDER',
    #         pm_item=pme.context.edit_item_idx,
    #         filepath=prefs().scripts_filepath)

    def execute(self, context):
        pr = prefs()
        mode = pr.pmi_data.mode
        if mode in MODAL_CMD_MODES:
            mode = 'COMMAND'

        context.window_manager.popup_menu(self._draw)
        # if mode == 'COMMAND':
        # elif mode == 'MENU':
        #     context.window_manager.popup_menu(self._draw_menu)
        # elif mode == 'CUSTOM':
        #     context.window_manager.popup_menu(self._draw_custom)
        # elif pr.pmi_data.mode == 'OPERATOR':
        #     context.window_manager.popup_menu(self._draw_operator)

        return {'FINISHED'}


class SearchOperator:
    use_cache = False

    def fill_enum_items(self, items):
        pass

    def get_enum_items(self, context):
        cls = getattr(bpy.types, self.__class__.__name__)
        if not hasattr(cls, "enum_items"):
            return tuple()

        if cls.enum_items is None:
            cls.enum_items = []
            cls.fill_enum_items(self, cls.enum_items)

        return cls.enum_items

    value: bpy.props.EnumProperty(
        name="Value", items=get_enum_items)

    def invoke(self, context, event):
        cls = getattr(bpy.types, self.__class__.__name__)
        if not hasattr(cls, "enum_items"):
            cls.enum_items = None
        elif not self.use_cache and cls.enum_items:
            cls.enum_items.clear()
            cls.enum_items = None

        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_pmi_menu_search(SearchOperator, bpy.types.Operator):
    bl_idname = "pme.pmi_menu_search"
    bl_label = ""
    bl_description = "Call menu"
    bl_options = {'INTERNAL'}
    bl_property = "value"

    idx: bpy.props.IntProperty(options={'SKIP_SAVE'})
    mouse_over: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    pie: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def fill_enum_items(self, items):
        for tp_name in dir(bpy.types):
            tp = getattr(bpy.types, tp_name)
            if not isclass(tp):
                continue

            if issubclass(tp, bpy.types.Menu) and hasattr(tp, "bl_label"):
                ctx, _, name = tp_name.partition("_MT_")
                label = hasattr(
                    tp, "bl_label") and tp.bl_label or name or tp_name
                label = "%s|%s" % (utitle(label), ctx)

                items.append((tp_name, label, ""))

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.idx]

        if self.pie:
            cmd = "bpy.ops.wm.call_menu_pie(name=\"%s\")" % self.value
            mode = 'COMMAND'

        elif self.mouse_over:
            cmd = (
                "L.menu(\"%s\", text=text, icon=icon, icon_value=icon_value, "
                "use_mouse_over_open=True)"
            ) % self.value
            mode = 'CUSTOM'
        else:
            cmd = "bpy.ops.wm.call_menu(name=\"%s\")" % self.value
            mode = 'COMMAND'

        typ = getattr(bpy.types, self.value)
        name = typ.bl_label if typ.bl_label else self.value

        if pr.mode == 'PMI':
            pr.pmi_data.mode = mode
            if self.mouse_over:
                pr.pmi_data.custom = cmd
            else:
                pr.pmi_data.cmd = cmd
            pr.pmi_data.sname = name
        else:
            pmi.mode = mode
            pmi.text = cmd
            pmi.name = name

        tag_redraw()
        return {'FINISHED'}


class PME_OT_script_open(bpy.types.Operator):
    bl_idname = "pme.script_open"
    bl_label = "Open Script"
    bl_description = (
        "Command tab:\n"
        "  Execute external script when the user clicks the button\n"
        "Custom tab:\n"
        "  Use external script to draw custom layout of widgets"
    )
    bl_options = {'INTERNAL'}

    filename_ext = ".py"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="")
    filter_glob: bpy.props.StringProperty(default="*.py", options={'HIDDEN'})
    idx: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})
    mode: bpy.props.EnumProperty(
        name="Tab",
        items=(
            ('COMMAND', "Command", ""),
            ('CUSTOM', "Custom", ""),
        )
    )

    def draw(self, context):
        if self.idx != -1:
            col = self.layout.column(align=True)
            col.label(text="Tab:")
            col.prop(self, "mode", text="")

    def execute(self, context):
        pr = prefs()

        filepath = os.path.normpath(self.filepath)
        pr.scripts_filepath = filepath

        if filepath.startswith(ADDON_PATH):
            filepath = os.path.relpath(filepath, ADDON_PATH)

        filename = os.path.basename(filepath)
        filename, _, _ = filename.rpartition(".")
        name = filename.replace("_", " ").strip().title()

        filepath = filepath.replace("\\", "/")
        cmd = "execute_script(\"%s\")" % filepath

        pm = pr.selected_pm
        if self.idx == -1:
            pm.poll_cmd = "return " + cmd

        else:
            pmi = pm.pmis[self.idx]

            if pr.mode == 'PMI':
                pr.pmi_data.mode = self.mode
                if pr.pmi_data.mode == 'COMMAND':
                    pr.pmi_data.cmd = cmd
                elif pr.pmi_data.mode == 'CUSTOM':
                    pr.pmi_data.custom = cmd

                pr.pmi_data.sname = name
            else:
                pmi.mode = self.mode
                pmi.text = cmd
                pmi.name = name

        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = prefs().scripts_filepath
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PME_OT_button_add(bpy.types.Operator):
    bl_idname = "pme.button_add"
    bl_label = "Add Button"
    bl_description = "Add the button to the menu"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        button_pointer = getattr(context, "button_pointer", None)
        button_prop = getattr(context, "button_prop", None)
        if button_prop and button_pointer:
            path = gen_prop_path(button_pointer, button_prop)
            DBG_PROP_PATH and logi("PATH", path)
            if path:
                try:
                    value = pme.context.eval(path)
                    DBG_PROP_PATH and logi("VALUE", value)
                    if value is not None:
                        path = "%s = %s" % (path, repr(value))
                except:
                    pass
                # context.window_manager.clipboard = path
                bpy.ops.pme.pm_edit('INVOKE_DEFAULT', text=path)
                return {'FINISHED'}

        if bpy.ops.ui.copy_python_command_button.poll():
            bpy.ops.ui.copy_python_command_button()
            bpy.ops.pme.pm_edit('INVOKE_DEFAULT', clipboard=True)
            return {'FINISHED'}

        button_operator = getattr(context, "button_operator", None)
        if button_operator:
            tpname = button_operator.__class__.__name__
            idname = operator_utils.to_bl_idname(tpname)
            args = ""
            keys = button_operator.keys()
            if keys:
                args = []
                for k in keys:
                    args.append(
                        "%s=%s" % (k, repr(getattr(button_operator, k))))
                args = ", ".join(args)
            cmd = "bpy.ops.%s(%s)" % (idname, args)

            # context.window_manager.clipboard = cmd
            bpy.ops.pme.pm_edit('INVOKE_DEFAULT', text=cmd, auto=False)
            return {'FINISHED'}

        message_box(W_PMI_ADD_BTN, 'ERROR')

        return {'CANCELLED'}


class PME_OT_debug_mode_toggle(bpy.types.Operator):
    bl_idname = "pme.debug_mode_toggle"
    bl_label = "Toggle Debug Mode"
    bl_description = "Toggle debug mode"

    def execute(self, context):
        bpy.app.debug_wm = not bpy.app.debug_wm
        mode = "Off"
        if bpy.app.debug_wm:
            mode = "On"
        self.report({'INFO'}, I_DEBUG % mode)
        tag_redraw()
        return {'CANCELLED'}


class WM_OT_pme_hotkey_call(bpy.types.Operator):
    bl_idname = "wm.pme_hotkey_call"
    bl_label = "Hotkey"

    hotkey: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        keymap_helper.run_operator_by_hotkey(context, self.hotkey)
        return {'FINISHED'}


class PME_OT_pm_chord_add(bpy.types.Operator):
    bl_idname = "pme.pm_chord_add"
    bl_label = "Add or Remove Chord"
    bl_description = "Add or remove chord"
    bl_options = {'INTERNAL'}

    add: bpy.props.BoolProperty(default=True, options={'SKIP_SAVE'})

    def execute(self, context):
        pm = prefs().selected_pm
        if self.add:
            pm.chord = 'A'
        else:
            pm.chord = 'NONE'

        return {'FINISHED'}


class PME_OT_pm_hotkey_remove(bpy.types.Operator):
    bl_idname = "pme.pm_hotkey_remove"
    bl_label = ""
    bl_description = "Remove the hotkey"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        pm = prefs().selected_pm
        return pm and pm.key != 'NONE'

    def execute(self, context):
        pm = prefs().selected_pm
        pm["key"] = 0
        pm["ctrl"] = False
        pm["shift"] = False
        pm["alt"] = False
        pm["oskey"] = False
        pm["key_mod"] = 0
        pm.update_keymap_item(context)

        return {'FINISHED'}

    def invoke(self, context, event):
        if event.shift:
            if 'FINISHED' in bpy.ops.pme.pm_hotkey_convert():
                return {'FINISHED'}

        return self.execute(context)


def register():
    pme.context.add_global("traceback", traceback)


# def unregister():
#     tp = WM_OT_pme_user_pie_menu_call
#     if tp.pm_handler:
#         tp.pm_handler_type.draw_handler_remove(
#             tp.pm_handler, 'WINDOW')
#         tp.pm_handler = None
#         tp.pm_handler_type = None

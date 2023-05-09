import bpy
from . import constants as CC
from .collection_utils import MoveItemOperator
from .ed_base import EditorBase, PME_OT_pm_edit, PME_OT_pm_add
from .addon import prefs, uprefs, ic, ic_cb, is_28
from .layout_helper import lh, operator, draw_pme_layout
from .ui import utitle, tag_redraw
from .ui_utils import draw_menu
from .bl_utils import bl_context
from .operators import (
    WM_OT_pm_select, WM_OT_pme_user_pie_menu_call, PME_OT_panel_hide,
    PME_OT_pm_search_and_select
)
from .extra_operators import PME_OT_clipboard_copy
from . import panel_utils as PAU
from .panel_utils import (
    panel, PLayout,
)
from . import pme
from . import c_utils


class PME_OT_panel_sub_toggle(bpy.types.Operator):
    bl_idname = "pme.panel_sub_toggle"
    bl_label = "Toggle Panel/Sub-panel"
    bl_description = "Toggle panel/sub-panel"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        if self.idx == 0:
            return {'FINISHED'}

        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.idx]
        pmi.icon = CC.PANEL_FOLDER if pmi.icon else CC.PANEL_FILE

        pm.update_panel_group()
        return {'FINISHED'}


class PME_OT_toolbar_menu(bpy.types.Operator):
    bl_idname = "pme.toolbar_menu"
    bl_label = "Toolbar Menu"
    bl_description = "Toolbar menu"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def draw_toolbar_menu(self, menu, context):
        lh.lt(menu.layout)

        def_name = "Toolbar"
        scr_name = def_name + " " + context.screen.name
        dir_name = PME_PT_toolbar.get_dir_name()
        dir_scr_name = scr_name + " " + dir_name
        dir_name = def_name + " " + dir_name

        lh.operator(
            self.bl_idname, "Create Toolbar (Current Screen)", 'ZOOMIN',
            name=dir_scr_name)
        lh.operator(
            self.bl_idname, "Create Toolbar (All Screens)", 'ZOOMIN',
            name=dir_name)

    def execute(self, context):
        if not self.name:
            context.window_manager.popup_menu(
                self.draw_toolbar_menu, title="Pie Menu Editor")
        else:
            pr = prefs()
            pr.add_pm('DIALOG', self.name)
            pr.update_tree()
            tag_redraw()
            pr.tab = 'EDITOR'
            bpy.ops.pme.popup_addon_preferences(
                'INVOKE_DEFAULT', addon="pie_menu_editor")

        return {'FINISHED'}


class PME_PT_toolbar(bpy.types.Panel):
    bl_label = "PME Toolbar"
    bl_space_type = CC.UPREFS
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    @staticmethod
    def get_dir_name():
        C = bpy.context
        area = C.area
        mid_x = C.window.width >> 1
        mid_y = C.window.height >> 1
        if area.width > area.height:
            if area.y < mid_y:
                return "Bottom"
            else:
                return "Top"
        else:
            if area.x < mid_x:
                return "Left"
            else:
                return "Right"

    def draw(self, context):
        lh.lt(self.layout)
        if not is_28():
            self.layout.scale_y = 0.001

        c_layout = c_utils.c_layout(self.layout)
        c_style = c_utils.c_style(c_layout)

        if is_28():
            margin = round(4 * uprefs().view.ui_scale)
            c_layout.y += margin
        else:
            margin = round(3 * uprefs().view.ui_scale)
            c_layout.y += c_style.panelspace - margin

        if context.area.width <= context.area.height:
            if is_28():
                c_layout.w += 2 * margin
                c_layout.x -= margin
            else:
                c_layout.w += 2 * c_style.panelspace - 2 * margin
                c_layout.x -= c_style.panelspace - margin

        def_name = "Toolbar"
        scr_name = def_name + " " + context.screen.name
        dir_name = PME_PT_toolbar.get_dir_name()

        vertical = True
        if dir_name in {"Top", "Bottom"}:
            vertical = False

        dir_scr_name = scr_name + " " + dir_name
        dir_name = def_name + " " + dir_name

        has_menu = draw_menu(dir_scr_name) or draw_menu(dir_name) or draw_menu(
            scr_name) or draw_menu(def_name)

        if not has_menu:
            lh.row()
            lh.layout.alignment = 'CENTER'
            lh.layout.scale_x = lh.layout.scale_y = 1.5 if vertical else 1
            lh.operator(
                PME_OT_toolbar_menu.bl_idname,
                "" if vertical else "Pie Menu Editor", 'COLOR')

    @classmethod
    def poll(cls, context):
        pr = prefs()
        ret = context.area.width <= pr.toolbar_width or \
            context.area.height <= pr.toolbar_height

        return ret


def draw_pme_panel(self, context):
    pr = prefs()
    if self.pme_data in pr.pie_menus:
        pm = pr.pie_menus[self.pme_data]
        if issubclass(self.__class__, bpy.types.Header):
            if not self.__class__.poll(context):
                return
            self.layout.separator()
        scale_x = 1
        if getattr(self, "pm_name", None) in pr.pie_menus:
            pg = pr.pie_menus[self.pm_name]
            prop = pme.props.parse(pg.data)
            scale_x = -1 if prop.pg_wicons else 1

        draw_pme_layout(
            pm, self.layout.column(align=True),
            WM_OT_pme_user_pie_menu_call._draw_item, None,
            scale_x)

    else:
        tp = PAU.hidden_panel(self.pme_data) or getattr(
            bpy.types, self.pme_data, None)
        if not tp:
            return
        pme.context.layout = self.layout
        panel(tp, False, False, root=True)


def poll_pme_panel(cls, context):
    pr = prefs()
    if cls.pm_name not in pr.pie_menus:
        return True

    pm = pr.pie_menus[cls.pm_name]
    return pm.poll(cls, context)


class PME_OT_panel_menu(bpy.types.Operator):
    bl_idname = "pme.panel_menu"
    bl_label = ""
    bl_description = ""
    bl_options = {'INTERNAL'}

    panel: bpy.props.StringProperty()
    is_right_region: bpy.props.BoolProperty()

    def extend_ui_operator(self, label, icon, mode, pm_name):
        pr = prefs()
        if pm_name in pr.pie_menus:
            lh.operator(
                WM_OT_pm_select.bl_idname,
                label, icon, pm_name=pm_name)
        else:
            lh.operator(
                PME_OT_pm_add.bl_idname,
                label, icon, mode=mode, name=pm_name)


    def draw_header_menu(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        pr = prefs()
        pm = pr.selected_pm

        right_suffix = CC.F_RIGHT if self.is_right_region else ""
        self.extend_ui_operator(
            "Extend Header", 'TRIA_LEFT', 'DIALOG',
            self.panel + right_suffix + CC.F_PRE)

        self.extend_ui_operator(
            "Extend Header", 'TRIA_RIGHT', 'DIALOG',
            self.panel + right_suffix)

        lh.operator(
            PME_OT_clipboard_copy.bl_idname, "Copy Menu ID", 'COPYDOWN',
            text=self.panel)

        lh.sep()

        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)
        lh.operator(
            PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')

        lh.sep()

        lh.prop(pr, "debug_mode")
        lh.prop(pr, "interactive_panels")

    def draw_menu_menu(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        pr = prefs()
        pm = pr.selected_pm

        if pm:
            tp = getattr(bpy.types, self.panel, None)
            label = tp and getattr(tp, "bl_label", None) or self.panel

            if pm.mode in {'PMENU', 'RMENU', 'DIALOG'}:
                lh.operator(
                    PME_OT_pm_edit.bl_idname, "Add as Menu to '%s'" % pm.name,
                    'ZOOMIN',
                    auto=False,
                    name=label, mode='CUSTOM',
                    text="L.menu(menu='%s', text=slot, icon=icon, "
                    "icon_value=icon_value)" % self.panel)

                lh.sep()

        self.extend_ui_operator(
            "Extend Menu", 'TRIA_UP', 'RMENU', self.panel + CC.F_PRE)
        self.extend_ui_operator(
            "Extend Menu", 'TRIA_DOWN', 'RMENU', self.panel)

        lh.operator(
            PME_OT_clipboard_copy.bl_idname, "Copy Menu ID", 'COPYDOWN',
            text=self.panel)

        lh.sep()

        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)
        lh.operator(
            PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')

        lh.sep()

        lh.prop(pr, "debug_mode")
        lh.prop(pr, "interactive_panels")

    def draw_panel_menu(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        pr = prefs()
        pm = pr.selected_pm

        lh.operator(
            PME_OT_panel_hide.bl_idname,
            "Hide Panel", 'VISIBLE_IPO_OFF',
            panel=self.panel)

        if pm:
            tp = PAU.hidden_panel(self.panel) or \
                getattr(bpy.types, self.panel, None)
            label = tp and getattr(tp, "bl_label", None) or self.panel

            if pm.mode in {'PMENU', 'RMENU', 'DIALOG', 'SCRIPT'}:
                lh.operator(
                    PME_OT_pm_edit.bl_idname,
                    "Add as Button to '%s'" % pm.name,
                    'ZOOMIN',
                    auto=False,
                    name=label, mode='COMMAND',
                    text=(
                        "bpy.ops.pme.popup_panel("
                        "panel='%s', frame=True, area='%s')"
                    ) % (self.panel, context.area.type))

                if is_28():
                    lh.operator(
                        PME_OT_pm_edit.bl_idname,
                        "Add as Popover to '%s'" % pm.name,
                        'ZOOMIN',
                        auto=False,
                        name=label, mode='CUSTOM',
                        text=(
                            "L.popover("
                            "panel='%s', "
                            "text=slot, icon=icon, icon_value=icon_value)"
                        ) % self.panel)

            if pm.mode == 'PANEL':
                lh.operator(
                    PME_OT_panel_add.bl_idname,
                    "Add as Panel to '%s'" % pm.name,
                    'ZOOMIN',
                    panel=self.panel, mode='BLENDER')

            elif pm.mode == 'DIALOG':
                lh.operator(
                    PME_OT_panel_add.bl_idname,
                    "Add as Panel to '%s'" % pm.name, 'ZOOMIN',
                    panel=self.panel, mode='DIALOG')

            elif pm.mode == 'PMENU':
                lh.operator(
                    PME_OT_pm_edit.bl_idname,
                    "Add as Panel to '%s'" % pm.name, 'ZOOMIN',
                    auto=False,
                    name=label, mode='CUSTOM',
                    text="panel('%s', area='%s')" % (
                        self.panel, context.area.type))

            lh.sep()

        self.extend_ui_operator(
            "Extend Panel", 'TRIA_UP', 'DIALOG', self.panel + CC.F_PRE)
        self.extend_ui_operator(
            "Extend Panel", 'TRIA_DOWN', 'DIALOG', self.panel)

        lh.operator(
            PME_OT_clipboard_copy.bl_idname, "Copy Panel ID", 'COPYDOWN',
            text=self.panel)

        lh.sep()

        lh.operator(
            WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)
        lh.operator(
            PME_OT_pm_search_and_select.bl_idname, None, 'VIEWZOOM')

        lh.sep()

        lh.prop(pr, "debug_mode")
        lh.prop(pr, "interactive_panels")

    def execute(self, context):
        if '_HT_' in self.panel:
            context.window_manager.popup_menu(
                self.draw_header_menu, title=self.panel)
        elif '_MT_' in self.panel:
            context.window_manager.popup_menu(
                self.draw_menu_menu, title=self.panel)
        else:
            context.window_manager.popup_menu(
                self.draw_panel_menu, title=self.panel)
        return {'FINISHED'}


class PME_OT_interactive_panels_toggle(bpy.types.Operator):
    bl_idname = "pme.interactive_panels_toggle"
    bl_label = "Toggle Interactive Panels (PME)"
    bl_description = "Toggle panel tools"
    bl_options = {'REGISTER'}

    active = False
    enabled = True

    action: bpy.props.EnumProperty(
        items=(
            ('TOGGLE', "Toggle", ""),
            ('ENABLE', "Enable", ""),
            ('DISABLE', "Disable", ""),
        ),
        options={'SKIP_SAVE'}
    )

    @staticmethod
    def _draw(self, context):
        # if not PME_OT_interactive_panels_toggle.enabled or \
        #         PLayout.active:
        #     return
        if panel.active:
            return

        lh.lt(self.layout.row(align=True))
        lh.layout.alert = True
        # is_pg = pm.mode == 'PANEL' or pm.mode == 'HPANEL' or \
        #     pm.mode == 'DIALOG'
        # lh.operator(
        #     WM_OT_pm_select.bl_idname,
        #     "" if is_pg else "Select Item",
        #     pm.ed.icon if is_pg else 'NONE',
        #     mode={'PANEL', 'HPANEL', 'DIALOG'})

        tp = self.__class__
        tp_name = tp.bl_idname if hasattr(tp, "bl_idname") else tp.__name__

        lh.operator(
            PME_OT_panel_menu.bl_idname,
            "PME Tools", 'COLOR', panel=tp_name)

        # lh.operator(
        #     PME_OT_interactive_panels_toggle.bl_idname, "", 'QUIT',
        #     action='DISABLE')

    @staticmethod
    def _draw_menu(self, context):
        # if not PME_OT_interactive_panels_toggle.enabled or \
        #         PLayout.active:
        #     return
        if panel.active:
            return

        tp = self.__class__
        tp_name = tp.bl_idname if hasattr(tp, "bl_idname") else tp.__name__

        lh.lt(self.layout)
        lh.layout.alert = True
        lh.sep()

        lh.operator(
            PME_OT_panel_menu.bl_idname,
            "PME Tools", 'COLOR', panel=tp_name)

    @staticmethod
    def _draw_header(self, context):
        if panel.active:
            return

        tp = self.__class__
        tp_name = tp.bl_idname if hasattr(tp, "bl_idname") else tp.__name__

        lh.lt(self.layout)
        lh.layout.alert = True
        lh.sep()

        lh.operator(
            PME_OT_panel_menu.bl_idname,
            "PME Tools", 'COLOR', panel=tp_name,
            is_right_region=context.region.alignment == 'RIGHT')

    def execute(self, context):
        pr = prefs()
        if self.action == 'ENABLE' or self.action == 'TOGGLE' and \
                not pr.interactive_panels:
            pr.interactive_panels = True
        else:
            pr.interactive_panels = False
            PLayout.editor = False

        # if self.__class__.ahpg and self.hpg:
        #     self.__class__.ahpg = self.hpg
        #     return {'FINISHED'}

        return {'FINISHED'}


class PME_OT_panel_add(bpy.types.Operator):
    bl_idname = "pme.panel_add"
    bl_label = "Add Panel"
    bl_description = "Add panel"
    bl_options = {'INTERNAL'}
    bl_property = "item"

    enum_items = None

    def get_items(self, context):
        if not PME_OT_panel_add.enum_items:
            enum_items = []

            if self.mode == 'BLENDER':
                def _add_item(tp_name, tp):
                    ctx, _, name = tp_name.partition("_PT_")
                    label = hasattr(
                        tp, "bl_label") and tp.bl_label or name or tp_name
                    if name:
                        if name == label or utitle(name) == label:
                            label = "[%s] %s" % (ctx, utitle(label))
                        else:
                            label = "[%s] %s (%s)" % (ctx, label, name)

                    enum_items.append((tp_name, label, ""))

                for tp in PAU.bl_panel_types():
                    _add_item(
                        tp.bl_idname if hasattr(tp, "bl_idname") else
                        tp.__name__,
                        tp)

                for tp_name, tp in PAU.get_hidden_panels().items():
                    _add_item(tp_name, tp)

            elif self.mode == 'PME':
                for pm in prefs().pie_menus:
                    if pm.mode == 'DIALOG':
                        enum_items.append((pm.name, pm.name, ""))

            PME_OT_panel_add.enum_items = enum_items

        return PME_OT_panel_add.enum_items

    item: bpy.props.EnumProperty(items=get_items, options={'SKIP_SAVE'})
    index: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})
    mode: bpy.props.StringProperty(options={'SKIP_SAVE'})
    panel: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        if not self.panel:
            self.panel = self.item

        pm = pr.selected_pm

        if self.mode == 'BLENDER' or self.mode == 'DIALOG':
            tp = PAU.hidden_panel(self.panel) or getattr(
                bpy.types, self.panel, None)
            if not tp:
                return {'CANCELLED'}

        if self.mode == 'DIALOG':
            pmi = pm.ed.add_pd_row(pm)
            pmi.mode = 'CUSTOM'
            pmi.text = (
                "panel("
                "'%s', frame=True, header=True, expand=None, area='%s')"
            ) % (self.panel, context.area.type)
        else:
            pmi = pm.pmis.add()
            pmi.mode = 'MENU'
            pmi.text = self.panel

        if self.mode == 'BLENDER' or self.mode == 'DIALOG':
            if hasattr(tp, "bl_label") and tp.bl_label:
                pmi.name = tp.bl_label
            else:
                ctx, _, name = self.panel.partition("_PT_")
                pmi.name = utitle(name if name else ctx)

        elif self.mode == 'PME':
            pmi.name = self.panel

        idx = len(pm.pmis) - 1
        if self.index != -1 and self.index != idx:
            pm.pmis.move(idx, self.index)
            idx = self.index

        if pm.mode == 'PANEL':
            pm.update_panel_group()

        if self.mode == 'PME':
            pr.update_tree()

        tag_redraw()
        return {'FINISHED'}

    def _draw(self, menu, context):
        pr = prefs()
        lh.lt(menu.layout, 'INVOKE_DEFAULT')
        lh.operator(
            self.__class__.bl_idname, "Popup Dialog", pr.ed('DIALOG').icon,
            mode='PME', index=self.index)
        lh.operator(
            self.__class__.bl_idname, "Panel", 'BLENDER',
            mode='BLENDER', index=self.index)

        lh.sep()

        lh.prop(prefs(), "interactive_panels")

    def invoke(self, context, event):
        if not self.mode:
            context.window_manager.popup_menu(self._draw)
        elif not self.panel:
            PME_OT_panel_add.enum_items = None
            context.window_manager.invoke_search_popup(self)
        else:
            return self.execute(context)
        return {'FINISHED'}


class PME_OT_panel_item_move(MoveItemOperator, bpy.types.Operator):
    bl_idname = "pme.panel_item_move"

    def get_icon(self, item, idx):
        return 'FILE' if item.icon == CC.PANEL_FILE else 'FILE_FOLDER'

    def get_collection(self):
        return prefs().selected_pm.pmis

    def finish(self):
        pr = prefs()
        pm = pr.selected_pm
        if self.new_idx == 0:
            pm.pmis[0].icon = CC.PANEL_FOLDER

        pm.update_panel_group()
        tag_redraw()


class PME_OT_panel_item_remove(bpy.types.Operator):
    bl_idname = "pme.panel_item_remove"
    bl_label = "Remove Panel"
    bl_description = "Remove the panel"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        PAU.remove_panel(pm.name, self.idx)

        pm.pmis.remove(self.idx)

        pr.update_tree()
        tag_redraw()
        return {'CANCELLED'}


pme.props.BoolProperty("pg", "pg_wicons")
pme.props.StringProperty("pg", "pg_context", "ANY")
pme.props.StringProperty("pg", "pg_category", "My Category")
pme.props.StringProperty("pg", "pg_space", "VIEW_3D")
pme.props.StringProperty("pg", "pg_region", "TOOLS")


class Editor(EditorBase):

    def __init__(self):
        self.id = 'PANEL'
        EditorBase.__init__(self)

        self.docs = "#Panel_Group_Editor"
        self.use_preview = False
        self.sub_item = False
        self.has_hotkey = False
        self.default_pmi_data = "pg?"
        self.supported_slot_modes = {'EMPTY', 'MENU'}

    def init_pm(self, pm):
        if pm.enabled:
            PAU.add_panel_group(pm, draw_pme_panel, poll_pme_panel)

    def on_pm_remove(self, pm):
        PAU.remove_panel_group(pm.name)
        super().on_pm_remove(pm)

    def on_pm_duplicate(self, from_pm, pm):
        EditorBase.on_pm_duplicate(self, from_pm, pm)
        if pm.enabled:
            PAU.add_panel_group(pm, draw_pme_panel, poll_pme_panel)

    def on_pm_enabled(self, pm, value):
        super().on_pm_enabled(pm, value)

        if pm.enabled:
            PAU.add_panel_group(pm, draw_pme_panel, poll_pme_panel)
        else:
            PAU.remove_panel_group(pm.name)

    def on_pm_rename(self, pm, name):
        super().on_pm_rename(pm, name)
        PAU.rename_panel_group(pm.name, name)

    def on_pmi_rename(self, pm, pmi, old_name, name):
        for item in pm.pmis:
            if item == pmi:
                pmi.name = name
                pm.update_panel_group()
                break

    def draw_keymap(self, layout, data):
        row = layout.row(align=True)
        row.prop(data, "panel_space", text="")
        row.prop(data, "panel_region", text="")

        if data.panel_region != 'HEADER':
            row = layout.row(align=True)
            row.prop(data, "panel_context", text="")

            ic_items = prefs().rna_type.properties[
                "panel_info_visibility"].enum_items
            row.prop(
                data, "panel_category", text="",
                icon=ic(ic_items['CAT'].icon))

    def draw_hotkey(self, layout, data):
        pass

    def draw_extra_settings(self, layout, pm):
        EditorBase.draw_extra_settings(self, layout, pm)
        layout.prop(pm, "panel_wicons")

    def draw_items(self, layout, pm):
        pr = prefs()
        col = layout.column(align=True)

        for idx, pmi in enumerate(pm.pmis):
            lh.row(col)

            if pmi.icon == CC.PANEL_FILE:
                lh.operator(
                    "pme.panel_sub_toggle", "",
                    'BLANK1',
                    idx=idx)

            lh.operator(
                "pme.panel_sub_toggle", "",
                'FILE' if pmi.icon == CC.PANEL_FILE else 'FILE_FOLDER',
                idx=idx)
            icon = pr.ed('DIALOG').icon if pmi.text in prefs().pie_menus \
                else 'BLENDER'
            lh.prop(pmi, "label", "", icon)

            # lh.operator(
            #     PME_OT_panel_item_menu.bl_idname,
            #     "", 'COLLAPSEMENU',
            #     idx=idx)

            self.draw_pmi_menu_btn(pr, idx)

        lh.row(col)
        lh.operator(PME_OT_panel_add.bl_idname, "Add Panel")

    def draw_pmi_menu(self, context, idx):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[idx]

        text, *_ = pmi.parse()
        lh.label(
            text if text.strip() else "Menu",
            pr.ed('DIALOG').icon if pmi.text in pr.pie_menus else 'BLENDER')

        lh.sep(check=True)

        lh.operator(
            "pme.panel_sub_toggle", "Sub-Panel",
            ic_cb(pmi.icon == CC.PANEL_FILE),
            idx=idx)

        lh.sep(check=True)

        lh.operator(
            PME_OT_panel_add.bl_idname, "Add Panel", 'ZOOMIN',
            index=idx)

        if len(pm.pmis) > 1:
            lh.operator(
                PME_OT_panel_item_move.bl_idname,
                "Move Panel", 'FORWARD',
                old_idx=idx)

            lh.sep(check=True)

        lh.operator(
            PME_OT_panel_item_remove.bl_idname,
            "Remove", 'X',
            idx=idx)

    def update_panel_group(self, pm):
        PAU.remove_panel_group(pm.name)
        PAU.add_panel_group(pm, draw_pme_panel, poll_pme_panel)


def register():
    Editor()

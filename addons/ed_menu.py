import bpy
from .ed_base import (
    EditorBase, PME_OT_pmi_copy, PME_OT_pmi_paste, WM_OT_pmi_data_edit,
    PME_OT_pmi_remove, WM_OT_pmi_icon_select, PME_OT_pmi_toggle,
    extend_panel, unextend_panel)
from .bl_utils import PME_OT_input_box
from .addon import prefs, ic_eye
from .layout_helper import lh, Col
from .ui import tag_redraw, shorten_str
from .constants import SPACER_SCALE_Y, SEPARATOR_SCALE_Y
from . import pme


class WM_OT_rmi_add(bpy.types.Operator):
    bl_idname = "wm.rmi_add"
    bl_label = "Add Slot or Column"
    bl_description = "Add a slot or column"
    bl_options = {'INTERNAL'}

    mode: bpy.props.StringProperty()
    index: bpy.props.IntProperty()

    def execute(self, context):
        pm = prefs().selected_pm
        pmi = pm.pmis.add()

        if self.mode == 'ITEM':
            pmi.mode = 'COMMAND'
            pmi.name = "Slot"
            pmi.text = ""

        elif self.mode == 'LABEL':
            pmi.name = "Label"
            pmi.text = "label"

        elif self.mode == 'SPACER':
            pmi.text = "spacer"

        elif self.mode == 'SEPARATOR':
            pmi.name = ""

        elif self.mode == 'COLUMN':
            pmi.text = "column"

        idx = len(pm.pmis) - 1
        if self.index != -1 and self.index != idx:
            pm.pmis.move(idx, self.index)

        tag_redraw()
        return {'FINISHED'}


class WM_OT_rmi_move(bpy.types.Operator):
    bl_idname = "wm.rmi_move"
    bl_label = ""
    bl_description = "Move the item"
    bl_options = {'INTERNAL'}

    pm_item: bpy.props.IntProperty()
    idx: bpy.props.IntProperty()

    def _draw(self, menu, context):
        pm = prefs().selected_pm

        row = menu.layout.row()
        lh.column(row)

        for idx, pmi in enumerate(pm.pmis):
            name = pmi.name
            # icon = pmi.parse_icon()
            icon = 'SPACE2' if idx == self.pm_item else 'SPACE3'

            if pmi.mode == 'EMPTY':
                if pmi.text == "column":
                    lh.operator(
                        WM_OT_rmi_move.bl_idname, ". . .",
                        pm_item=self.pm_item,
                        idx=idx)
                    lh.column(row)
                    continue

                if pmi.text == "":
                    name = "<Separator>"
                elif pmi.text == "spacer":
                    name = "<Spacer>"

                if pmi.text != "label":
                    icon = 'NONE'

            lh.operator(
                WM_OT_rmi_move.bl_idname, name, icon,
                pm_item=self.pm_item,
                idx=idx)

        lh.operator(
            WM_OT_rmi_move.bl_idname, ". . .",
            pm_item=self.pm_item,
            idx=idx + 1)

    def execute(self, context):
        pm = prefs().selected_pm

        if self.idx == -1:
            bpy.context.window_manager.popup_menu(self._draw)

        elif self.idx != self.pm_item and self.idx != self.pm_item + 1:
            if self.idx > self.pm_item + 1 or self.idx == len(pm.pmis):
                pm.pmis.move(self.pm_item, self.idx - 1)
            else:
                pm.pmis.move(self.pm_item, self.idx)

            tag_redraw()

        return {'FINISHED'}


class WM_OT_rm_col_specials_call(bpy.types.Operator):
    bl_idname = "wm.rm_col_specials_call"
    bl_label = ""
    bl_description = "Menu"
    bl_options = {'INTERNAL'}

    cur_col = Col()

    col_idx: bpy.props.IntProperty()

    def _draw(self, menu, context):
        pr = prefs()
        pm = pr.selected_pm

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Column", 'ZOOMIN',
            index=self.cur_col.a,
            mode='COLUMN')

        lh.sep(check=True)

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Slot", 'ZOOMIN',
            index=self.cur_col.b,
            mode='ITEM')

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Label", 'ZOOMIN',
            index=self.cur_col.b,
            mode='LABEL')

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Separator", 'ZOOMIN',
            index=self.cur_col.b,
            mode='SEPARATOR')

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Spacer", 'ZOOMIN',
            index=self.cur_col.b,
            mode='SPACER')

        lh.sep(check=True)

        if self.col_idx < len(pm.pmis):

            lh.operator(
                WM_OT_rm_col_remove.bl_idname,
                "Join Column", 'FULLSCREEN_EXIT',
                ask=True,
                mode='JOIN',
                col_idx=self.cur_col.a,
                col_last_idx=self.cur_col.b)

        lh.sep(check=True)

        if self.cur_col.calc_num_items(pm) > 0:
            lh.operator(
                WM_OT_rm_col_copy.bl_idname, "Copy Column", 'COPYDOWN',
                idx=self.cur_col.a,
                last_idx=self.cur_col.b)

        if pr.rmc_clipboard:
            lh.operator(
                WM_OT_rm_col_paste.bl_idname, "Paste Column", 'BACK',
                idx=self.cur_col.a,
                last_idx=self.cur_col.b,
                left=True)

            lh.operator(
                WM_OT_rm_col_paste.bl_idname, "Paste Column", 'FORWARD',
                idx=self.cur_col.a,
                last_idx=self.cur_col.b,
                left=False)

        lh.sep(check=True)

        lh.operator(
            WM_OT_rm_col_move.bl_idname, "Move Column", 'FORWARD',
            col_idx=self.cur_col.b,
            move_idx=-1)

        lh.sep(check=True)

        lh.operator(
            WM_OT_rm_col_remove.bl_idname,
            "Remove Column", 'X',
            ask=True,
            mode='REMOVE',
            col_idx=self.cur_col.a,
            col_last_idx=self.cur_col.b)

    def execute(self, context):
        pm = prefs().selected_pm

        self.cur_col.find_ab(pm, self.col_idx)

        context.window_manager.popup_menu(
            self._draw, title="Column")

        return {'FINISHED'}


class WM_OT_rm_col_move(bpy.types.Operator):
    bl_idname = "wm.rm_col_move"
    bl_label = ""
    bl_description = "Move the column"
    bl_options = {'INTERNAL'}

    col_idx: bpy.props.IntProperty()
    move_idx: bpy.props.IntProperty()
    cols = []

    def _draw(self, menu, context):
        lh.lt(menu.layout)

        for idx, col in enumerate(WM_OT_rm_col_move.cols):
            icon = 'SPACE2' if self.col_idx == col[1] else 'SPACE3'
            lh.operator(
                WM_OT_rm_col_move.bl_idname, "Column %d" % (idx + 1), icon,
                move_idx=idx,
                col_idx=self.col_idx)

    def execute(self, context):
        pm = prefs().selected_pm

        if self.move_idx == -1:
            cols = []
            col_idx = -1
            idx = 0
            for idx, pmi in enumerate(pm.pmis):
                if Col.is_column(pmi):
                    if col_idx == -1:
                        cols.append((0, idx))
                        col_idx = idx
                    else:
                        cols.append((col_idx, idx))
                        col_idx = idx

            if col_idx != -1:
                cols.append((col_idx, idx + 1))
            else:
                cols.append((0, idx + 1))

            WM_OT_rm_col_move.cols = cols

            context.window_manager.popup_menu(
                self._draw, title=WM_OT_rm_col_move.bl_description)

        else:
            forward = True
            for idx, col in enumerate(WM_OT_rm_col_move.cols):
                if col[1] == self.col_idx:
                    if idx == self.move_idx:
                        return {'CANCELLED'}

                    col_idx, col_last_idx = col
                    if self.move_idx < idx:
                        forward = False
                    break

            if forward:
                move_idx = WM_OT_rm_col_move.cols[self.move_idx][1]
            else:
                col = WM_OT_rm_col_move.cols[self.move_idx]
                move_idx = col[0]
                if self.move_idx != 0:
                    move_idx += 1

            if forward:
                if col_idx != col_last_idx and Col.is_column(pm.pmis[col_idx]):
                    col_idx += 1

                if move_idx >= len(pm.pmis):
                    pm.pmis.move(col_last_idx, col_idx)
                    move_idx -= 1

                for i in range(0, col_last_idx - col_idx + 1):
                    pm.pmis.move(col_idx, move_idx)

            else:
                if col_last_idx >= len(pm.pmis):
                    pm.pmis.move(col_idx, col_last_idx - 1)

                if (col_last_idx < len(pm.pmis) or
                        col_idx + 1 != col_last_idx) and \
                        Col.is_column(pm.pmis[col_idx]):
                    col_idx += 1

                for i in range(0, col_last_idx - col_idx + 1):
                    pm.pmis.move(col_idx + i, move_idx + i)

            tag_redraw()

        return {'FINISHED'}


class WM_OT_rm_col_remove(bpy.types.Operator):
    bl_idname = "wm.rm_col_remove"
    bl_label = ""
    bl_description = "Remove the column"
    bl_options = {'INTERNAL'}

    col_idx: bpy.props.IntProperty()
    col_last_idx: bpy.props.IntProperty()
    ask: bpy.props.BoolProperty()
    mode: bpy.props.StringProperty()

    def _draw(self, menu, context):
        lh.lt(menu.layout)
        lh.operator(
            WM_OT_rm_col_remove.bl_idname, "Remove", 'X',
            col_idx=self.col_idx,
            col_last_idx=self.col_last_idx,
            ask=False)

    def execute(self, context):
        pm = prefs().selected_pm

        if self.mode == 'JOIN':
            pm.pmis.remove(self.col_last_idx)
            tag_redraw()
            return {'FINISHED'}

        if self.ask:
            context.window_manager.popup_menu(
                self._draw, title=WM_OT_rm_col_remove.bl_description)
        else:
            if self.col_idx == self.col_last_idx:
                pm.pmis.remove(self.col_idx)

            elif self.col_idx == 0 and not Col.is_column(pm.pmis[0]):
                for i in range(self.col_idx, self.col_last_idx + 1):
                    pm.pmis.remove(self.col_idx)
            else:
                for i in range(self.col_idx, self.col_last_idx):
                    pm.pmis.remove(self.col_idx)

            tag_redraw()

        return {'FINISHED'}


class WM_OT_rm_col_copy(bpy.types.Operator):
    bl_idname = "wm.rm_col_copy"
    bl_label = "Copy Column"
    bl_description = "Copy the column"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()
    last_idx: bpy.props.IntProperty()

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        pr.rmc_clipboard.clear()

        for i in range(self.idx, self.last_idx):
            pmi = pm.pmis[i]
            if pmi.mode == 'EMPTY' and pmi.text == "column":
                continue
            pr.rmc_clipboard.append((pmi.name, pmi.icon, pmi.mode, pmi.text))

        return {'FINISHED'}


class WM_OT_rm_col_paste(bpy.types.Operator):
    bl_idname = "wm.rm_col_paste"
    bl_label = "Paste Column"
    bl_description = "Paste the column"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()
    last_idx: bpy.props.IntProperty()
    left: bpy.props.BoolProperty()

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        idx = self.idx if self.left else self.last_idx
        if self.left and Col.is_column(pm.pmis[idx]) and \
                self.idx != self.last_idx:
            idx += 1

        last_idx = len(pm.pmis)

        if not self.left:
            pmi = pm.pmis.add()
            pmi.mode = 'EMPTY'
            pmi.text = "column"
            pm.pmis.move(last_idx, idx)
            last_idx += 1
            idx += 1

        for row in pr.rmc_clipboard:
            pmi = pm.pmis.add()
            pmi.name = row[0]
            pmi.icon = row[1]
            pmi.mode = row[2]
            pmi.text = row[3]

            pm.pmis.move(last_idx, idx)
            last_idx += 1
            idx += 1

        if self.left:
            pmi = pm.pmis.add()
            pmi.mode = 'EMPTY'
            pmi.text = "column"
            pm.pmis.move(last_idx, idx)

        tag_redraw()

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return prefs().rmc_clipboard is not None


class WM_OT_rmi_specials_call(bpy.types.Operator):
    bl_idname = "wm.rmi_specials_call"
    bl_label = ""
    bl_description = "Menu"
    bl_options = {'INTERNAL'}

    pm_item: bpy.props.IntProperty()

    def _draw(self, menu, context):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.pm_item]

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')
        text, icon, *_ = pmi.parse()
        lh.label(shorten_str(text) if text.strip() else "Menu", icon)
        lh.sep(check=True)

        if pmi.mode != 'EMPTY':
            lh.operator(
                WM_OT_pmi_data_edit.bl_idname,
                "Edit Slot", 'TEXT',
                idx=self.pm_item,
                ok=False)

        lh.sep(check=True)

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Slot", 'ZOOMIN',
            index=self.pm_item,
            mode='ITEM')

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Label", 'ZOOMIN',
            index=self.pm_item,
            mode='LABEL')

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Separator", 'ZOOMIN',
            index=self.pm_item,
            mode='SEPARATOR')

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Spacer", 'ZOOMIN',
            index=self.pm_item,
            mode='SPACER')

        lh.sep(check=True)

        lh.operator(
            WM_OT_rmi_add.bl_idname, "Split Column", 'FULLSCREEN_ENTER',
            index=self.pm_item,
            mode='COLUMN')

        lh.sep(check=True)

        if pmi.mode != 'EMPTY':
            lh.operator(
                PME_OT_pmi_copy.bl_idname, None, 'COPYDOWN',
                idx=self.pm_item)

        if pmi.mode != 'EMPTY':
            if pr.pmi_clipboard.has_data():
                lh.operator(
                    PME_OT_pmi_paste.bl_idname, None, 'PASTEDOWN',
                    idx=self.pm_item)

        lh.sep(check=True)

        lh.operator(
            WM_OT_rmi_move.bl_idname, "Move Slot", 'FORWARD',
            pm_item=self.pm_item,
            idx=-1)

        lh.sep(check=True)
        lh.operator(
            PME_OT_pmi_toggle.bl_idname,
            "Enabled" if pmi.enabled else "Disabled", ic_eye(pmi.enabled),
            pm=pm.name, pmi=self.pm_item)

        lh.sep(check=True)

        lh.operator(
            PME_OT_pmi_remove.bl_idname,
            "Remove", 'X',
            idx=self.pm_item)

    def execute(self, context):
        context.window_manager.popup_menu(self._draw)
        return {'FINISHED'}


pme.props.BoolProperty("rm", "rm_title", True)


class Editor(EditorBase):

    def __init__(self):
        self.id = 'RMENU'
        EditorBase.__init__(self)

        self.docs = "#Regular_Menu_Editor"
        self.default_pmi_data = "rm?"
        self.supported_open_modes = {'PRESS', 'HOLD', 'DOUBLE_CLICK'}

    def init_pm(self, pm):
        super().init_pm(pm)
        extend_panel(pm)

    def on_pm_add(self, pm):
        pmi = pm.pmis.add()
        pmi.mode = 'COMMAND'
        pmi.name = "Slot"
        extend_panel(pm)

    def on_pm_remove(self, pm):
        super().on_pm_remove(pm)

        unextend_panel(pm)

    def on_pm_enabled(self, pm, value):
        super().on_pm_enabled(pm, value)
        if value:
            extend_panel(pm)
        else:
            unextend_panel(pm)

    def on_pm_rename(self, pm, name):
        unextend_panel(pm)
        super().on_pm_rename(pm, name)
        extend_panel(pm)

    def draw_extra_settings(self, layout, pm):
        EditorBase.draw_extra_settings(self, layout, pm)
        layout.prop(pm, "rm_title")

    def draw_slots(self, layout, data):
        pass

    def draw_items(self, layout, pm):
        column = layout.box()
        row = column.row()

        column = row.column(align=True)

        scale_y = 0
        max_scale_y = 0
        idx = -1
        for pmi in pm.pmis:
            idx += 1
            if pmi.mode == 'EMPTY':
                if not pmi.text:
                    lh.row(column, active=pmi.enabled)
                    lh.operator(
                        WM_OT_rmi_specials_call.bl_idname,
                        " ",
                        pm_item=idx)
                    lh.layout.scale_y = SEPARATOR_SCALE_Y
                    scale_y += SEPARATOR_SCALE_Y
                    continue

                elif pmi.text == "spacer":
                    lh.row(column, active=pmi.enabled)
                    lh.operator(
                        WM_OT_rmi_specials_call.bl_idname,
                        " ",
                        pm_item=idx)
                    lh.layout.active = False
                    scale_y += 1
                    continue

                elif pmi.text == "column":
                    if scale_y > 0:
                        column.separator()
                        scale_y += SPACER_SCALE_Y

                    lh.row(column)
                    lh.operator(
                        WM_OT_rmi_add.bl_idname, "Add Slot",
                        index=idx,
                        mode='ITEM')
                    lh.operator(
                        WM_OT_rm_col_specials_call.bl_idname,
                        "", 'COLLAPSEMENU',
                        col_idx=idx)

                    if max_scale_y < scale_y:
                        max_scale_y = scale_y
                    scale_y = 0

                    column = row.column(align=True)
                    continue

            lh.row(column, active=pmi.enabled)

            if pmi.mode == 'EMPTY':
                lh.operator(
                    PME_OT_input_box.bl_idname, "",
                    'FONT_DATA',
                    prop="prefs().selected_pm.pmis[%d].name" % idx)
            else:
                lh.operator(
                    WM_OT_pmi_data_edit.bl_idname, "",
                    self.icon,
                    idx=idx,
                    ok=False)

            if pmi.mode == 'EMPTY' and pmi.text != "label":
                icon = 'BLANK1'
            else:
                icon = pmi.parse_icon('FILE_HIDDEN')

            lh.operator(
                WM_OT_pmi_icon_select.bl_idname, "", icon,
                idx=idx,
                icon="")

            lh.prop(
                pmi, "name", "",
                enabled=pmi.mode != 'EMPTY' or pmi.text == "label")

            lh.operator(
                WM_OT_rmi_specials_call.bl_idname,
                "", 'COLLAPSEMENU',
                pm_item=idx)

            scale_y += 1

        if scale_y > 0:
            column.separator()
            scale_y += SPACER_SCALE_Y

        if max_scale_y < scale_y:
            max_scale_y = scale_y

        lh.row(column)
        lh.operator(
            WM_OT_rmi_add.bl_idname, "Add Slot",
            index=-1,
            mode='ITEM')
        lh.operator(
            WM_OT_rm_col_specials_call.bl_idname, "", 'COLLAPSEMENU',
            col_idx=idx + 1)

        column = row.column(align=True)
        lh.lt(column)
        row = lh.row(column)
        row.scale_y = max_scale_y + 1

        lh.operator(
            WM_OT_rmi_add.bl_idname, "", 'ZOOMIN',
            index=-1,
            mode='COLUMN')


def register():
    Editor()

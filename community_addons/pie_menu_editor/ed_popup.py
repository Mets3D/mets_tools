import bpy
import re
from .ed_base import (
    EditorBase, PME_OT_pmi_copy, PME_OT_pmi_paste, WM_OT_pmi_data_edit,
    WM_OT_pmi_icon_select, WM_OT_pmi_icon_tag_toggle, PME_OT_pmi_toggle,
    extend_panel, unextend_panel)
from .addon import prefs, ic, ic_cb, ic_eye
from . import constants as CC
from .layout_helper import lh, draw_pme_layout, Row
from .ui import tag_redraw, shorten_str
from .collection_utils import MoveItemOperator, move_item, remove_item
from .debug_utils import *
from .bl_utils import PME_OT_message_box, ConfirmBoxHandler, enum_item_idx
from .operators import popup_dialog_pie, WM_OT_pme_user_pie_menu_call
from .keymap_helper import CTRL, SHIFT, ALT, OSKEY, test_mods
from . import pme


current_pdi = 0
cur_row = Row()
prev_row = Row()


def merge_empties(pm, idx):
    pp = pme.props
    pmi = idx < len(pm.pmis) and pm.pmis[idx]
    prev = idx - 1 < len(pm.pmis) and pm.pmis[
        idx - 1]
    ret = False

    if prev and prev.mode == 'EMPTY' and pmi and pmi.mode == 'EMPTY':
        pprop = pp.parse(prev.text)
        prop = pp.parse(pmi.text)

        if pprop.type == "row" and prop.type == "spacer":
            if prop.hsep not in {'NONE', 'ALIGNER'}:
                ret = True
                pmi.text = pp.encode(pmi.text, "hsep", 'NONE')
                if pp.parse(pmi.text).is_empty:
                    pm.pmis.remove(idx)

        elif pprop.type == "spacer" and prop.type == "row":
            if pprop.hsep != 'ALIGNER':
                ret = True
                pm.pmis.remove(idx - 1)
                idx -= 1

        elif pprop.type == "spacer" and prop.type == "spacer":
            if pprop.subrow == 'BEGIN' and prop.subrow == 'BEGIN':
                ret = True
                pmi.text = pp.encode(pmi.text, "subrow", 'NONE')
                if pp.parse(pmi.text).is_empty:
                    pm.pmis.remove(idx)

            elif pprop.subrow == 'BEGIN' and prop.subrow == 'END':
                ret = True
                pmi.text = pp.encode(pmi.text, "subrow", 'NONE')
                if pp.parse(pmi.text).is_empty:
                    pm.pmis.remove(idx)

                prev.text = pp.encode(
                    prev.text, "subrow", 'NONE')
                if pp.parse(prev.text).is_empty:
                    pm.pmis.remove(idx - 1)
                    idx -= 1

            elif pprop.subrow != 'NONE' and prop.subrow == 'COLUMN':
                ret = True
                pm.pmis.remove(idx - 1)
                idx -= 1

            elif pprop.hsep == 'COLUMN' and prop.hsep == 'SPACER':
                pmi.text = pp.encode(pmi.text, "hsep", 'NONE')
                ret = True
                if pp.parse(pmi.text).is_empty:
                    pm.pmis.remove(idx)

            elif pprop.hsep == 'SPACER' and prop.hsep == 'COLUMN':
                prev.text = pp.encode(prev.text, "hsep", 'NONE')
                ret = True
                if pp.parse(prev.text).is_empty:
                    pm.pmis.remove(idx - 1)
                    idx -= 1

            elif pprop.hsep == 'COLUMN' and prop.hsep == 'COLUMN':
                ret = True
                pm.pmis.remove(idx)

            elif pprop.hsep == 'SPACER' and prop.hsep == 'SPACER':
                ret = True
                pm.pmis.remove(idx)

            elif pprop.hsep == 'ALIGNER' and prop.hsep == 'ALIGNER':
                ret = True
                pm.pmis.remove(idx)

            elif pprop.hsep == 'SPACER' and prop.hsep == 'ALIGNER':
                ret = True
                pm.pmis.remove(idx - 1)
                idx -= 1

            elif pprop.hsep == 'ALIGNER' and prop.hsep == 'SPACER':
                ret = True
                pm.pmis.remove(idx)

    elif prev and prev.mode == 'EMPTY' and not pmi:
        pprop = pp.parse(prev.text)
        if pprop.type != "spacer" or pprop.hsep != 'ALIGNER':
            ret = True
            pm.pmis.remove(idx - 1)
            idx -= 1

    return idx, ret


class PME_OT_pdi_add(bpy.types.Operator):
    bl_idname = "pme.pdi_add"
    bl_label = "Add Row or Button"
    bl_description = "Add a row or a button"
    bl_options = {'INTERNAL'}

    mode: bpy.props.StringProperty()
    idx: bpy.props.IntProperty()
    row_idx: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        if self.mode == 'BUTTON':
            pm.ed.add_pd_button(pm, self.idx)
            if pr.use_spacer:
                sp_idx = self.idx
                if self.idx == current_pdi:
                    sp_idx += 1
                spacer = pm.ed.add_pd_spacer(pm, sp_idx)
                spacer.text = "spacer?hsep=SPACER"

        elif self.mode == 'ROW':
            pm.ed.add_pd_row(pm, self.idx, False, self.row_idx)

        elif self.mode == 'SPLIT':
            prev = pm.pmis[self.idx - 1]
            if prev.mode == 'EMPTY' and prev.text.startswith("spacer"):
                pm.pmis.remove(self.idx - 1)
                self.idx -= 1

            pm.ed.add_pd_row(pm, self.idx, True)

        tag_redraw()
        return {'FINISHED'}


class PME_OT_pdi_move(bpy.types.Operator):
    bl_idname = "pme.pdi_move"
    bl_label = ""
    bl_description = "Move an item"
    bl_options = {'INTERNAL'}

    pm_item: bpy.props.IntProperty()
    idx: bpy.props.IntProperty()

    def _draw(self, menu, context):
        pm = prefs().selected_pm

        layout = menu.layout.menu_pie()
        layout.separator()
        layout.separator()
        column = layout.box()
        column = column.column(align=True)
        lh.lt(column)

        def draw_pmi(pr, pm, pmi, idx):
            text, icon, _, icon_only, hidden, _ = pmi.parse_edit()

            # if not text and not hidden:
            #     text = button_text(pmi, text)
            #     # if pmi.mode == 'CUSTOM' or pmi.mode == 'PROP' and (
            #     #         pmi.is_expandable_prop() or icon == 'NONE'):
            #     #     if icon_only and pmi.mode != 'CUSTOM':
            #     #         text = "[%s]" % pmi.name if pmi.name else " "
            #     #     else:
            #     #         text = pmi.name if pmi.name else " "

            lh.operator(
                PME_OT_pdi_move.bl_idname, text, icon,
                pm_item=self.pm_item,
                idx=idx)

        draw_pme_layout(pm, column, draw_pmi)

    def execute(self, context):
        pm = prefs().selected_pm

        if self.idx != self.pm_item:
            pm.pmis.move(self.pm_item, self.idx)
            idx2 = \
                self.idx - 1 if self.pm_item < self.idx else self.idx + 1
            if idx2 != self.pm_item:
                pm.pmis.move(idx2, self.pm_item)

        tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        if self.idx == -1:
            popup_dialog_pie(event, self._draw)
        else:
            self.execute(context)

        return {'FINISHED'}


class PME_OT_pdi_remove(ConfirmBoxHandler, bpy.types.Operator):
    bl_idname = "pme.pdi_remove"
    bl_label = "Remove"
    bl_description = "Remove the item"
    bl_options = {'INTERNAL'}

    pm_item: bpy.props.IntProperty()
    delete: bpy.props.BoolProperty()

    def on_confirm(self, value):
        if not value:
            return

        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[self.pm_item]

        if self.delete:
            pm.pmis.remove(self.pm_item)
            if pm.mode == 'DIALOG':
                while True:
                    self.pm_item, merged = merge_empties(pm, self.pm_item)
                    if not merged:
                        break
                self.pm_item -= 1
                r = Row()
                r.find_ab(pm, self.pm_item)
                r.find_columns(pm)
                if r.num_columns < 2:
                    r.remove_subrows(pm)

        else:
            pmi.text = ""
            pmi.name = ""
            pmi.icon = ""
            pmi.mode = 'EMPTY'

        pr.update_tree()
        tag_redraw()

        return {'FINISHED'}


class PME_OT_pdr_fixed_col_set(bpy.types.Operator):
    bl_idname = "pme.pdr_fixed_col_set"
    bl_label = ""
    bl_description = "Use columns with fixed width"
    bl_options = {'INTERNAL'}

    row_idx: bpy.props.IntProperty()
    value: bpy.props.BoolProperty()

    def execute(self, context):
        pm = prefs().selected_pm
        pmi = pm.pmis[self.row_idx]
        pmi.text = pme.props.encode(pmi.text, "fixed_col", self.value)

        tag_redraw()

        return {'FINISHED'}


class PME_OT_pdr_fixed_but_set(bpy.types.Operator):
    bl_idname = "pme.pdr_fixed_but_set"
    bl_label = ""
    bl_description = "Use buttons with fixed width"
    bl_options = {'INTERNAL'}

    row_idx: bpy.props.IntProperty()
    value: bpy.props.BoolProperty()

    def execute(self, context):
        pm = prefs().selected_pm
        pmi = pm.pmis[self.row_idx]
        pmi.text = pme.props.encode(pmi.text, "fixed_but", self.value)

        tag_redraw()

        return {'FINISHED'}


class PME_OT_pdr_prop_set(bpy.types.Operator):
    bl_idname = "pme.pdr_prop_set"
    bl_label = ""
    bl_options = {'INTERNAL'}

    mode: bpy.props.StringProperty()
    prop: bpy.props.StringProperty()
    value: bpy.props.StringProperty(options={'SKIP_SAVE'})
    toggle: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        pr = prefs()
        pp = pme.props
        pm = pr.selected_pm

        if self.toggle:
            if self.mode == 'PDI':
                pmi = pm.pmis[current_pdi - 1]
                pmi = pmi.mode == 'EMPTY' and pmi.text.startswith(
                    "spacer") and pmi
            else:
                pmi = pm.pmis[cur_row.a]

            if pmi:
                prop = pme.props.parse(pmi.text)
                self.value = getattr(prop, self.prop)
            else:
                self.value = ""

            items = pme.props.get(self.prop).items
            if self.value == 'ALIGNER':
                return {'FINISHED'}

            elif self.value:
                idx = -1
                for i, item in enumerate(items):
                    if item[0] == self.value:
                        idx = i + 1
                        break
                n = len(items)
                if self.prop in {"vspacer", "hsep"}:
                    n = 2
                self.value = items[idx % n][0]
            else:
                self.value = items[1][0]

            if self.prop == "hsep":
                if current_pdi == cur_row.a + 1:
                    return {'FINISHED'}

        if self.mode == 'ROW':
            row = pm.pmis[cur_row.a]
            row.text = pme.props.encode(
                row.text, self.prop, self.value)

        elif self.mode == 'ALIGN_ROWS':
            row_pmis = []
            i = cur_row.a
            while i >= 0:
                pmi = pm.pmis[i]
                if i == 0:
                    row_pmis.append(pmi)
                    break
                if pmi.mode == 'EMPTY' and pmi.text.startswith("row"):
                    row_pmis.append(pmi)
                    prop = pme.props.parse(pmi.text)
                    if prop.vspacer != 'NONE':
                        break
                i -= 1

            i = cur_row.b
            while i < len(pm.pmis):
                pmi = pm.pmis[i]
                if pmi.mode == 'EMPTY' and pmi.text.startswith("row"):
                    prop = pme.props.parse(pmi.text)
                    if prop.vspacer == 'NONE':
                        row_pmis.append(pmi)
                    else:
                        break
                i += 1

            for pmi in row_pmis:
                pmi.text = pme.props.encode(
                    pmi.text, self.prop, self.value)

        elif self.mode == 'ALL_ROWS':
            r = None
            prev_row_has_columns = False
            cur_row_has_columns = False
            for i, pmi in enumerate(pm.pmis):
                if pmi.mode == 'EMPTY' and pmi.text.startswith("row"):
                    value = self.value
                    if self.prop == "vspacer" and self.value == 'NONE':
                        if not r:
                            r = Row()
                        else:
                            prev_row_has_columns = cur_row_has_columns

                        r.find_ab(pm, i)
                        r.find_columns(pm)
                        cur_row_has_columns = r.num_columns > 0

                        if prev_row_has_columns or cur_row_has_columns:
                            value = 'NORMAL'

                    pmi.text = pme.props.encode(
                        pmi.text, self.prop, value)

        elif self.mode == 'PDI':
            prev_pdi = pm.pmis[current_pdi - 1]
            if prev_pdi.mode == 'EMPTY' and prev_pdi.text.startswith("spacer"):
                prop = pp.parse(prev_pdi.text)
                remove_subrows = False
                if prop.hsep == 'COLUMN' and \
                        self.prop == "hsep" and self.value != 'COLUMN' and \
                        cur_row.num_columns == 2:
                    remove_subrows = True

                if prop.subrow == 'END' and \
                        self.prop == "hsep" and self.value == 'COLUMN':
                    prev_pdi.text = pp.encode(prev_pdi.text, "subrow", 'NONE')

                prev_pdi.text = pp.encode(
                    prev_pdi.text, self.prop, self.value)
                if self.value == 'NONE' and \
                        pp.parse(prev_pdi.text).is_empty:
                    pm.pmis.remove(current_pdi - 1)
                    cur_row.b -= 1

                if remove_subrows:
                    cur_row.remove_subrows(pm)

            else:
                prev_pdi = pm.ed.add_pd_spacer(pm, current_pdi)
                prev_pdi.text = pp.encode(
                    prev_pdi.text, self.prop, self.value)
                cur_row.b += 1

            if self.prop == "hsep" and self.value == 'COLUMN':
                pmi = cur_row.b < len(pm.pmis) and pm.pmis[cur_row.b]
                if pmi and pp.parse(pmi.text).vspacer == 'NONE':
                    pmi.text = pp.encode(pmi.text, "vspacer", 'NORMAL')

                pmi = cur_row.a > 0 and pm.pmis[cur_row.a]
                if pmi and pp.parse(pmi.text).vspacer == 'NONE':
                    pmi.text = pp.encode(pmi.text, "vspacer", 'NORMAL')

        tag_redraw()
        return {'FINISHED'}


class PME_OT_pdr_copy(bpy.types.Operator):
    bl_idname = "pme.pdr_copy"
    bl_label = "Copy Row"
    bl_description = "Copy the row"
    bl_options = {'INTERNAL'}

    row_idx: bpy.props.IntProperty()
    row_last_idx: bpy.props.IntProperty()

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        if not pr.pdr_clipboard:
            tag_redraw()

        pr.pdr_clipboard.clear()

        for i in range(self.row_idx, self.row_last_idx):
            pmi = pm.pmis[i]
            pr.pdr_clipboard.append((pmi.name, pmi.icon, pmi.mode, pmi.text))

        return {'FINISHED'}


class PME_OT_pdr_paste(bpy.types.Operator):
    bl_idname = "pme.pdr_paste"
    bl_label = "Paste Row"
    bl_description = "Paste the row"
    bl_options = {'INTERNAL'}

    row_idx: bpy.props.IntProperty()
    row_last_idx: bpy.props.IntProperty()

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm

        last_idx = len(pm.pmis)
        idx = self.row_idx

        for row in pr.pdr_clipboard:
            pmi = pm.pmis.add()
            pmi.name = row[0]
            pmi.icon = row[1]
            pmi.mode = row[2]
            pmi.text = row[3]

            if self.row_idx != -1:
                pm.pmis.move(last_idx, idx)
                last_idx += 1
                idx += 1

        tag_redraw()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return prefs().pdr_clipboard is not None


class PME_OT_pdr_move(bpy.types.Operator, MoveItemOperator):
    bl_idname = "pme.pdr_move"
    bl_label = ""
    bl_description = "Move the row"

    def get_collection(self):
        return prefs().selected_pm.pmis

    def finish(self):
        tag_redraw()

    # def draw_menu(self, menu, context):
    #     layout = menu.layout
    #     pr = prefs()

    #     prev_p = None
    #     for i, tab in enumerate(pr.tabs):
    #         if not tab.is_row:
    #             continue

    #         p = layout.operator(self.bl_idname, text=tab.label)
    #         p.swap = False
    #         p.old_idx = self.old_idx
    #         p.old_idx_last = self.old_idx_last
    #         p.new_idx = i

    #         if prev_p and self.old_idx < prev_p.new_idx:
    #             prev_p.new_idx = i - 1

    #         prev_p = p

    #     if prev_p and self.old_idx < prev_p.new_idx:
    #         prev_p.new_idx = i

    # rows = []

    def draw_menu(self, menu, context):
        pr = prefs()
        pm = pr.selected_pm
        lh.lt(menu.layout)

        lh.label("Move Row", 'FORWARD')
        lh.sep()

        row_idx = 1
        prev_p = None
        for i, pmi in enumerate(pm.pmis):
            if pmi.mode == 'EMPTY' and pmi.text.startswith("row"):
                icon = 'SPACE2' if self.old_idx == i else 'SPACE3'
                new_idx = i

                p = lh.operator(
                    PME_OT_pdr_move.bl_idname, "Row %d" % row_idx, icon,
                    new_idx=new_idx,
                    old_idx=self.old_idx, old_idx_last=self.old_idx_last)

                if prev_p and self.old_idx < prev_p.new_idx:
                    prev_p.new_idx = i - 1

                row_idx += 1
                prev_p = p

        if prev_p and self.old_idx < prev_p.new_idx:
            prev_p.new_idx = i

        # idx = 0
        # for idx, row in enumerate(PME_OT_pdr_move.rows):
        #     icon = 'SPACE2' if self.row_idx == row[0] else 'SPACE3'
        #     lh.operator(
        #         PME_OT_pdr_move.bl_idname, "Row %d" % (idx + 1), icon,
        #         move_idx=idx,
        #         row_idx=self.row_idx)

        # lh.operator(
        #     PME_OT_pdr_move.bl_idname, ". . .", 'SPACE3',
        #     move_idx=idx + 1,
        #     row_idx=self.row_idx)

    # def execute(self, context):
    #     pm = prefs().selected_pm

    #     if self.move_idx == -1:
    #         rows = []
    #         row_idx = -1
    #         for idx, pmi in enumerate(pm.pmis):
    #             if pmi.mode == 'EMPTY' and pmi.text.startswith("row"):
    #                 if row_idx == -1:
    #                     row_idx = idx
    #                 else:
    #                     rows.append((row_idx, idx))
    #                     row_idx = idx
    #         if row_idx != -1:
    #             rows.append((row_idx, idx + 1))

    #         PME_OT_pdr_move.rows = rows

    #         context.window_manager.popup_menu(
    #             self._draw, title=PME_OT_pdr_move.bl_description)

    #     else:
    #         if self.move_idx < len(PME_OT_pdr_move.rows):
    #             move_idx = PME_OT_pdr_move.rows[self.move_idx][0]
    #         else:
    #             move_idx = PME_OT_pdr_move.rows[-1][1]

    #         for row in PME_OT_pdr_move.rows:
    #             if row[0] == self.row_idx:
    #                 row_idx, row_last_idx = row
    #                 break

    #         if move_idx == row_idx or move_idx == row_last_idx:
    #             return {'CANCELLED'}

    #         for i in range(0, row_last_idx - row_idx):
    #             if row_idx < move_idx:
    #                 pm.pmis.move(row_last_idx - 1 - i, move_idx - 1 - i)
    #             else:
    #                 pm.pmis.move(row_idx + i, move_idx + i)

    #         tag_redraw()

    #     return {'FINISHED'}


class PME_OT_pdr_remove(ConfirmBoxHandler, bpy.types.Operator):
    bl_idname = "pme.pdr_remove"
    bl_label = "Remove Row"
    bl_description = "Remove the row"
    bl_options = {'INTERNAL'}

    title = "Remove Row"

    row_idx: bpy.props.IntProperty()
    row_last_idx: bpy.props.IntProperty()
    mode: bpy.props.StringProperty()

    def on_confirm(self, value):
        if not value:
            return

        pm = prefs().selected_pm

        if self.mode == 'JOIN':
            pm.pmis.remove(self.row_idx)
            i = self.row_idx
            while i < len(pm.pmis):
                pmi = pm.pmis[i]
                if pmi.mode == 'EMPTY':
                    if pmi.text.startswith("row"):
                        break

                    prop = pme.props.parse(pmi.text)
                    if prop.type == "spacer" and (
                            prop.hsep == 'ALIGNER' or prop.hsep == 'COLUMN'):
                        pm.pmis.remove(i)
                        continue
                i += 1
            tag_redraw()
            return

        if self.row_last_idx < len(pm.pmis):
            self.row_idx += 1
            self.row_last_idx += 1

        for i in range(self.row_idx, self.row_last_idx):
            pm.pmis.remove(self.row_idx)

        tag_redraw()


class PME_OT_pdi_alignment(bpy.types.Operator):
    bl_idname = "pme.pdi_alignment"
    bl_label = ""
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()
    value: bpy.props.StringProperty()

    def execute(self, context):
        pr = prefs()
        pm = pr.selected_pm
        pp = pme.props
        self.idx

        cur_row = Row()
        cur_row.find_ab(pm, self.idx)
        cur_row.find_columns(pm)

        if not self.value:
            if cur_row.r != -1:
                remove_item(pm.pmis, cur_row.r)
            if cur_row.l != -1:
                remove_item(pm.pmis, cur_row.l)

        elif self.value == 'LEFT':
            if cur_row.l == -1:
                cur_row.l = self.idx + 1
                prev_pdi = pm.ed.add_pd_spacer(pm, cur_row.l)
                prev_pdi.text = pp.encode(
                    prev_pdi.text, "hsep", 'ALIGNER')

            elif cur_row.r == -1:
                if self.idx > cur_row.l:
                    self.idx = move_item(
                        pm.pmis, cur_row.l, self.idx,
                        [self.idx])
                    cur_row.l = self.idx + 1

            else:
                if self.idx >= cur_row.r - 1:
                    cur_row.r = move_item(
                        pm.pmis, cur_row.l, self.idx,
                        [cur_row.r])
                    remove_item(
                        pm.pmis, cur_row.r)
                    cur_row.r = -1

                elif self.idx > cur_row.l:
                    move_item(pm.pmis, cur_row.l, self.idx)
                    cur_row.r = self.idx

        elif self.value == 'CENTER':
            if cur_row.l == -1:
                cur_row.l = self.idx
                prev_pdi = pm.ed.add_pd_spacer(pm, cur_row.l)
                prev_pdi.text = pp.encode(
                    prev_pdi.text, "hsep", 'ALIGNER')
                cur_row.b += 1
                cur_row.r = self.idx + 2
                prev_pdi = pm.ed.add_pd_spacer(pm, cur_row.r)
                prev_pdi.text = pp.encode(
                    prev_pdi.text, "hsep", 'ALIGNER')

            elif cur_row.r == -1:
                if cur_row.l < self.idx:
                    cur_row.r = self.idx + 1
                    prev_pdi = pm.ed.add_pd_spacer(pm, cur_row.r)
                    prev_pdi.text = pp.encode(
                        prev_pdi.text, "hsep", 'ALIGNER')

                else:
                    cur_row.r = cur_row.l
                    cur_row.l = self.idx
                    prev_pdi = pm.ed.add_pd_spacer(pm, cur_row.l)
                    prev_pdi.text = pp.encode(
                        prev_pdi.text, "hsep", 'ALIGNER')

            else:
                if self.idx < cur_row.l:
                    move_item(pm.pmis, cur_row.l, self.idx)
                    cur_row.l = self.idx

                elif self.idx > cur_row.r:
                    move_item(pm.pmis, cur_row.r, self.idx)
                    cur_row.r = self.idx

        elif self.value == 'RIGHT':
            if cur_row.l == -1:
                cur_row.l = self.idx
                prev_pdi = pm.ed.add_pd_spacer(pm, cur_row.l)
                prev_pdi.text = pp.encode(
                    prev_pdi.text, "hsep", 'ALIGNER')

            elif cur_row.r == -1:
                if self.idx < cur_row.l:
                    move_item(
                        pm.pmis, cur_row.l, self.idx)
                    cur_row.l = self.idx

            else:
                if self.idx <= cur_row.l + 1:
                    cur_row.l = move_item(
                        pm.pmis, cur_row.r, self.idx,
                        [cur_row.l])
                    remove_item(
                        pm.pmis, cur_row.l)
                    cur_row.r = -1

                elif self.idx < cur_row.r:
                    move_item(pm.pmis, cur_row.r, self.idx)
                    cur_row.r = self.idx

        if self.value:
            if cur_row.r != -1:
                idx = cur_row.r + 1
                while True:
                    idx, merged = merge_empties(pm, idx)
                    if not merged:
                        break
                idx -= 1
                while True:
                    idx, merged = merge_empties(pm, idx)
                    if not merged:
                        break

            if cur_row.l != -1:
                idx = cur_row.l + 1
                while True:
                    idx, merged = merge_empties(pm, idx)
                    if not merged:
                        break
                idx -= 1
                while True:
                    idx, merged = merge_empties(pm, idx)
                    if not merged:
                        break

        tag_redraw(True)
        return {'FINISHED'}


class PME_MT_pdr_alignment(bpy.types.Menu):
    bl_label = "Row Alignment"

    def draw(self, context):
        pp = pme.props
        pm = prefs().selected_pm
        row = pm.pmis[cur_row.a]
        lh.lt(self.layout)
        col = lh.column()
        col.active = False
        # lh.row()

        # lh.save()
        # lh.column()
        lh.label("Row")
        lh.sep()

        for item in pme.props.get("align").items:
            lh.operator(
                PME_OT_pdr_prop_set.bl_idname, item[1],
                'SPACE2' if pp.parse(
                    row.text).align == item[0] else 'SPACE3',
                mode='ROW',
                prop="align",
                value=item[0])

        lh.lt(self.layout)
        lh.sep()
        lh.operator(
            PME_OT_message_box.bl_idname, "Deprecated", 'INFO',
            title="Deprecated",
            message="Use Button Alignment tools instead")
        # lh.restore()

        # lh.save()
        # lh.column()
        # lh.label("Aligned Rows", icon='MESH_GRID')
        # lh.sep()
        # for item in pme.props.get("align").items:
        #     lh.operator(
        #         PME_OT_pdr_prop_set.bl_idname, item[1],
        #         'SPACE3',
        #         mode='ALIGN_ROWS',
        #         prop="align",
        #         value=item[0])
        # lh.restore()

        # lh.column()
        # lh.label("All Rows", icon='COLLAPSEMENU')
        # lh.sep()
        # for item in pme.props.get("align").items:
        #     lh.operator(
        #         PME_OT_pdr_prop_set.bl_idname, item[1],
        #         'SPACE3',
        #         mode='ALL_ROWS',
        #         prop="align",
        #         value=item[0])


class PME_MT_pdr_size(bpy.types.Menu):
    bl_label = "Row Size"

    def draw(self, context):
        pr = prefs()
        pp = pme.props
        pm = pr.selected_pm
        row = pm.pmis[cur_row.a]
        lh.lt(self.layout)
        lh.row(align=False)

        lh.save()
        lh.column()
        lh.label("Row", icon='ZOOMOUT')
        lh.sep()
        for item in pme.props.get("size").items:
            lh.operator(
                PME_OT_pdr_prop_set.bl_idname, item[1],
                'SPACE2' if pp.parse(
                    row.text).size == item[0] else 'SPACE3',
                mode='ROW',
                prop="size",
                value=item[0])
        lh.restore()

        lh.save()
        lh.column()
        lh.label("Aligned Rows", icon='MESH_GRID')
        lh.sep()
        for item in pme.props.get("size").items:
            lh.operator(
                PME_OT_pdr_prop_set.bl_idname, item[1],
                'SPACE3',
                mode='ALIGN_ROWS',
                prop="size",
                value=item[0])
        lh.restore()

        lh.column()
        lh.label("All Rows", icon='COLLAPSEMENU')
        lh.sep()
        for item in pme.props.get("size").items:
            lh.operator(
                PME_OT_pdr_prop_set.bl_idname, item[1],
                'SPACE3',
                mode='ALL_ROWS',
                prop="size",
                value=item[0])


class PME_MT_pdr_spacer(bpy.types.Menu):
    bl_label = "Row Spacer"

    def draw(self, context):
        pr = prefs()
        pm = pr.selected_pm
        row = pm.pmis[cur_row.a]
        lh.lt(self.layout)
        lh.row(align=False)

        lh.save()
        lh.column()
        lh.label("Row", icon='ZOOMOUT')
        lh.sep()

        for item in pme.props.get("vspacer").items:
            if item[0] == 'NONE' and (
                    prev_row.num_columns > 0 or cur_row.num_columns > 0):
                continue
            lh.operator(
                PME_OT_pdr_prop_set.bl_idname, item[1],
                'SPACE2' if pme.props.parse(
                    row.text).vspacer == item[0] else 'SPACE3',
                mode='ROW',
                prop="vspacer",
                value=item[0])
        lh.restore()

        lh.column()
        lh.label("All Rows", icon='COLLAPSEMENU')
        lh.sep()
        for item in pme.props.get("vspacer").items:
            lh.operator(
                PME_OT_pdr_prop_set.bl_idname, item[1],
                'SPACE3',
                mode='ALL_ROWS',
                prop="vspacer",
                value=item[0])


# class WM_MT_pdi_separator(bpy.types.Menu):
#     bl_label = "Spacer"

#     def draw(self, context):
#         pr = prefs()
#         pp = pme.props
#         pm = pr.selected_pm
#         prev_pmi = pm.pmis[current_pdi - 1]
#         lh.lt(self.layout)

#         for item in pme.props.get("hsep").items:
#             icon = 'SPACE3'
#             if prev_pmi.mode == 'EMPTY' and \
#                     pp.parse(prev_pmi.text).hsep == item[0] or \
#                     prev_pmi.mode != 'EMPTY' and item[0] == 'NONE':
#                 icon = 'SPACE2'

#             lh.operator(
#                 PME_OT_pdr_prop_set.bl_idname, item[1], icon,
#                 mode='PDI',
#                 prop="hsep",
#                 value=item[0])


class PME_OT_pdi_subrow_set(bpy.types.Operator):
    bl_idname = "pme.pdi_subrow_set"
    bl_label = ""
    bl_description = "Mark as a subrow"
    bl_options = {'INTERNAL'}

    mode: bpy.props.StringProperty()
    value: bpy.props.StringProperty()

    def execute(self, context):
        pm = prefs().selected_pm

        def set_subrow_value(idx, new_idx):
            pp = pme.props
            pmi = pm.pmis[idx]
            if pmi.mode == 'EMPTY' and pmi.text.startswith("spacer"):
                prop = pp.parse(pmi.text)

                set_value(pmi, idx, prop, self.value)
            else:
                pmi = pm.ed.add_pd_spacer(pm, new_idx)
                pmi.text = pp.encode(pmi.text, "subrow", self.value)

        def set_value(pmi, idx, prop, value):
            if value == 'NONE' and prop.hsep == 'NONE':
                pm.pmis.remove(idx)
            else:
                pmi.text = pme.props.encode(
                    pmi.text, "subrow", value)

        def remove_subrows(idx):
            i = idx
            if self.mode == 'BEGIN':
                i += 1
            elif self.mode == 'END':
                i += 2
            while i < len(pm.pmis):
                pmi = pm.pmis[i]
                if pmi.mode == 'EMPTY':
                    if pmi.text.startswith("row"):
                        break

                    prop = pme.props.parse(pmi.text)
                    if prop.subrow == 'BEGIN':
                        break
                    if prop.subrow == 'END':
                        set_value(pmi, i, prop, 'NONE')
                        break
                    if prop.hsep == 'COLUMN':
                        break
                i += 1

        if self.mode == 'BEGIN':
            set_subrow_value(current_pdi - 1, current_pdi)
            if self.value == 'NONE':
                remove_subrows(current_pdi)

        elif self.mode == 'END':
            set_subrow_value(current_pdi + 1, current_pdi + 1)

        tag_redraw()

        return {'FINISHED'}


class PME_OT_pdi_menu(bpy.types.Operator):
    bl_idname = "pme.pdi_menu"
    bl_label = ""
    bl_description = (
        "Ctrl+LMB - Add Slot (Right)\n"
        "Ctrl+Shift+LMB - Add Slot (Left)\n"
        "Ctrl+Alt+LMB - Remove Slot\n"
        "Shift+LMB - Edit Slot\n"
        "Alt+LMB - Change Icon\n"
        "Alt+OSKey+LMB - Clear Icon\n"
        "Alt+Shift+LMB - Hide Text\n"
        "OSKey+LMB - Toggle Spacer\n"
        "Ctrl+OSKey+LMB - Copy Slot"
    )
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()

    def _draw(self, menu, context):
        pr = prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[current_pdi]

        text, icon, oicon, *_ = pmi.parse()

        has_cols = False
        num_buttons = 0
        for i in range(self.row_idx, self.row_last_idx):
            v = pm.pmis[i]
            if v.mode == 'EMPTY':
                if v.text.startswith("spacer"):
                    prop = pme.props.parse(v.text)
                    if prop.hsep == 'COLUMN':
                        has_cols = True
            else:
                num_buttons += 1

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')
        row = lh.row(align=False)
        lh.column()
        lh.label(shorten_str(text) if text else "Menu", icon)

        lh.sep(check=True)

        lh.operator(
            WM_OT_pmi_data_edit.bl_idname,
            "Edit Slot", 'TEXT',
            idx=self.idx,
            ok=False)

        lh.operator(
            WM_OT_pmi_icon_select.bl_idname,
            "Change Icon", 'FILE_HIDDEN',
            idx=self.idx,
            icon="")

        if oicon or pmi.mode == 'PROP':
            lh.operator(
                WM_OT_pmi_icon_tag_toggle.bl_idname, "Hide Text",
                ic_cb(CC.F_ICON_ONLY in pmi.icon),
                idx=self.idx,
                tag=CC.F_ICON_ONLY)

        lh.operator(
            WM_OT_pmi_icon_tag_toggle.bl_idname, "Visible",
            ic_cb(CC.F_HIDDEN not in pmi.icon),
            idx=self.idx,
            tag=CC.F_HIDDEN)

        lh.sep(check=True)

        lh.operator(
            PME_OT_pdi_add.bl_idname, "Add Slot", 'BACK',
            idx=self.idx,
            mode='BUTTON')

        lh.operator(
            PME_OT_pdi_add.bl_idname, "Add Slot", 'FORWARD',
            idx=self.idx + 1,
            mode='BUTTON')

        if not has_cols and cur_row.num_aligners == 0 and \
                self.idx > self.row_idx + 1:
            lh.operator(
                PME_OT_pdi_add.bl_idname, "Split Row", 'FULLSCREEN_ENTER',
                idx=self.idx,
                mode='SPLIT')

        lh.sep(check=True)

        lh.operator(
            PME_OT_pmi_copy.bl_idname, None, 'COPYDOWN',
            idx=self.idx)

        if pr.pmi_clipboard.has_data():
            lh.operator(
                PME_OT_pmi_paste.bl_idname, None, 'PASTEDOWN',
                idx=self.idx)

        lh.sep(check=True)

        lh.operator(
            PME_OT_pdi_move.bl_idname, "Move Slot", 'ARROW_LEFTRIGHT',
            pm_item=self.idx,
            idx=-1)

        lh.sep(check=True)
        lh.operator(
            PME_OT_pmi_toggle.bl_idname,
            "Enabled" if pmi.enabled else "Disabled", ic_eye(pmi.enabled),
            pm=pm.name, pmi=current_pdi)

        if num_buttons > 1:
            lh.sep(check=True)
            lh.operator(
                PME_OT_pdi_remove.bl_idname,
                "Remove Slot", 'X',
                delete=True,
                pm_item=self.idx,
                confirm=False)
        elif self.row_idx > 0 or self.row_last_idx < len(pm.pmis):
            lh.sep(check=True)
            lh.operator(
                PME_OT_pdr_remove.bl_idname,
                "Remove Row", 'X',
                row_idx=self.row_idx,
                row_last_idx=self.row_last_idx,
                mode='REMOVE',
                confirm=False)

        # if self.idx > self.row_idx + 1:
        if cur_row.l == -1 or \
                cur_row.r == -1 and self.idx != cur_row.l + 1 or \
                cur_row.r != -1 and self.idx != cur_row.r + 1 and \
                self.idx != cur_row.l + 1:
            lh.column(row)
            lh.label("Separator")

            lh.sep(check=True)

            prev_pmi = pm.pmis[self.idx - 1]

            for item in pme.props.get("hsep").items:
                if item[0] == 'ALIGNER':
                    continue

                if item[0] == 'SPACER':
                    if self.idx == self.row_idx + 1 or \
                            self.idx == self.row_idx + 2 and \
                            prev_pmi.text.startswith("spacer"):
                        continue

                if item[0] == 'COLUMN' and \
                        self.subrow_idx != -1 and self.subrow_has_end:
                    continue

                if item[0] == 'COLUMN' and cur_row.num_aligners > 0:
                    continue

                icon = 'RADIOBUT_OFF'
                if prev_pmi.mode == 'EMPTY':
                    if prev_pmi.text.startswith("row"):
                        if item[0] == 'NONE':
                            icon = 'RADIOBUT_ON'

                    else:
                        if pme.props.parse(prev_pmi.text).hsep == item[0]:
                            icon = 'RADIOBUT_ON'

                else:
                    if item[0] == 'NONE':
                        icon = 'RADIOBUT_ON'

                lh.operator(
                    PME_OT_pdr_prop_set.bl_idname, item[1], icon,
                    mode='PDI',
                    prop="hsep",
                    value=item[0])

        if has_cols:
            lh.column(row)
            lh.label("Column")
            lh.sep(check=True)

            # begin_value = is_begin_subrow()
            begin_value = self.subrow_idx == self.idx - 1
            lh.operator(
                PME_OT_pdi_subrow_set.bl_idname,
                "Begin Subrow",
                ic_cb(begin_value),
                mode='BEGIN',
                value='NONE' if begin_value else 'BEGIN')

            # end_value = is_end_subrow()
            end_value = -1
            if self.subrow_has_end:
                if self.subrow_last_idx == self.idx + 1:
                    end_value = 1
            else:
                if self.subrow_last_idx == self.idx + 1:
                    pass
                elif self.subrow_idx != -1:
                    end_value = 0

            if end_value != -1:
                lh.operator(
                    PME_OT_pdi_subrow_set.bl_idname,
                    "End Subrow",
                    ic_cb(end_value),
                    mode='END',
                    value='NONE' if end_value else 'END')

        if cur_row.num_columns == 0:
            lh.column(row)
            lh.label("Alignment")

            lh.sep()

            lh.operator(
                PME_OT_pdi_alignment.bl_idname, "Left", 'BACK',
                idx=self.idx, value='LEFT')
            lh.operator(
                PME_OT_pdi_alignment.bl_idname, "Center", 'ARROW_LEFTRIGHT',
                idx=self.idx, value='CENTER')
            lh.operator(
                PME_OT_pdi_alignment.bl_idname, "Right", 'FORWARD',
                idx=self.idx, value='RIGHT')

            if cur_row.num_aligners > 0:
                lh.operator(
                    PME_OT_pdi_alignment.bl_idname, "Clear", 'X',
                    idx=self.idx, value="")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        pr = prefs()
        pp = pme.props
        pm = pr.selected_pm

        cur_row.find_ab(pm, self.idx)
        cur_row.find_columns(pm)
        prev_row.find_ab(pm, cur_row.a - 1)
        prev_row.find_columns(pm)

        self.row_idx = cur_row.a
        self.row_last_idx = cur_row.b

        self.row_idx = self.idx
        self.subrow_idx = -2
        while self.row_idx > 0:
            pmi = pm.pmis[self.row_idx]
            if pmi.mode == 'EMPTY':
                if pmi.text.startswith("row"):
                    break
                elif pmi.text.startswith("spacer") and self.subrow_idx == -2:
                    prop = pp.parse(pmi.text)
                    if prop.hsep == 'COLUMN':
                        self.subrow_idx = -1
                    if prop.subrow == 'BEGIN':
                        self.subrow_idx = self.row_idx
                    elif prop.subrow == 'END':
                        self.subrow_idx = -1
            self.row_idx -= 1

        self.row_last_idx = self.idx
        self.subrow_last_idx = -2
        self.subrow_has_end = False
        while self.row_last_idx < len(pm.pmis):
            pmi = pm.pmis[self.row_last_idx]
            if pmi.mode == 'EMPTY':
                if pmi.text.startswith("row"):
                    break
                elif pmi.text.startswith("spacer") and \
                        self.subrow_last_idx == -2:
                    prop = pp.parse(pmi.text)
                    if prop.subrow == 'END':
                        self.subrow_has_end = True
                        self.subrow_last_idx = self.row_last_idx
                    elif prop.subrow == 'BEGIN':
                        self.subrow_last_idx = self.row_last_idx
                    if prop.hsep == 'COLUMN':
                        self.subrow_last_idx = self.row_last_idx
            self.row_last_idx += 1

        if self.subrow_idx == -2:
            self.subrow_idx = -1
        if self.subrow_last_idx == -2:
            self.subrow_last_idx = self.row_last_idx

        global current_pdi
        current_pdi = self.idx

        pmi = pm.pmis[self.idx]

        # Add Button (Left)
        if test_mods(event, CTRL | SHIFT):
            bpy.ops.pme.pdi_add(idx=self.idx, mode='BUTTON')

        # Add Button (Right)
        elif test_mods(event, CTRL):
            bpy.ops.pme.pdi_add(idx=self.idx + 1, mode='BUTTON')

        # Toggle Hide Text
        elif test_mods(event, ALT | SHIFT):
            bpy.ops.wm.pmi_icon_tag_toggle(
                'INVOKE_DEFAULT', idx=self.idx, tag=CC.F_ICON_ONLY)

        # Remove Button
        elif test_mods(event, CTRL | ALT):
            if self.row_last_idx - self.row_idx > 2:
                bpy.ops.pme.pdi_remove(
                    'INVOKE_DEFAULT', pm_item=self.idx, delete=True)
            elif self.row_idx > 0 or self.row_last_idx < len(pm.pmis):
                bpy.ops.pme.pdr_remove(
                    'INVOKE_DEFAULT',
                    row_idx=self.row_idx, row_last_idx=self.row_last_idx,
                    mode='REMOVE', confirm=False)

        # Clear Icon
        elif test_mods(event, ALT | OSKEY):
            bpy.ops.wm.pmi_icon_select(
                'INVOKE_DEFAULT', idx=self.idx, icon="NONE")

        # Change Icon
        elif test_mods(event, ALT):
            bpy.ops.wm.pmi_icon_select(
                'INVOKE_DEFAULT', idx=self.idx, icon="")

        # Edit Button
        elif test_mods(event, SHIFT):
            bpy.ops.wm.pmi_data_edit(
                'INVOKE_DEFAULT', idx=self.idx, ok=False)

        # Toggle Separator
        elif test_mods(event, OSKEY):
            bpy.ops.pme.pdr_prop_set(
                'INVOKE_DEFAULT', mode='PDI', prop="hsep", toggle=True)

        # Copy Button
        elif test_mods(event, CTRL | OSKEY):
            bpy.ops.pme.pmi_copy(idx=self.idx)

        # Paste Button
        elif test_mods(event, CTRL | SHIFT | OSKEY):
            if bpy.ops.pme.pmi_paste.poll():
                bpy.ops.pme.pmi_paste(idx=self.idx)
            else:
                return {'CANCELLED'}

        else:
            context.window_manager.popup_menu(self._draw)

        return {'FINISHED'}


class PME_OT_pdr_menu(bpy.types.Operator):
    bl_idname = "pme.pdr_menu"
    bl_label = ""
    bl_description = (
        "Ctrl+LMB - Add Row Below\n"
        "Ctrl+Shift+LMB - Add Row Above\n"
        "Shift+LMB - Toggle Row Size\n"
        "OSKey+LMB - Toggle Row Spacer\n"
    )
    bl_options = {'INTERNAL'}

    row_idx: bpy.props.IntProperty()

    def _draw(self, menu, context):
        pr = prefs()
        pm = pr.selected_pm

        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        # lh.menu(
        #     PME_MT_pdr_alignment.__name__, "Alignment", 'ALIGN',
        #     active=False)
        lh.menu(
            PME_MT_pdr_size.__name__, "Size", 'UV_FACESEL')

        if self.row_idx > 0:
            lh.menu(
                PME_MT_pdr_spacer.__name__, "Spacer", 'SEQ_SEQUENCER')

        r = Row()
        r.find_ab(pm, self.row_idx)
        has_columns = r.has_columns(pm)
        row_prop = pme.props.parse(pm.pmis[self.row_idx].text)
        lh.operator(
            PME_OT_pdr_fixed_but_set.bl_idname,
            "Fixed Buttons",
            ic_cb(row_prop.fixed_but),
            row_idx=self.row_idx,
            value=False if row_prop.fixed_but else True)
        if has_columns:
            lh.operator(
                PME_OT_pdr_fixed_col_set.bl_idname,
                "Fixed Columns",
                ic_cb(row_prop.fixed_col),
                row_idx=self.row_idx,
                value=False if row_prop.fixed_col else True)

        lh.sep(check=True)

        lh.operator(
            PME_OT_pdi_add.bl_idname, "Add Row Above", 'ZOOMIN',
            row_idx=self.row_idx,
            idx=self.row_idx,
            mode='ROW')

        lh.operator(
            PME_OT_pdi_add.bl_idname, "Add Row Below", 'ZOOMIN',
            row_idx=self.row_idx,
            idx=self.row_last_idx,
            mode='ROW')

        if self.row_last_idx < len(pm.pmis):
            lh.operator(
                PME_OT_pdr_remove.bl_idname, "Join Row", 'FULLSCREEN_EXIT',
                row_idx=self.row_last_idx,
                mode='JOIN',
                confirm=False)

        lh.sep(check=True)

        lh.operator(
            PME_OT_pdr_copy.bl_idname, "Copy Row", 'COPYDOWN',
            row_idx=self.row_idx,
            row_last_idx=self.row_last_idx)

        if pr.pdr_clipboard:
            lh.operator(
                PME_OT_pdr_paste.bl_idname, "Paste Row", 'PASTEDOWN',
                row_idx=self.row_idx,
                row_last_idx=self.row_last_idx)

        lh.sep(check=True)

        lh.operator(
            PME_OT_pdr_move.bl_idname, "Move Row", 'FORWARD',
            old_idx=self.row_idx, old_idx_last=self.row_last_idx - 1)
        # lh.operator(
        #     PME_OT_pdr_move.bl_idname, "Move Row", 'ARROW_LEFTRIGHT',
        #     row_idx=self.row_idx,
        #     move_idx=-1)

        if self.row_idx > 0 or self.row_last_idx < len(pm.pmis):
            lh.sep(check=True)
            lh.operator(
                PME_OT_pdr_remove.bl_idname,
                "Remove Row", 'X',
                row_idx=self.row_idx,
                row_last_idx=self.row_last_idx,
                mode='REMOVE')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        pm = prefs().selected_pm

        # cur_row = Row()
        # prev_row = Row()

        prev_row.find_ab(pm, self.row_idx - 1)
        prev_row.find_columns(pm)
        cur_row.find_ab(pm, self.row_idx)
        cur_row.find_columns(pm)

        self.row_last_idx = cur_row.b

        # Add Row (Above)
        if test_mods(event, CTRL | SHIFT):
            bpy.ops.pme.pdi_add(
                'INVOKE_DEFAULT',
                idx=self.row_idx, row_idx=self.row_idx, mode='ROW')

        # Add Row (Below)
        elif test_mods(event, CTRL):
            bpy.ops.pme.pdi_add(
                'INVOKE_DEFAULT',
                idx=self.row_last_idx, row_idx=self.row_idx, mode='ROW')

        # Toggle Row Spacer
        elif test_mods(event, OSKEY):
            bpy.ops.pme.pdr_prop_set(
                'INVOKE_DEFAULT', mode='ROW', prop="vspacer", toggle=True)

        # Toggle Row Size
        elif test_mods(event, SHIFT):
            bpy.ops.pme.pdr_prop_set(
                'INVOKE_DEFAULT', mode='ROW', prop="size", toggle=True)

        else:
            context.window_manager.popup_menu(self._draw, title="Row")
        return {'FINISHED'}


pme.props.EnumProperty(
    "row", "align", 'CENTER', [
        ('CENTER', "Center", 0),
        ('LEFT', "Left", 0),
        ('RIGHT', "Right", 0),
    ])
pme.props.EnumProperty(
    "row", "size", 'NORMAL', [
        ('NORMAL', "Normal", 1),
        ('LARGE', "Large", 1.25),
        ('LARGER', "Larger", 1.5),
    ])
pme.props.EnumProperty(
    "row", "vspacer", 'NORMAL', [
        ('NONE', "None", 0),
        ('NORMAL', "Normal", 1),
        ('LARGE', "Large", 3),
        ('LARGER', "Larger", 5),
    ])
pme.props.BoolProperty("row", "fixed_col", False)
pme.props.BoolProperty("row", "fixed_but", False)
pme.props.EnumProperty(
    "spacer", "hsep", 'NONE', [
        ('NONE', "None", ""),
        ('SPACER', "Spacer", ""),
        ('COLUMN', "Column", ""),
        ('ALIGNER', "Aligner", ""),
    ])
pme.props.EnumProperty(
    "spacer", "subrow", 'NONE', [
        ('NONE', "None", 0),
        ('BEGIN', "Begin", 0),
        ('END', "End", 0),
    ])

pme.props.BoolProperty("pd", "pd_title", True)
pme.props.BoolProperty("pd", "pd_box", True)
pme.props.BoolProperty("pd", "pd_expand")
pme.props.IntProperty("pd", "pd_panel", 1)
pme.props.BoolProperty("pd", "pd_auto_close", False)
pme.props.IntProperty("pd", "pd_width", 300)


class Editor(EditorBase):

    def __init__(self):
        self.id = 'DIALOG'
        EditorBase.__init__(self)

        self.docs = "#Pop-up_Dialog_Editor"
        self.supported_open_modes = {'PRESS', 'HOLD', 'DOUBLE_CLICK'}
        self.default_pmi_data = "pd?pd_panel=1"

    def update_default_pmi_data(self):
        pr = prefs()
        if pr is None:
            return
        self.default_pmi_data = "pd?pd_panel=%d" % enum_item_idx(
            pr, "default_popup_mode", pr.default_popup_mode)

    def init_pm(self, pm):
        super().init_pm(pm)
        extend_panel(pm)

    def on_pm_add(self, pm):
        self.add_pd_row(pm)
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
        old_name = pm.name

        unextend_panel(pm)
        super().on_pm_rename(pm, name)
        extend_panel(pm)

        for v in prefs().pie_menus:
            if v.mode == 'PANEL':
                update_flag = False
                for pmi in v.pmis:
                    if pmi.name == old_name:
                        pmi.name = name
                        update_flag = True

                if update_flag:
                    v.update_panel_group()

    def on_pmi_paste(self, pm, pmi):
        pass

    def draw_extra_settings(self, layout, pm):
        EditorBase.draw_extra_settings(self, layout, pm)
        layout.row(align=True).prop(pm, "pd_panel", expand=True)
        col = layout.column(align=True)
        # col.prop(pm, "pd_expand")

        if pm.pd_panel == 'PIE':
            col.prop(pm, "pd_box")
        else:
            row = col.row(align=True)
            row.prop(pm, "pd_width")

            default_width = pme.props.get("pd_width").default
            if pm.pd_width != default_width:
                row.operator("pme.exec", text="", icon=ic('X')).cmd = \
                    "prefs().selected_pm.pd_width = %d" % default_width

        if pm.pd_panel == 'POPUP':
            col.prop(pm, "pd_title")

    def draw_items(self, layout, pm):
        pr = prefs()

        col = layout.column(align=True)
        row = col.row(align=True)
        column1 = row.box().column(align=True)
        xrow = column1.row()
        xrow.scale_y = 0
        column2 = row.box()
        column2 = column2.column(align=True)

        def draw_pdi(pr, pm, pmi, idx):
            text, icon, _, icon_only, hidden, _ = pmi.parse_edit()

            # if not text and not hidden:
            #     text = button_text(pmi, text)
            #     # # if pmi.mode == 'CUSTOM' or pmi.mode == 'PROP' and (
            #     # if pmi.mode == 'PROP' and (
            #     #         pmi.is_expandable_prop() or icon == 'NONE'):
            #     #     # if icon_only and pmi.mode != 'CUSTOM':
            #     #     if icon_only:
            #     #         text = "[%s]" % pmi.name if pmi.name else " "
            #     #     else:
            #     #         text = pmi.name if pmi.name else " "

            lh.layout.active = not hidden and pmi.enabled

            lh.operator(
                PME_OT_pdi_menu.bl_idname,
                text, icon,
                idx=idx)

        rows = draw_pme_layout(pm, column1, draw_pdi, [])
        DBG_LAYOUT and logi("Rows", rows)

        prev_r = None
        for r in rows:
            if r[0] > 0:
                lh.lt(column2)
                n = r[5]
                if prev_r and prev_r[4] and n == 0:
                    n = 1
                for i in range(0, n):
                    lh.sep()
            row = lh.row(column2)
            row.scale_y = r[1] * r[2] + CC.SPACER_SCALE_Y * r[3]
            lh.operator(
                PME_OT_pdr_menu.bl_idname,
                "", 'COLLAPSEMENU',
                row_idx=r[0])
            prev_r = r

        lh.row(col)
        lh.operator(
            PME_OT_pdi_add.bl_idname, "Add Row",
            idx=-1,
            mode='ROW')

        if pr.pdr_clipboard:
            lh.operator(
                PME_OT_pdr_paste.bl_idname, "Paste Row",
                row_idx=-1)

    def add_pd_button(self, pm, index=-1):
        new_pmi = pm.pmis.add()
        new_pmi.mode = 'COMMAND'
        new_pmi.text = ""

        btn_idx = -1
        num_buttons = 0
        re_btn = re.compile(r"Button (\d+)")
        for pmi in reversed(pm.pmis):
            if pmi.mode != 'EMPTY':
                num_buttons += 1
                name = pmi.name
                mo = re_btn.search(name)
                if mo:
                    btn_idx = max(btn_idx, int(mo.group(1)) + 1)

        if btn_idx == -1:
            btn_idx = num_buttons

        new_pmi.name = "Button %d" % btn_idx

        idx = len(pm.pmis) - 1
        if index != -1 and index != idx:
            pm.pmis.move(idx, index)

        return pm.pmis[index] if index != -1 else new_pmi

    def add_pd_spacer(self, pm, index=-1):
        pmi = pm.pmis.add()
        pmi.mode = 'EMPTY'
        pmi.text = "spacer"

        idx = len(pm.pmis) - 1
        if index != -1 and index != idx:
            pm.pmis.move(idx, index)

        return pm.pmis[index] if index != -1 else pmi

    def add_pd_row(self, pm, idx=-1, split=False, row_idx=-1):
        num_pmis = len(pm.pmis)
        if idx == num_pmis:
            idx = -1

        pmi = pm.pmis.add()
        pmi.mode = 'EMPTY'
        pmi.text = "row"

        if num_pmis:
            if idx == -1:
                r = Row()
                r.find_ab(pm, num_pmis - 1)
                prev_row = pm.pmis[r.a]
                prev_row_prop = pme.props.parse(prev_row.text)

                if not r.has_columns(pm):
                    pmi.text = pme.props.encode(
                        pmi.text, "vspacer",
                        prev_row_prop.vspacer)
                    # else:
                    #     pmi.text = pme.props.encode(
                    #         pmi.text, "vspacer", 'NONE')

                pmi.text = pme.props.encode(
                    pmi.text, "size", prev_row_prop.size)

            else:
                cur_row = pm.pmis[row_idx]
                cur_row_prop = pme.props.parse(cur_row.text)
                prev_row = None
                r = Row()
                r.find_ab(pm, row_idx)
                cur_row_has_columns = r.num_columns > 0
                next_row_has_columns = False
                prev_row_has_columns = False

                if r.b < num_pmis:
                    r.find_ab(pm, r.b)
                    next_row_has_columns = r.num_columns > 0

                if row_idx > 0:
                    r.find_ab(pm, row_idx - 1)
                    prev_row = pm.pmis[r.a]
                    prev_row_has_columns = r.num_columns > 0

                if not split:
                    if idx == row_idx:
                        if not prev_row_has_columns and \
                                not cur_row_has_columns:

                            cur_row.text = pme.props.encode(
                                cur_row.text, "vspacer", 'NONE')
                            pmi.text = pme.props.encode(
                                pmi.text, "vspacer",
                                'NONE' if cur_row_prop.vspacer == 'NONE' else
                                'NORMAL')

                    else:
                        if not next_row_has_columns and \
                                not cur_row_has_columns:

                            pmi.text = pme.props.encode(
                                pmi.text, "vspacer", 'NONE')

                pmi.text = pme.props.encode(
                    pmi.text, "size", cur_row_prop.size)

        last_index = len(pm.pmis) - 1
        if idx != -1 and idx != last_index:
            pm.pmis.move(last_index, idx)
            idx += 1

        if not split:
            pmi = self.add_pd_button(pm, idx)

        return pm.pmis[idx] if idx != -1 else pmi


def register():
    Editor()

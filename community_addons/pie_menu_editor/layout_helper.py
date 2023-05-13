import bpy
from . import pme
from . import c_utils as CTU
from .addon import prefs, print_exc, ic, is_28
from .constants import SCALE_X, SPACER_SCALE_Y, F_CUSTOM_ICON
from .bl_utils import bp, PME_OT_message_box
from .utils import format_exception
from .debug_utils import *
from .previews_helper import ph


L_SEP = 1 << 0
L_LABEL = 1 << 1


class CLayout:
    use_mouse_over_open = None
    real_getattribute = None
    layout = None
    depth = 0

    @staticmethod
    def save():
        CLayout.depth += 1
        if bpy.types.UILayout.__getattribute__ == CLayout.getattribute:
            return

        if not CLayout.real_getattribute:
            CLayout.real_getattribute = bpy.types.UILayout.__getattribute__
        bpy.types.UILayout.__getattribute__ = CLayout.getattribute

    @staticmethod
    def restore():
        CLayout.depth -= 1
        if CLayout.depth > 0:
            return

        if bpy.types.UILayout.__getattribute__ == CLayout.getattribute:
            bpy.types.UILayout.__getattribute__ = CLayout.real_getattribute

    def getattribute(self, attr):
        CLayout.layout = self
        bpy.types.UILayout.__getattribute__ = CLayout.real_getattribute

        if hasattr(CLayout, attr):
            ret = getattr(CLayout, attr)
        else:
            ret = getattr(self, attr)

        bpy.types.UILayout.__getattribute__ = CLayout.getattribute
        return ret

    def menu(
            menu, text=None, text_ctxt="", translate=True, icon='NONE',
            icon_value=0, use_mouse_over_open=None):
        bpy.types.UILayout.__getattribute__ = CLayout.real_getattribute

        if use_mouse_over_open is True or CLayout.use_mouse_over_open is True:
            # UI_LAYOUT_HEADER = 1
            c_layout = CTU.c_layout(CLayout.layout)
            # root_type = c_layout.root.contents.type
            # c_layout.root.contents.type = UI_LAYOUT_HEADER

        elif use_mouse_over_open is False:
            # UI_LAYOUT_PANEL = 0
            c_layout = CTU.c_layout(CLayout.layout)
            # root_type = c_layout.root.contents.type
            # c_layout.root.contents.type = UI_LAYOUT_PANEL

        if text is None:
            CLayout.layout.menu(
                menu,
                text_ctxt=text_ctxt, translate=translate,
                icon=ic(icon), icon_value=icon_value)
        else:
            CLayout.layout.menu(
                menu, text=text, text_ctxt=text_ctxt,
                translate=translate, icon=ic(icon), icon_value=icon_value)

        if use_mouse_over_open is True or CLayout.use_mouse_over_open is True:
            UI_BTYPE_PULLDOWN = 27 << 9
            c_btn = CTU.c_last_btn(c_layout)
            c_btn.type = UI_BTYPE_PULLDOWN
            # c_layout.root.contents.type = root_type

        elif use_mouse_over_open is False:
            UI_BTYPE_MENU = 4 << 9
            c_btn = CTU.c_last_btn(c_layout)
            c_btn.type = UI_BTYPE_MENU
            # c_layout.root.contents.type = root_type

        bpy.types.UILayout.__getattribute__ = CLayout.getattribute


class LayoutHelper:

    def __init__(self, previews_helper=None):
        self.layout = None
        self.saved_layouts = []
        self.ph = previews_helper
        self.prev_sep_group = None
        self.has_sep = False
        self.parent = None
        self.icon_only = False
        self.skip_flags = 0

    def __getattr__(self, name):
        return getattr(self.layout, name, None)

    def blank(self):
        # self.layout.operator("wm.pme_none", text="", icon='BLANK1', emboss=False)
        self.layout.label(text="", icon=ic('BLANK1'))
        self.has_sep = False

    def box(
            self, parent=None, operator_context=None,
            enabled=True, alignment='EXPAND'):
        if parent is None:
            parent = self.layout
        self.parent = parent

        self.layout = parent.box()
        self.layout.alignment = alignment
        self.layout.enabled = enabled
        if operator_context is not None:
            self.layout.operator_context = operator_context

        self.has_sep = True
        return self.layout

    def column(
            self, parent=None, align=True, operator_context=None,
            enabled=True):
        if parent is None:
            parent = self.layout
        self.parent = parent

        self.layout = parent.column(align=align)
        self.enabled = enabled
        if operator_context is not None:
            self.layout.operator_context = operator_context

        self.has_sep = True
        return self.layout

    def label(self, text, icon='NONE'):
        if self.skip_flags & L_LABEL:
            return
        icon, icon_value = self.parse_icon(icon)

        self.layout.label(
            text="" if self.icon_only else text,
            icon=ic(icon), icon_value=icon_value)
        self.has_sep = False

    def lt(self, layout, operator_context=None):
        self.layout = layout
        if operator_context is not None:
            layout.operator_context = operator_context
        self.parent = None
        self.has_sep = True
        self.prev_sep_group = None

    def menu(
            self, menu, text, icon='NONE', enabled=True, active=True,
            use_mouse_over_open=False):
        icon, icon_value = self.parse_icon(icon)

        if not enabled or not active:
            self.save()
            scale_x = self.layout.scale_x
            scale_y = self.layout.scale_y
            self.row(enabled=enabled, active=active)
            self.layout.scale_x = scale_x
            self.layout.scale_y = scale_y

        cl = CLayout.depth > 0
        if use_mouse_over_open:
            if not cl:
                CLayout.save()

            self.layout.menu(
                menu, text=text, icon=ic(icon), icon_value=icon_value,
                use_mouse_over_open=True)

            if not cl:
                CLayout.restore()

        else:
            self.layout.menu(
                menu, text=text, icon=ic(icon),
                icon_value=icon_value)

        self.has_sep = False

        if not enabled or not active:
            self.restore()

    def error(self, txt, message=None):
        if not message:
            message = format_exception(0)

        print_exc()
        self.operator(
            PME_OT_message_box.bl_idname, txt, 'ERROR',
            message=message, icon=ic('ERROR'))

    def operator(
            self, idname, txt=None, icon_id='NONE',
            enabled=True, active=True, emboss=True,
            **props):
        icon_id, icon_value = self.parse_icon(icon_id)

        if not enabled or not active:
            self.save()
            scale_x = self.layout.scale_x
            scale_y = self.layout.scale_y
            self.row(enabled=enabled, active=active)
            self.layout.scale_x = scale_x
            self.layout.scale_y = scale_y

        if self.icon_only:
            txt = ""

        if txt is None:
            pr = self.layout.operator(
                idname, icon=ic(icon_id), icon_value=icon_value, emboss=emboss)
        else:
            pr = self.layout.operator(
                idname, text=txt, icon=ic(icon_id), icon_value=icon_value,
                emboss=emboss)
        if props:
            for p in props.keys():
                setattr(pr, p, props[p])

        if not enabled or not active:
            self.restore()

        self.has_sep = False
        return pr

    def op(
            self, idname, txt=None, icon='NONE',
            enabled=True, active=True, emboss=True):
        def set_props(**props):
            for k, v in props.items():
                setattr(pr, k, v)

            return pr

        icon, icon_value = self.parse_icon(icon)

        if not enabled or not active:
            self.save()
            scale_x = self.layout.scale_x
            scale_y = self.layout.scale_y
            self.row(enabled=enabled, active=active)
            self.layout.scale_x = scale_x
            self.layout.scale_y = scale_y

        if self.icon_only:
            txt = ""

        if txt is None:
            pr = self.layout.operator(
                idname, icon=ic(icon), icon_value=icon_value, emboss=emboss)
        else:
            pr = self.layout.operator(
                idname, text=txt, icon=ic(icon), icon_value=icon_value,
                emboss=emboss)

        if not enabled or not active:
            self.restore()

        self.has_sep = False
        return set_props

    def parse_icon(self, icon):
        icon_value = 0
        icon_id = icon
        if icon.startswith(F_CUSTOM_ICON):
            icon_id = 'CANCEL'
            if self.ph:
                icon = icon[1:]
                if self.ph.has_icon(icon):
                    icon_value = self.ph.get_icon(icon)
                    icon_id = 'NONE'

        return icon_id, icon_value

    def prop(
            self, data, prop, text=None, icon='NONE',
            expand=False, slider=False, toggle=-1, icon_only=False,
            event=False, full_event=False, emboss=True, index=-1,
            enabled=True, active=True, alert=False):
        if not prop.startswith("[") and not hasattr(data, prop):
            # pass
            # return
            raise AttributeError(
                "Property not found: %s.%s" % (type(data).__name__, prop))

        icon, icon_value = self.parse_icon(icon)

        if not enabled or not active or alert:
            self.save()
            scale_x = self.layout.scale_x
            scale_y = self.layout.scale_y
            self.row(enabled=enabled, active=active, alert=alert)
            self.layout.scale_x = scale_x
            self.layout.scale_y = scale_y

        if self.icon_only:
            text = ""

        if text is None:
            self.layout.prop(
                data, prop, icon=ic(icon), icon_value=icon_value,
                expand=expand, slider=slider, toggle=toggle,
                icon_only=icon_only, event=event, full_event=full_event,
                emboss=emboss, index=index)
        else:
            self.layout.prop(
                data, prop, text=text, icon=ic(icon), icon_value=icon_value,
                expand=expand, slider=slider, toggle=toggle,
                icon_only=icon_only, event=event, full_event=full_event,
                emboss=emboss, index=index)

        if not enabled or not active or alert:
            self.restore()

        self.has_sep = False

    def prop_compact(
            self, data, prop, text=None, icon='NONE',
            expand=False, slider=False, toggle=False, icon_only=False,
            event=False, full_event=False, emboss=True, index=-1,
            enabled=True, active=True, alert=False):
        p = data.bl_rna.properties[prop]
        tp = p.__class__.__name__
        size = getattr(p, "array_length", 0)
        if size > 1 or \
                tp == "StringProperty" or \
                tp == "EnumProperty" and not p.is_enum_flag and not expand:
            text = ""
        if size > 1 and (tp == "IntProperty" or tp == "FloatProperty"):
            icon = 'NONE'

        is_row = CTU.is_row(self.layout)
        if is_row:
            if tp == "EnumProperty" and expand:
                icon_only = True
                for v in p.enum_items:
                    if v.name:
                        icon_only = False
                        break

                self.save()
                sy = self.layout.scale_y
                self.layout.scale_y = 1
                self.split() if icon_only else self.row()
                self.layout.scale_y = sy

                for v in p.enum_items:
                    self.layout.prop_enum(data, prop, v.identifier)

                self.restore()
                return

            if size > 1 and tp == "BoolProperty":
                self.save()
                sy = self.layout.scale_y
                self.layout.scale_y = 1
                self.split()
                self.layout.scale_y = sy

                text = ""
                icon = 'NONE'
                for i in range(size):
                    index = i
                    self.prop(
                        data, prop, text, icon, expand, slider,
                        toggle, icon_only,
                        event, full_event, emboss, index,
                        enabled, active, alert)

                self.restore()
                return

        else:
            if tp == "EnumProperty" and expand:
                for v in p.enum_items:
                    self.layout.prop_enum(data, prop, v.identifier)

                return

            if size > 1 and tp == "BoolProperty":
                text = ""
                icon = 'NONE'
                for i in range(size):
                    index = i
                    self.prop(
                        data, prop, text, icon, expand, slider,
                        toggle, icon_only,
                        event, full_event, emboss, index,
                        enabled, active, alert)
                return

        self.prop(
            data, prop, text, icon, expand, slider, toggle, icon_only,
            event, full_event, emboss, index,
            enabled, active, alert)

    def restore(self):
        self.layout = self.saved_layouts.pop()

    def row(
            self, parent=None, align=True, operator_context=None,
            enabled=True, active=True, alert=False, alignment='EXPAND'):
        if parent is None:
            parent = self.layout
        self.parent = parent

        self.layout = parent.row(align=align)
        self.layout.alignment = alignment
        self.layout.enabled = enabled
        self.layout.active = active
        self.layout.alert = alert
        if operator_context is not None:
            self.layout.operator_context = operator_context

        self.has_sep = True
        return self.layout

    def save(self):
        self.saved_layouts.append(self.layout)

    def sep(self, parent=None, check=False, group=None):
        if self.skip_flags & L_SEP:
            return
        if parent is None:
            parent = self.layout
        if group and group != self.prev_sep_group or \
                not group and (not check or not self.has_sep):
            parent.separator()
        self.has_sep = True
        self.prev_sep_group = group

    def skip(self, flags=0):
        self.skip_flags = flags

    def spacer(self):
        self.layout.operator("wm.pme_none", text=" ", emboss=False)
        self.has_sep = False

    def split(self, parent=None, factor=None, align=True):
        if parent is None:
            parent = self.layout
        self.parent = parent

        self.layout = split(parent, factor, align)

        self.has_sep = True
        return self.layout

    def unregister(self):
        self.layout = None
        self.saved_layouts = None
        self.ph = None


class Row:
    def __init__(self):
        self.a = 0
        self.b = 0
        self.l = -1
        self.r = -1
        self.num_columns = 0
        self.num_aligners = 0

    def __str__(self):
        return "Row [%d, %d] |%d|%d| %d cols" % (
            self.a, self.b, self.l, self.r, self.num_columns)

    def find_ab(self, pm, idx):
        self.a = idx
        while self.a > 0:
            pmi = pm.pmis[self.a]
            if pmi.mode == 'EMPTY' and pmi.text.startswith('row'):
                break
            self.a -= 1

        self.b = idx + 1
        n = len(pm.pmis)
        while self.b < n:
            pmi = pm.pmis[self.b]
            if pmi.mode == 'EMPTY' and pmi.text.startswith('row'):
                break
            self.b += 1

    def has_columns(self, pm):
        for i in range(self.a + 1, self.b):
            pmi = pm.pmis[i]
            if pmi.mode == 'EMPTY' and pmi.text.startswith("spacer"):
                prop = pme.props.parse(pmi.text)
                if prop.hsep == 'COLUMN':
                    return True

        return False

    def find_columns(self, pm):
        self.num_columns = 0
        self.num_aligners = 0
        for i in range(self.a + 1, self.b):
            pmi = pm.pmis[i]
            if pmi.mode == 'EMPTY':
                prop = pme.props.parse(pmi.text)
                if prop.hsep == 'COLUMN':
                    self.num_columns += 1
                if prop.hsep == 'ALIGNER':
                    self.num_aligners += 1
                    if self.num_aligners == 1:
                        self.l = i
                    else:
                        self.r = i

        if self.num_columns:
            self.num_columns += 1

    def remove_subrows(self, pm):
        pp = pme.props
        i = self.a + 1
        while i < self.b:
            pmi = pm.pmis[i]  # BUG
            if pmi.mode == 'EMPTY' and pmi.text.startswith("spacer"):
                prop = pp.parse(pmi.text)
                if prop.subrow == 'BEGIN' or prop.subrow == 'END':
                    pmi.text = pp.encode(pmi.text, "subrow", 'NONE')
                    if pp.parse(pmi.text).is_empty:
                        pm.pmis.remove(i)
                        self.b -= 1
                        i -= 1
            i += 1


class Col:
    def __init__(self):
        self.a = 0
        self.b = 0

    def __str__(self):
        return "Col [%d, %d]" % (self.a, self.b)

    @staticmethod
    def is_column(item):
        return item.mode == 'EMPTY' and item.text == "column"

    def calc_num_items(self, pm):
        num_items = self.b - self.a + 1
        if self.a >= len(pm.pmis) or Col.is_column(pm.pmis[self.a]):
            num_items -= 1
        if self.b >= len(pm.pmis) or Col.is_column(pm.pmis[self.b]):
            num_items -= 1
        return num_items

    def find_ab(self, pm, idx):
        if idx == 0:
            self.a = 0
            self.b = 0
            return

        self.a = idx - 1
        while self.a > 0:
            pmi = pm.pmis[self.a]
            if pmi.mode == 'EMPTY' and pmi.text == "column":
                break
            self.a -= 1

        self.b = idx


cur_col = Col()


def draw_pme_layout(pm, column, draw_pmi, rows=None, icon_btn_scale_x=-1):
    CLayout.save()

    global num_btns, num_spacers, max_btns, max_spacers, al_l, al_r
    pr = prefs()
    pp = pme.props

    if icon_btn_scale_x == -1:
        icon_btn_scale_x = SCALE_X
        # icon_btn_scale_x = 1 if pr.use_square_buttons else SCALE_X

    num_btns = 0
    num_spacers = 0
    max_btns = 0
    max_spacers = 0
    al_l = -1
    al_r = -1

    DBG_LAYOUT and logh("Draw PME Layout")

    is_subrow = False
    has_columns = False
    row = None
    row_idx = 0
    last_row_idx = 0
    row_is_expanded = False
    subrow_is_expanded = False
    for idx, pmi in enumerate(pm.pmis):
        if pmi.mode == 'EMPTY':
            DBG_LAYOUT and logi(pmi.mode, pmi.text)

            if row and pmi.text.startswith("row"):
                row_prop = pp.parse(pm.pmis[row_idx].text)
                if not row_is_expanded and al_l == -1:
                    row.alignment = row_prop.align
                row_is_expanded = False

                if is_subrow and not subrow_is_expanded and al_l == -1:
                    cur_subrow.alignment = row_prop.align
                subrow_is_expanded = False

                last_row_idx = row_idx
                row_idx = idx

            elif pmi.text.startswith("spacer"):
                prop = pp.parse(pmi.text)
                if prop.subrow == 'BEGIN' or prop.subrow == 'END' or \
                        prop.hsep == 'COLUMN':
                    if is_subrow and not subrow_is_expanded and al_l == -1:
                        row_prop = pp.parse(pm.pmis[row_idx].text)
                        cur_subrow.alignment = row_prop.align
                    subrow_is_expanded = False

            has_columns_mem = has_columns
            new_row, has_columns, is_subrow = _parse_empty_pdi(
                pr, pm, idx, row_idx, column, row, has_columns, is_subrow)
            if not new_row:
                new_row = row

            if rows is not None and pmi.text.startswith("row") and row:
                row_prop = pp.parse(pm.pmis[last_row_idx].text)
                rows.append((
                    last_row_idx, row_prop.value("size"),
                    max_btns, max_spacers, has_columns_mem,
                    row_prop.value("vspacer")))
                max_btns = 0
                max_spacers = 0

            row = new_row
            continue

        text, icon, *_ = pmi.parse()
        row_prop = pp.parse(pm.pmis[row_idx].text)

        DBG_LAYOUT and logi(idx, pmi.mode, text)

        if not is_subrow and has_columns:
            lh.save()
            subrow = lh.row()
            subrow.scale_x = 1
            subrow.scale_y = 1  # row_prop.value("size")

            if pmi.mode == 'PROP':
                if not pmi.is_expandable_prop() and not text and al_l == -1:
                    subrow.alignment = row_prop.align
            elif not text and al_l == -1:
                subrow.alignment = row_prop.align

        lh.save()
        item_col = lh.column()
        if has_aligners:
            item_col.alignment = 'LEFT'

        scale_x = 1
        scale_y = row_prop.value("size")
        if not text:
            if pmi.mode == 'PROP':
                bl_prop = bp.get(pmi.text)
                if not bl_prop or bl_prop.type == 'BOOLEAN':
                    scale_x = max(icon_btn_scale_x, scale_y)
            else:
                scale_x = max(icon_btn_scale_x, scale_y)

        item_col.scale_x = scale_x
        item_col.scale_y = scale_y

        try:
            draw_pmi(pr, pm, pmi, idx)
        except:
            print_exc(pmi.text)

        lh.restore()

        if not is_subrow and has_columns:
            lh.restore()

        if not is_subrow:
            num_btns += 1

        if not row_is_expanded:
            if pmi.name and (icon == 'NONE' or "#" not in pmi.icon):
                row_is_expanded = True
            elif pmi.is_expandable_prop():
                row_is_expanded = True
            # elif pmi.mode == 'CUSTOM' and is_expandable(pmi.text):
            #     row_is_expanded = True

        if is_subrow:
            if not subrow_is_expanded:
                if pmi.name and (icon == 'NONE' or "#" not in pmi.icon):
                    subrow_is_expanded = True
                elif pmi.is_expandable_prop():
                    subrow_is_expanded = True
                # elif pmi.mode == 'CUSTOM' and is_expandable(pmi.text):
                #     subrow_is_expanded = True

    if row:
        row_prop = pp.parse(pm.pmis[row_idx].text)
        if not row_is_expanded and al_l == -1:
            row.alignment = row_prop.align
        if is_subrow and not subrow_is_expanded and al_l == -1:
            cur_subrow.alignment = row_prop.align

        size = row_prop.value("size")
        if max_btns * size + max_spacers * SPACER_SCALE_Y < \
                num_btns * size + num_spacers * SPACER_SCALE_Y:
            max_btns = num_btns if has_columns else 1
            max_spacers = num_spacers if has_columns else 0
        if rows is not None:
            rows.append((
                row_idx, row_prop.value("size"), max_btns, max_spacers,
                has_columns, row_prop.value("vspacer")))

    pme.context.is_first_draw = False

    CLayout.restore()
    return rows


cur_column = None
cur_subrow = None
prev_row_has_columns = False
num_btns = 0
num_spacers = 0
max_btns = 0
max_spacers = 0
al_split = None
al_l = -1
al_r = -1
has_aligners = False


def _parse_empty_pdi(
        prefs, pm, idx, row_idx, layout, row, has_columns, is_subrow):
    global cur_column, cur_subrow, \
        num_btns, num_spacers, max_btns, max_spacers, al_split, has_aligners, \
        al_l, al_r
    pp = pme.props
    pmi = pm.pmis[idx]
    r = pp.parse(pmi.text)

    if pmi.text.startswith("row"):
        if row and r.vspacer != 'NONE':
            lh.lt(layout)
            for i in range(0, r.value("vspacer")):
                lh.sep()

        row_prop = pp.parse(pm.pmis[row_idx].text)
        size = row_prop.value("size")
        if max_btns * size + max_spacers * SPACER_SCALE_Y < \
                num_btns * size + num_spacers * SPACER_SCALE_Y:
            max_btns = num_btns if has_columns else 1
            max_spacers = num_spacers if has_columns else 0
        num_btns = 0
        num_spacers = 0

        has_columns = False
        has_aligners = False
        al_l, al_r, al_c = -1, -1, False
        row_a, row_b = idx, -1
        num_pmis = len(pm.pmis)
        while idx < num_pmis - 1:
            idx += 1
            next_pmi = pm.pmis[idx]
            if next_pmi.mode == 'EMPTY':
                if next_pmi.text.startswith("row"):
                    row_b = idx
                    break
                prop = pp.parse(next_pmi.text)
                if prop.hsep == 'COLUMN':
                    has_columns = True
                    break
                elif prop.hsep == 'ALIGNER':
                    has_aligners = True
                    if al_l == -1:
                        al_l = idx
                    else:
                        al_r = idx

        if row_b == -1:
            row_b = num_pmis
        if al_l != -1 and al_r != -1 and \
                al_l == row_a + 1 and al_r == row_b - 1:
            al_c = True

        if has_aligners:
            if al_c:
                al_split = lh.row(layout)
                al_split.alignment = 'CENTER'
            elif al_r == -1:
                al_split = lh.row(layout)
            else:
                al_split = lh.split(layout)
            row = lh.row()
            row.alignment = 'LEFT'
        elif has_columns and row_prop.fixed_col or \
                not has_columns and row_prop.fixed_but:
            row = lh.split(layout, align=not has_columns)
        else:
            row = lh.row(layout, align=not has_columns)

        DBG_LAYOUT and logi("- ROW -")

        row.scale_x = 1
        row.scale_y = 1  # r.value("size")
        # row.alignment = 'EXPAND'
        is_subrow = False
        if has_columns and idx != row_idx + 1:
            row.scale_x = 1
            row.scale_y = 1
            column = lh.column()
            cur_column = column

        return row, has_columns, is_subrow

    elif pmi.text.startswith("spacer"):
        if r.subrow == 'END' or is_subrow and r.subrow == 'BEGIN':
            lh.lt(cur_column)
            is_subrow = False

            DBG_LAYOUT and logi("^ SUBROW ^")

        if r.hsep == 'SPACER':
            if not is_subrow:
                num_spacers += 1
            lh.sep()

        elif r.hsep == 'ALIGNER':
            row = lh.row(al_split)
            row.alignment = 'CENTER' if al_r != -1 and idx == al_l else 'RIGHT'

        elif r.hsep == 'COLUMN':
            lh.lt(row)
            row.scale_x = 1
            row.scale_y = 1
            column = lh.column(row)
            cur_column = column

            DBG_LAYOUT and logi("- COL -")

            if max_btns < num_btns:
                max_btns = num_btns if has_columns else 1
                max_spacers = num_spacers if has_columns else 0
            num_btns = 0
            num_spacers = 0
            is_subrow = False

        elif r.hsep == 'LARGE':
            lh.sep()
            lh.blank()
            lh.sep()

        elif r.hsep == 'LARGER':
            lh.sep()
            lh.spacer()
            lh.sep()

        if r.subrow == 'BEGIN':
            row_prop = pp.parse(pm.pmis[row_idx].text)
            if row_prop.fixed_but:
                subrow = lh.split(cur_column, align=True)
            else:
                subrow = lh.row(cur_column)

            DBG_LAYOUT and logi("v SUBROW v")

            row_prop = pp.parse(pm.pmis[row_idx].text)
            subrow.scale_x = 1
            subrow.scale_y = 1  # row_prop.value("size")
            num_btns += 1
            is_subrow = True
            cur_subrow = subrow

    return None, has_columns, is_subrow


lh = LayoutHelper(ph)


def operator(
        layout, idname, text=None, icon='NONE',
        emboss=True, icon_value=0, depress=None,
        **kwargs):
    d = dict(
        icon=ic(icon), icon_value=icon_value, emboss=emboss)

    if text is not None:
        d["text"] = text

    if depress is not None and is_28():
        d["depress"] = depress

    properties = layout.operator(idname, **d)

    for k, v in kwargs.items():
        setattr(properties, k, v)

    return properties


def split(layout, factor=None, align=True):
    if bpy.app.version < (2, 80, 0):
        return layout.split(align=align) if factor is None else \
            layout.split(factor, align)

    return layout.split(align=align) if factor is None else \
        layout.split(factor=factor, align=align)


def register():
    pme.context.add_global("lh", lh)
    pme.context.add_global("operator", operator)

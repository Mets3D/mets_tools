from .ed_base import EditorBase
from .constants import ARROW_ICONS
from . import pme
from .addon import ic, prefs
from .layout_helper import lh


pme.props.IntProperty("pm", "pm_radius", -1)
pme.props.IntProperty("pm", "pm_confirm", -1)
pme.props.IntProperty("pm", "pm_threshold", -1)
pme.props.BoolProperty("pm", "pm_flick", True)


class Editor(EditorBase):

    def __init__(self):
        self.id = 'PMENU'
        EditorBase.__init__(self)

        self.docs = "#Pie_Menu_Editor"
        self.default_pmi_data = "pm?"
        self.fixed_num_items = True
        self.use_swap = True
        self.supported_open_modes = {'PRESS', 'HOLD', 'DOUBLE_CLICK'}

    def on_pm_add(self, pm):
        for i in range(0, 10):
            pm.pmis.add()

    def on_pmi_rename(self, pm, pmi, old_name, name):
        pmi.name = name
        if not old_name and pmi.mode == 'EMPTY':
            pmi.mode = 'COMMAND'

    def draw_extra_settings(self, layout, pm):
        EditorBase.draw_extra_settings(self, layout, pm)
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(pm, "pm_radius", text="Radius")
        if pm.pm_radius != -1:
            row.operator("pme.exec", text="", icon=ic('X')).cmd = \
                "prefs().selected_pm.pm_radius = -1"
        if pm.pm_flick:
            row = col.row(align=True)
            row.prop(pm, "pm_threshold", text="Threshold")
            if pm.pm_threshold != -1:
                row.operator("pme.exec", text="", icon=ic('X')).cmd = \
                    "prefs().selected_pm.pm_threshold = -1"

            row = col.row(align=True)
            row.prop(pm, "pm_confirm", text="Confirm Threshold")
            if pm.pm_confirm != -1:
                row.operator("pme.exec", text="", icon=ic('X')).cmd = \
                    "prefs().selected_pm.pm_confirm = -1"
        layout.prop(pm, "pm_flick")

        # if pm.pm_radius != -1:
        #     layout.label(
        #         text="Custom radius disables pie menu animation", icon='INFO')

    def draw_items(self, layout, pm):
        pr = prefs()
        column = layout.column(align=True)

        for idx, pmi in enumerate(pm.pmis):
            lh.row(column, active=pmi.enabled)

            self.draw_item(pm, pmi, idx)
            self.draw_pmi_menu_btn(pr, idx)

            if idx == 7:
                column.separator()

    def get_pmi_icon(self, pm, pmi, idx):
        return ARROW_ICONS[idx]


def register():
    Editor()

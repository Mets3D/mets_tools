import bpy
from .ed_base import EditorBase
from .addon import prefs, temp_prefs, SAFE_MODE
from .layout_helper import lh
from . import panel_utils as PAU
from .ui import tag_redraw
from .operators import *


class PME_OT_hpanel_menu(bpy.types.Operator):
    bl_idname = "pme.panel_hide_menu"
    bl_label = "Hide Panels"
    bl_description = "Hide panels"

    def _draw(self, menu, context):
        pr = prefs()
        lh.lt(menu.layout, 'INVOKE_DEFAULT')
        lh.operator(
            PME_OT_panel_hide.bl_idname, None, 'ZOOMIN',
            group=pr.selected_pm.name)
        lh.operator(PME_OT_panel_hide_by.bl_idname, None, 'ZOOMIN')
        lh.sep()

        lh.prop(pr, "interactive_panels")

    def execute(self, context):
        context.window_manager.popup_menu(
            self._draw, title=self.bl_description)
        return {'FINISHED'}


class PME_OT_hpanel_remove(bpy.types.Operator):
    bl_idname = "pme.hpanel_remove"
    bl_label = "Unhide Panel"
    bl_description = "Unhide panel"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()

    def execute(self, context):
        pm = prefs().selected_pm

        if self.idx == -1:
            PAU.unhide_panels([pmi.text for pmi in pm.pmis])

            pm.pmis.clear()

        else:
            pmi = pm.pmis[self.idx]
            PAU.unhide_panel(pmi.text)
            pm.pmis.remove(self.idx)

        tag_redraw()
        return {'FINISHED'}


class Editor(EditorBase):

    def __init__(self):
        self.id = 'HPANEL'
        EditorBase.__init__(self)

        self.docs = "#Hiding_Unused_Panels"
        self.use_preview = False
        self.sub_item = False
        self.has_hotkey = False
        self.has_extra_settings = False
        self.default_pmi_data = "hpg?"
        self.supported_slot_modes = {'EMPTY'}

    def init_pm(self, pm):
        if pm.enabled and not SAFE_MODE:
            for pmi in pm.pmis:
                PAU.hide_panel(pmi.text)

    def on_pm_remove(self, pm):
        for pmi in pm.pmis:
            PAU.unhide_panel(pmi.text)
        super().on_pm_remove(pm)

    def on_pm_duplicate(self, from_pm, pm):
        pass

    def on_pm_enabled(self, pm, value):
        super().on_pm_enabled(pm, value)

        if pm.enabled:
            for pmi in pm.pmis:
                PAU.hide_panel(pmi.text)

        else:
            PAU.unhide_panels([pmi.text for pmi in pm.pmis])

    def draw_keymap(self, layout, data):
        pass

    def draw_hotkey(self, layout, data):
        pass

    def draw_items(self, layout, pm):
        tpr = temp_prefs()

        row = layout.row()
        row.template_list(
            "WM_UL_panel_list", "",
            pm, "pmis", tpr, "hidden_panels_idx", rows=10)

        lh.column(row)
        lh.operator(PME_OT_hpanel_menu.bl_idname, "", 'ZOOMIN')

        if len(pm.pmis):
            lh.operator(
                PME_OT_hpanel_remove.bl_idname, "", 'ZOOMOUT',
                idx=tpr.hidden_panels_idx)
            lh.operator(
                PME_OT_hpanel_remove.bl_idname, "", 'X', idx=-1)

        lh.sep()

        lh.layout.prop(
            prefs(), "panel_info_visibility", text="", expand=True)


def register():
    Editor()

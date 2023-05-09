import bpy
from . import pme
from .ed_base import EditorBase
from .addon import prefs
from .ui import tag_redraw
from .operator_utils import find_statement


class PME_OT_sticky_key_edit(bpy.types.Operator):
    bl_idname = "pme.sticky_key_edit"
    bl_label = "Save and Restore Previous Value"
    bl_description = "Save and restore the previous value"
    bl_options = {'INTERNAL'}

    pmi_prop = None
    pmi_value = None

    @staticmethod
    def parse_prop_value(text):
        prop, value = find_statement(text)
        if not prop:
            PME_OT_sticky_key_edit.pmi_prop = None
            PME_OT_sticky_key_edit.pmi_value = None
        else:
            PME_OT_sticky_key_edit.pmi_prop = prop
            PME_OT_sticky_key_edit.pmi_value = value

    def execute(self, context):
        cl = self.__class__
        pr = prefs()
        pm = pr.selected_pm
        pm.pmis[1].mode = 'COMMAND'
        pm.pmis[1].text = cl.pmi_prop + " = value"
        pm.pmis[0].mode = 'COMMAND'
        pm.pmis[0].text = "value = %s; %s = %s" % (
            cl.pmi_prop, cl.pmi_prop, cl.pmi_value)

        pr.pmi_data.info()
        pr.leave_mode()
        tag_redraw()

        return {'FINISHED'}


pme.props.BoolProperty("sk", "sk_block_ui", False)


class Editor(EditorBase):

    def __init__(self):
        self.id = 'STICKY'
        EditorBase.__init__(self)

        self.docs = "#Sticky_Key_Editor"
        self.use_slot_icon = False
        self.use_preview = False
        self.sub_item = False
        self.default_pmi_data = "sk?"
        self.fixed_num_items = True
        self.movable_items = False
        self.supported_slot_modes = {'COMMAND', 'HOTKEY'}
        self.toggleable_slots = False

    def init_pm(self, pm):
        pass

    def on_pm_add(self, pm):
        pmi = pm.pmis.add()
        pmi.mode = 'COMMAND'
        pmi.name = "On Press"
        pmi = pm.pmis.add()
        pmi.mode = 'COMMAND'
        pmi.name = "On Release"

    def on_pmi_check(self, pm, pmi_data):
        EditorBase.on_pmi_check(self, pm, pmi_data)

        if pmi_data.mode == 'COMMAND':
            PME_OT_sticky_key_edit.parse_prop_value(pmi_data.cmd)

    def draw_extra_settings(self, layout, pm):
        EditorBase.draw_extra_settings(self, layout, pm)
        layout.prop(pm, "sk_block_ui")

    def get_pmi_icon(self, pm, pmi, idx):
        return 'TRIA_DOWN_BAR' if idx == 0 else 'TRIA_UP'


def register():
    Editor()

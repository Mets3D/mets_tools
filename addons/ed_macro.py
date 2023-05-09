import bpy
from . import pme
from .addon import prefs
from .constants import MAX_STR_LEN
from .bl_utils import uname
from .ed_base import EditorBase
from .operators import PME_OT_sticky_key_base, PME_OT_modal_base
from . import macro_utils as MAU


class PME_OT_macro_exec_base:
    bl_idname = "pme.macro_exec_base"
    bl_label = "Macro Command"
    bl_options = {'INTERNAL'}

    macro_globals = None

    cmd: bpy.props.StringProperty(
        maxlen=MAX_STR_LEN, options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        if not pme.context.exe(
                self.cmd, PME_OT_macro_exec_base.macro_globals):
            return {'CANCELLED'}

        ret = {'CANCELLED'} \
            if PME_OT_macro_exec_base.macro_globals.get("stop", False) \
            else {'FINISHED'}
        PME_OT_macro_exec_base.macro_globals.pop("stop", None)
        return ret


class PME_OT_macro_exec1(bpy.types.Operator):
    bl_idname = "pme.macro_exec1"
    bl_label = "Macro Command"
    bl_options = {'INTERNAL'}

    cmd: bpy.props.StringProperty(
        maxlen=MAX_STR_LEN, options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        PME_OT_macro_exec_base.macro_globals = pme.context.gen_globals()

        return PME_OT_macro_exec_base.execute(self, context)


class Editor(EditorBase):

    def __init__(self):
        self.id = 'MACRO'
        EditorBase.__init__(self)

        self.docs = "#Macro_Operator_Editor"
        self.use_slot_icon = False
        self.use_preview = False
        self.default_pmi_data = "m?"
        self.supported_slot_modes = {'COMMAND', 'MENU'}
        self.supported_sub_menus = {'STICKY', 'MACRO', 'MODAL'}

    def init_pm(self, pm):
        if pm.enabled:
            MAU.add_macro(pm)

    def on_pm_add(self, pm):
        pmi = pm.pmis.add()
        pmi.mode = 'COMMAND'
        pmi.name = "Command 1"
        MAU.add_macro(pm)

    def on_pm_remove(self, pm):
        MAU.remove_macro(pm)
        super().on_pm_remove(pm)

    def on_pm_duplicate(self, from_pm, pm):
        EditorBase.on_pm_duplicate(self, from_pm, pm)
        MAU.add_macro(pm)

    def on_pm_enabled(self, pm, value):
        super().on_pm_enabled(pm, value)

        if pm.enabled:
            MAU.add_macro(pm)
        else:
            MAU.remove_macro(pm)

    def on_pm_rename(self, pm, name):
        MAU.remove_macro(pm)
        super().on_pm_rename(pm, name)
        MAU.add_macro(pm)

    def on_pmi_add(self, pm, pmi):
        pmi.mode = 'COMMAND'
        pmi.name = uname(pm.pmis, "Command", " ", 1, False)
        MAU.update_macro(pm)

    def on_pmi_move(self, pm):
        MAU.update_macro(pm)

    def on_pmi_remove(self, pm):
        MAU.update_macro(pm)

    def on_pmi_paste(self, pm, pmi):
        MAU.update_macro(pm)

    def on_pmi_toggle(self, pm, pmi):
        MAU.update_macro(pm)

    def on_pmi_edit(self, pm, pmi):
        MAU.update_macro(pm)

    def get_pmi_icon(self, pm, pmi, idx):
        pr = prefs()
        icon = self.icon
        if pmi.icon:
            icon = pmi.icon
        elif pmi.text in pr.pie_menus:
            icon = pr.pie_menus[pmi.text].ed.icon

        return icon


def register():
    Editor()

    MAU.init_macros(
        PME_OT_macro_exec1, PME_OT_macro_exec_base,
        PME_OT_sticky_key_base, PME_OT_modal_base)

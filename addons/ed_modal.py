import bpy
from . import pme
from .constants import (
    MODAL_CMD_MODES, W_PMI_HOTKEY, I_MODAL_PROP_MOVE,
    W_PMI_EXPR
)
from .bl_utils import uname
from .ed_base import EditorBase
from .addon import temp_prefs
from .modal_utils import encode_modal_data, decode_modal_data


class PME_OT_prop_data_reset(bpy.types.Operator):
    bl_idname = "pme.prop_data_reset"
    bl_label = "Reset"
    bl_description = "Reset values"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        tpr = temp_prefs()
        tpr.modal_item_prop_min = tpr.prop_data.min
        tpr.modal_item_prop_max = tpr.prop_data.max
        tpr.modal_item_prop_step = tpr.prop_data.step
        tpr.modal_item_prop_step_is_set = False
        return {'FINISHED'}


pme.props.BoolProperty("mo", "confirm", False)
pme.props.BoolProperty("mo", "block_ui", True)
pme.props.BoolProperty("mo", "lock", True)


class Editor(EditorBase):

    def __init__(self):
        self.id = 'MODAL'
        EditorBase.__init__(self)

        self.docs = "#Modal_Operator_Editor"
        self.use_slot_icon = False
        self.use_preview = False
        self.default_pmi_data = "mo?"
        self.supported_slot_modes = {
            'COMMAND', 'PROP', 'INVOKE', 'FINISH', 'CANCEL', 'UPDATE'}
        self.supported_paste_modes = {
            'MODAL'
        }

    def init_pm(self, pm):
        pass

    def on_pm_add(self, pm):
        pmi = pm.pmis.add()
        pmi.mode = 'INVOKE'
        pmi.name = bpy.types.UILayout.enum_item_name(pmi, "mode", 'INVOKE')

    def on_pmi_check(self, pm, pmi_data):
        EditorBase.on_pmi_check(self, pm, pmi_data)

        tpr = temp_prefs()
        if pmi_data.mode in {'COMMAND', 'PROP'}:
            if tpr.modal_item_custom:
                try:
                    compile(tpr.modal_item_custom, "<string>", "eval")
                except:
                    pmi_data.info(W_PMI_EXPR)

        if pmi_data.mode == 'COMMAND' or \
                pmi_data.mode == 'PROP' and tpr.modal_item_prop_mode == 'KEY':
            if tpr.modal_item_hk.key == 'NONE':
                pmi_data.info(W_PMI_HOTKEY)

        elif pmi_data.mode in MODAL_CMD_MODES:
            pmi_data.sname = bpy.types.UILayout.enum_item_name(
                pmi_data, "mode", pmi_data.mode)

        # elif pmi_data.mode == 'PROP':
        #     pmi_data.sname = bpy.types.UILayout.enum_item_name(
        #         tpr, "modal_item_prop_mode", tpr.modal_item_prop_mode)

        if pmi_data.mode == 'PROP' and tpr.modal_item_prop_mode == 'MOVE':
            pmi_data.info(I_MODAL_PROP_MOVE, False)

    def on_pmi_add(self, pm, pmi):
        pmi.mode = 'INVOKE'
        pmi.name = uname(pm.pmis, "Command", " ", 1, False)

    def on_pmi_pre_edit(self, pm, pmi, data):
        EditorBase.on_pmi_pre_edit(self, pm, pmi, data)

        tpr = temp_prefs()
        tpr.prop_data.clear()
        if pmi.mode == 'PROP':
            tpr.prop_data.init(pmi.text, pme.context.globals)

        tpr.modal_item_prop_min = tpr.prop_data.min
        tpr.modal_item_prop_max = tpr.prop_data.max
        tpr.modal_item_prop_step = tpr.prop_data.step
        tpr.modal_item_prop_step_is_set = False
        tpr.modal_item_custom = ""

        decode_modal_data(pmi, None, tpr)

    def on_pmi_edit(self, pm, pmi):
        if pmi.mode == 'COMMAND' and pmi.icon in {'', 'NONE'}:
            pmi.mode = 'INVOKE'

        if pmi.mode == 'PROP':
            encode_modal_data(pmi)
        elif pmi.mode == 'COMMAND':
            encode_modal_data(pmi)
        else:
            pmi.icon = ""

    def draw_extra_settings(self, layout, pm):
        EditorBase.draw_extra_settings(self, layout, pm)
        col = layout.column(align=True)
        col.prop(pm, "mo_confirm_on_release")
        col.prop(pm, "mo_block_ui")
        col.prop(pm, "mo_lock")

    def get_pmi_icon(self, pm, pmi, idx):
        icon = 'BLENDER'
        if pmi.mode == 'COMMAND':
            icon = 'FILE_SCRIPT'
        elif pmi.mode == 'PROP':
            if 'WHEELUPMOUSE' in pmi.icon or \
                    'WHEELDOWNMOUSE' in pmi.icon:
                icon = 'DECORATE_OVERRIDE'
            elif pmi.icon.startswith('MOUSEMOVE'):
                icon = 'CENTER_ONLY'
            else:
                icon = 'ARROW_LEFTRIGHT'
        elif pmi.mode == 'INVOKE':
            icon = 'PLAY'
        elif pmi.mode == 'CANCEL':
            icon = 'CANCEL'
        elif pmi.mode == 'FINISH':
            icon = 'CHECKBOX_HLT'
        elif pmi.mode == 'UPDATE':
            icon = 'FILE_REFRESH'

        return icon


def register():
    Editor()

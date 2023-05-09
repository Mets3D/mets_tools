# Open context sensitive menu

# Usage 1:
# Import ./examples/context_sensitive_menu.json file

# Usage 2 (Command tab):
# execute_script("scripts/command_context_sensitive_menu.py")

# Usage 3 (Command tab):
# from .scripts.command_context_sensitive_menu import open_csm; open_csm()

import bpy
from pie_menu_editor import pme


def open_csm(prefix="", suffix=""):
    p, s = prefix, suffix
    context = bpy.context
    obj = context.selected_objects and context.active_object
    open_menu = pme.context.open_menu

    if not obj:
        open_menu(p + "None Object" + s)

    elif obj.type == "MESH":
        if obj.mode == 'EDIT':
            msm = context.tool_settings.mesh_select_mode
            msm[0] and open_menu(p + "Vertex" + s) or \
                msm[1] and open_menu(p + "Edge" + s) or \
                msm[2] and open_menu(p + "Face" + s) or \
                open_menu(p + "Edit" + s) or \
                open_menu(p + "Mesh" + s) or \
                open_menu(p + "Any Object" + s)

        else:
            open_menu(p + obj.mode.replace("_", " ").title() + s) or \
                open_menu(p + "Mesh" + s) or \
                open_menu(p + "Any Object" + s)

    else:
        open_menu(p + obj.mode.replace("_", " ").title() + s) or \
            open_menu(p + obj.type.replace("_", " ").title() + s) or \
            open_menu(p + "Any Object" + s)


kwargs = locals().get("kwargs", {})
prefix = kwargs.get("prefix", "")
suffix = kwargs.get("suffix", "")
open_csm(prefix, suffix)

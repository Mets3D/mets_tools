import bpy
from bpy.types import AddonPreferences
from bpy.props import BoolProperty
from . import __package__ as base_package

class MetsToolsPrefs(AddonPreferences):
    bl_idname = __package__

    auto_fix_whitespace: BoolProperty(
        name="Force Spaces",
        description="Every few seconds, replace all tabs with spaces in any text editors",
        default=True,
    )

    def draw(self, context):
        self.layout.prop(self, 'auto_fix_whitespace')

def force_spaces_timer() -> int:
    prefs = get_addon_prefs()
    if not prefs.auto_fix_whitespace:
        return 3
    for a in bpy.context.screen.areas:
        if a.type != 'TEXT_EDITOR':
            continue
        text = a.spaces.active.text
        if not text or not text.is_editable or text.indentation == 'SPACES':
            continue
        text.indentation = 'SPACES'
        text.region_from_string(text.as_string().replace("\t", "    "), range=((0, 0), (-1, -1)))

    return 3

def get_addon_prefs(context=None):
    if not context:
        context = bpy.context
    if base_package.startswith('bl_ext'):
        # 4.2
        return context.preferences.addons[base_package].preferences
    else:
        return context.preferences.addons[base_package.split(".")[0]].preferences

registry = [MetsToolsPrefs]

def register():
    bpy.app.timers.register(force_spaces_timer)

def unregister():
    bpy.app.timers.unregister(force_spaces_timer)
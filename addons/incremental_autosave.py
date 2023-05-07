bl_info = {
    "name": "Incremental Autosave",
    "author": "Demeter Dzadik",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "blender",
    "description": "Autosaves in a way where subsequent autosaves don't overwrite previous ones",
    "category": "System",
}

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.app.handlers import persistent
from datetime import datetime
import os, platform, tempfile

# Timestamp format for prefixing autosave file names.
TIME_FMT_STR = '%Y_%M_%d_%H-%M-%S'

# Timestamp of when Blender is launched. Used to avoid creating an autosave when opening Blender.
LAUNCH_TIME = datetime.now()

def get_addon_prefs():
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__name__].preferences

class IncrementalAutoSavePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    save_before_close : BoolProperty(name='Save Before File Open',
                    description='Save the current file before opening another file',
                    default=True)
    save_interval : IntProperty(name='Save Interval (Minutes)',
                    description="Number of minutes between each save. (As long as the add-on is enabled, it always auto-saves, since that's all the add-on does)",
                    default=5, min=1, max=120, soft_max=30)

    use_native_autosave_path: BoolProperty(
        name = "Use Native Autosave Path",
        description = "If True, use the autosave path that's part of the regular Blender preferences. If you use the add-on's autosave path, it is a per-OS path, so if you have multiple workstations with multiple operating systems, the add-on can have a separate (and functional) filepath for each of them",
        default = True
    )
    autosave_path_linux : StringProperty(name='Autosave Path (Linux)',
                    description='Path to auto save files into',
                    subtype='FILE_PATH',
                    default='')
    autosave_path_windows : StringProperty(name='Autosave Path (Windows)',
                    description='Path to auto save files into',
                    subtype='FILE_PATH',
                    default='')
    autosave_path_mac : StringProperty(name='Autosave Path (Mac)',
                    description='Path to auto save files into',
                    subtype='FILE_PATH',
                    default='')

    @property
    def autosave_path_naive(self):
        """Return the autosave path that the user wishes existed."""
        if self.use_native_autosave_path:
            return bpy.context.preferences.filepaths.temporary_directory
        system = platform.system()
        if system == "Windows":
            return self.autosave_path_windows
        elif system == "Linux":
            return self.autosave_path_linux
        elif system == "Darwin":
            return self.autosave_path_mac

    @property
    def autosave_path(self):
        """Return an autosave path that will always actually exist, no matter how desperate."""
        path = self.autosave_path_naive
        if path and os.path.exists(path):
            return path

        if bpy.data.filepath:
            return os.path.dirname(bpy.data.filepath)

        sys_temp = tempfile.gettempdir()
        return sys_temp

    max_save_files : bpy.props.IntProperty(name='Max Save Files',
                    description='Maximum number of copies to save, 0 means unlimited',
                    default=10, min=0, max=100)
    compress_files : bpy.props.BoolProperty(name='Compress Files',
                    description='Save backups with compression enabled',
                    default=True)

    def draw(self, context):
        layout = self.layout.column()
        layout.use_property_decorate = False
        layout.use_property_split = True

        layout.prop(context.preferences.filepaths, 'use_auto_save_temporary_files', text="Enable Native Autosave (Redundant)")

        layout.prop(self, 'use_native_autosave_path')
        if bpy.data.filepath == '':
            par = os.getcwd()
        else:
            par = None
        abs_path = bpy.path.abspath(self.autosave_path_naive, start=par)

        path_row = layout.row()
        if not os.path.exists(abs_path):
            path_row.alert = True
        if self.use_native_autosave_path:
            path_row.prop(context.preferences.filepaths, 'temporary_directory')
        else:
            system = platform.system()
            if system == "Windows":
                path_row.prop(self, 'autosave_path_windows')
            elif system == "Linux":
                path_row.prop(self, 'autosave_path_linux')
            elif system == "Darwin":
                path_row.prop(self, 'autosave_path_mac')

        if path_row.alert:
            split = layout.split(factor=0.4)
            split.row()
            split.label(text='Path not found: '+abs_path, icon='ERROR')
            fallback_split = layout.split(factor=0.4)
            fallback_split.row()
            fallback_split.label(text="Fallback path: " + self.autosave_path)

        layout.separator()

        layout.prop(self,'save_interval')
        layout.prop(self,'max_save_files')
        layout.prop(self,'compress_files')

def save_file():
    addon_prefs = get_addon_prefs()

    basename = bpy.data.filepath
    if basename == '':
        basename = 'Unnamed.blend'
    else:
        basename = bpy.path.basename(basename)

    try:
        save_dir = bpy.path.abspath(addon_prefs.autosave_path)
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)
    except:
        print("Incremental Autosave: Error creating auto save directory.")
        return

    # Delete old files, to limit the number of saves.
    if addon_prefs.max_save_files > 0:
        try:
            # As we prefix saved blends with a timestamp,
            # `sorted()` puts the oldest prefix at the start of the list.
            # This should be quicker than getting system timestamps for each file.
            otherfiles = sorted([name for name in os.listdir(save_dir) if name.endswith(basename)])
            if len(otherfiles) >= addon_prefs.max_save_files:
                while len(otherfiles) >= addon_prefs.max_save_files:
                    old_file = os.path.join(save_dir,otherfiles[0])
                    os.remove(old_file)
                    otherfiles.pop(0)
        except:
            print("Incremental Autosave: Unable to remove old files.")

    # Save the copy.
    time = datetime.now()
    filename = time.strftime(TIME_FMT_STR) + '_' + basename
    backup_file = os.path.join(save_dir,filename)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=backup_file, copy=True,
                                        compress=addon_prefs.compress_files)
        print("Incremental Autosave: Saved file: ", backup_file)
    except:
        print('Incremental Autosave: Error auto saving file.')

@persistent
def save_pre_close(_dummy=None):
    # is_dirty means there are changes that haven't been saved to disk
    if bpy.data.is_dirty and get_addon_prefs().save_before_close:
        save_file()

def create_autosave():
    now = datetime.now()
    delta = now-LAUNCH_TIME
    if delta.seconds < 5:
        return get_addon_prefs().save_interval * 60

    if bpy.data.is_dirty:
        save_file()
    return get_addon_prefs().save_interval * 60

@persistent
def register_autosave_timer(_dummy=None):
    bpy.app.timers.register(create_autosave)

def register():
    bpy.utils.register_class(IncrementalAutoSavePreferences)
    bpy.app.timers.register(create_autosave)
    bpy.app.handlers.load_pre.append(save_pre_close)
    bpy.app.handlers.load_post.append(register_autosave_timer)

def unregister():
    bpy.app.handlers.load_pre.remove(save_pre_close)
    bpy.app.handlers.load_post.remove(register_autosave_timer)
    bpy.app.timers.unregister(create_autosave)
    bpy.utils.unregister_class(IncrementalAutoSavePreferences)

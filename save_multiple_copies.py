import bpy, os

copies = 8  # Excluding self.

for i in range(0, copies):
    filepath = bpy.data.filepath.replace(".blend", ".%d.blend"%i)
    bpy.ops.wm.save_as_mainfile(filepath=filepath, copy=True)
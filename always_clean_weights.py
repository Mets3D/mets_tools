import bpy
from bpy.app.handlers import persistent

class ToggleCleaner(bpy.types.Operator):
	""" Toggle automatic calling of weight clean operator """
	bl_idname = "object.toggle_weight_cleaner"
	bl_label = "Toggle Weight Cleaner"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		WeightCleaner.cleaner_active = not WeightCleaner.cleaner_active
		return {'FINISHED'}

class WeightCleaner:
	cleaner_active = True

	do_clean = True
	cleaning_in_progress = False # Avoid threading issues.
	
	@classmethod
	def clean_weights(cls, scene, depsgraph):
		if not bpy.context or not bpy.context.object or bpy.context.mode!='PAINT_WEIGHT': return
		if not cls.cleaner_active: return
		if cls.do_clean:
			cls.do_clean = False
			cls.cleaning_in_progress = True
			# Note: It is very important that this call NEVER fails.
			bpy.ops.object.vertex_group_clean(limit=0.001) # This will trigger a depsgraph update, and therefore clean_weights, again.
			cls.cleaning_in_progress = False

	@classmethod
	def reset_flag(cls, scene, depsgraph):
		if not bpy.context or not bpy.context.object or bpy.context.mode!='PAINT_WEIGHT': return
		if cls.cleaning_in_progress: return
		if not cls.cleaner_active: return
		cls.do_clean = True

@persistent
def start_cleaner(scene, depsgraph):
	bpy.app.handlers.depsgraph_update_pre.append(WeightCleaner.clean_weights)
	bpy.app.handlers.depsgraph_update_post.append(WeightCleaner.reset_flag)

def register():
	bpy.app.handlers.load_post.append(start_cleaner)

	from bpy.utils import register_class
	register_class(ToggleCleaner)

def unregister():
	WeightCleaner.cleaner_active = False

	from bpy.utils import unregister_class
	unregister_class(ToggleCleaner)
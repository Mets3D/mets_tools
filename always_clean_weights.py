import bpy
from bpy.app.handlers import persistent

class ToggleCleaner(bpy.types.Operator):
	"""Toggle automatic calling of Clean Vertex Groups operator after every depsgraph update while in Weight Paint mode.
	(Ie. after every brush stroke)
	"""
	bl_idname = "object.toggle_weight_cleaner"
	bl_label = "Toggle Weight Cleaner"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		WeightCleaner.cleaner_active = not WeightCleaner.cleaner_active
		return {'FINISHED'}

class WeightCleaner:
	"""Run bpy.ops.object.vertex_group_clean on every depsgraph update while in weight paint mode (ie. every brush stroke)."""
	# Most of the code is simply responsible for avoiding infinite looping depsgraph updates.
	cleaner_active = False	# Flag set by the user via the toggle operator.

	do_clean = True	# Flag set in post_depsgraph_update, to indicate to pre_depsgraph_update that the depsgraph update has indeed completed.
	cleaning_in_progress = False # Flag set by pre_depsgraph_update to indicate to post_depsgraph_update that the cleanup operator is still running (in a different thread).
	
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
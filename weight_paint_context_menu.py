import bpy
from bpy.props import *
from bpy.app.handlers import persistent

class WPContextMenu(bpy.types.Operator):
	""" Custom Weight Paint context menu """
	bl_idname = "object.custom_weight_paint_context_menu"
	bl_label = "Custom Weight Paint Context Menu"
	bl_options = {'REGISTER'}

	def update_weight_cleaner(self, context):
		context.scene['weight_cleaner'] = self.weight_cleaner
		WeightCleaner.cleaner_active = context.scene['weight_cleaner']

	def update_front_faces(self, context):
		for b in bpy.data.brushes:
			if not b.use_paint_weight: continue
			b.use_frontface = self.front_faces
	
	def update_falloff_shape(self, context):
		for b in bpy.data.brushes:
			if not b.use_paint_weight: continue
			b.falloff_shape = self.falloff_shape
			for i, val in enumerate(b.cursor_color_add):
				if val > 0:
					b.cursor_color_add[i] = (0.5 if self.falloff_shape=='SPHERE' else 2.0)

	weight_cleaner: BoolProperty(name="Weight Cleaner", update=update_weight_cleaner)
	front_faces: BoolProperty(name="Front Faces Only", update=update_front_faces)
	falloff_shape: EnumProperty(name="Falloff Shape", update=update_falloff_shape,
		items=[
			('SPHERE', 'Sphere', "The brush influence falls off along a sphere whose center is the mesh under the cursor's pointer"),
			('PROJECTED', 'Projected', "The brush influence falls off in a tube around the cursor. This is useful for painting backfaces, as long as Front Faces Only is off.")
		]
	)

	@classmethod
	def poll(cls, context):
		return context.mode=='PAINT_WEIGHT'

	def draw(self, context):
		layout = self.layout

		layout.label(text="Brush Settings (Global)")
		layout.prop(self, "front_faces", toggle=True)
		layout.prop(self, "falloff_shape", expand=True)
		layout.separator()

		layout.label(text="Weight Paint settings")
		tool_settings = context.tool_settings
		
		row = layout.row()
		row.prop(tool_settings, "use_auto_normalize", text="Auto Normalize", toggle=True)
		row.prop(self, "weight_cleaner", toggle=True)
		row = layout.row()
		row.prop(tool_settings, "use_multipaint", text="Multi-Paint", toggle=True)
		row.prop(context.weight_paint_object.data, "use_mirror_x", toggle=True)
		layout.separator()

		layout.label(text="Overlay")
		row = layout.row()
		row.use_property_split=True
		row.prop(tool_settings, "vertex_group_user", text="Zero Weights", expand=True)
		if hasattr(context.space_data, "overlay"):
			overlay = context.space_data.overlay
			layout.prop(overlay, "show_wpaint_contours", text="Weight Contours", toggle=True)
			layout.prop(overlay, "show_paint_wire", text="Wireframe", toggle=True)

		if context.pose_object:
			layout.label(text="Armature Display")
			layout.prop(context.pose_object.data, "display_type", expand=True)
			layout.prop(context.pose_object, "show_in_front", toggle=True)
	
	def invoke(self, context, event):
		active_brush = context.tool_settings.weight_paint.brush
		self.front_faces = active_brush.use_frontface
		self.falloff_shape = active_brush.falloff_shape
		if 'weight_cleaner' not in context.scene:
			context.scene['weight_cleaner'] = False
		self.weight_cleaner = context.scene['weight_cleaner']
		
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def execute(self, context):
		context.scene.tool_settings.vertex_group_user = 'ACTIVE'
		return {'FINISHED'}

class WeightCleaner:
	"""Run bpy.ops.object.vertex_group_clean on every depsgraph update while in weight paint mode (ie. every brush stroke)."""
	# Most of the code is simply responsible for avoiding infinite looping depsgraph updates.
	cleaner_active = False			# Flag set by the user via the custom WP context menu.

	can_clean = True				# Flag set in post_depsgraph_update, to indicate to pre_depsgraph_update that the depsgraph update has indeed completed.
	cleaning_in_progress = False 	# Flag set by pre_depsgraph_update to indicate to post_depsgraph_update that the cleanup operator is still running (in a different thread).
	
	@classmethod
	def clean_weights(cls, scene, depsgraph):
		if not bpy.context or not bpy.context.object or bpy.context.mode!='PAINT_WEIGHT': return
		if not cls.cleaner_active: return
		if cls.can_clean:
			cls.can_clean = False
			cls.cleaning_in_progress = True
			bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0.001) # This will trigger a depsgraph update, and therefore clean_weights, again.
			cls.cleaning_in_progress = False

	@classmethod
	def reset_flag(cls, scene, depsgraph):
		if not bpy.context or not bpy.context.object or bpy.context.mode!='PAINT_WEIGHT': return
		if cls.cleaning_in_progress: return
		if not cls.cleaner_active: return
		cls.can_clean = True

@persistent
def start_cleaner(scene, depsgraph):
	bpy.app.handlers.depsgraph_update_pre.append(WeightCleaner.clean_weights)
	bpy.app.handlers.depsgraph_update_post.append(WeightCleaner.reset_flag)

def register():
	from bpy.utils import register_class
	register_class(WPContextMenu)
	bpy.app.handlers.load_post.append(start_cleaner)
	
def unregister():
	from bpy.utils import unregister_class
	unregister_class(WPContextMenu)
	bpy.app.handlers.load_post.remove(start_cleaner)
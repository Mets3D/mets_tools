# A custom context menu for weight paint mode.

import bpy
from bpy.props import *

class WPContextMenu(bpy.types.Operator):
	""" Custom Weight Paint context menu """
	bl_idname = "object.custom_weight_paint_context_menu"
	bl_label = "Custom Weight Paint Context Menu"
	bl_options = {'REGISTER'}

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

	front_faces: BoolProperty(name="Front Faces Only", update=update_front_faces)
	falloff_shape: EnumProperty(name="Falloff Shape", update=update_falloff_shape,
		items=[
			('SPHERE', 'Sphere', 'Sphere'),
			('PROJECTED', 'Projected', 'Projected')
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
		row.prop(tool_settings, "use_multipaint", text="Multi-Paint", toggle=True)
		row.prop(context.weight_paint_object.data, "use_mirror_x", toggle=True)
		layout.separator()

		if context.pose_object:
			layout.label(text="Armature Display")
			layout.prop(context.pose_object.data, "display_type", expand=True)
			layout.prop(context.pose_object, "show_in_front", toggle=True)
	
	def invoke(self, context, event):
		active_brush = context.tool_settings.weight_paint.brush
		self.front_faces = active_brush.use_frontface
		self.falloff_shape = active_brush.falloff_shape
		
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def execute(self, context):
		return {'FINISHED'}


def register():
	from bpy.utils import register_class
	register_class(WPContextMenu)
	
def unregister():
	from bpy.utils import unregister_class
	unregister_class(WPContextMenu)
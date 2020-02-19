import bpy
from bpy.props import *

class ChangeWPBrush(bpy.types.Operator):
	""" Just change the weight paint brush to an actual specific brush rather than a vague tool """
	bl_idname = "brush.set_specific"
	bl_label = "Set WP Brush"
	bl_options = {'REGISTER', 'UNDO'}

	brush: EnumProperty(name="Brush",
	items=[('Add', 'Add', 'Add'),
			('Subtract', 'Subtract', 'Subtract'),
			('Draw', 'Draw', 'Draw'),
			('Average', 'Average', 'Average'),
			('Blur', 'Blur', 'Blur'),
			],
	default="Add")

	def execute(self, context):
		brush = self.brush

		bpy.context.tool_settings.weight_paint.brush = bpy.data.brushes[brush] #This will break if you delete or rename your brushes, so don't.

		return { 'FINISHED' }

def register():
	from bpy.utils import register_class
	register_class(ChangeWPBrush)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(ChangeWPBrush)
import bpy
from bpy.props import *
from bpy.app.handlers import persistent


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
		brush_name = self.brush
		brush = bpy.data.brushes.get(brush_name)
		if not brush:
			# Create the brush.
			if brush_name == 'Add':
				brush = bpy.data.brushes.new('Add', mode='WEIGHT_PAINT')
				brush.blend = 'ADD'
			if brush_name == 'Subtract':
				brush = bpy.data.brushes.new('Subtract', mode='WEIGHT_PAINT')
				brush.blend = 'SUB'
			if brush_name == 'Blur':
				brush = bpy.data.brushes.new('Blur', mode='WEIGHT_PAINT')
				brush.weight_tool = 'BLUR'
			if brush_name == 'Average':
				brush = bpy.data.brushes.new('Blur', mode='WEIGHT_PAINT')
				brush.weight_tool = 'AVERAGE'
		
		# Configure brush.
		# value = 0.5 if brush.falloff_shape == 'SPHERE' else 1.0
		# if brush_name=='Add':
		# 	brush.cursor_color_add = [value, 0.0, 0.0, 1.0] 
		# if brush_name=='Subtract':
		# 	brush.cursor_color_add = [0.0, 0.0, value, 1.0]
		# if brush_name=='Blur':
		# 	brush.cursor_color_add = [value, value, value, 1.0]

		bpy.context.tool_settings.weight_paint.brush = brush

		return { 'FINISHED' }

@persistent
def register_brush_switch_hotkeys(dummy):
	wp_hotkeys = bpy.data.window_managers[0].keyconfigs.active.keymaps['Weight Paint'].keymap_items
	
	add_hotkey = wp_hotkeys.new('brush.set_specific',value='PRESS',type='ONE',ctrl=False,alt=False,shift=False,oskey=False)
	add_hotkey.properties.brush = 'Add'
	add_hotkey.type = add_hotkey.type
	
	sub_hotkey = wp_hotkeys.new('brush.set_specific',value='PRESS',type='TWO',ctrl=False,alt=False,shift=False,oskey=False)
	sub_hotkey.properties.brush = 'Subtract'
	sub_hotkey.type = sub_hotkey.type
	
	blur_hotkey = wp_hotkeys.new('brush.set_specific',value='PRESS',type='THREE',ctrl=False,alt=False,shift=False,oskey=False)
	blur_hotkey.properties.brush = 'Blur'
	blur_hotkey.type = blur_hotkey.type

def register():
	from bpy.utils import register_class
	register_class(ChangeWPBrush)
	bpy.app.handlers.load_post.append(register_brush_switch_hotkeys)
	
def unregister():
	from bpy.utils import unregister_class
	unregister_class(ChangeWPBrush)
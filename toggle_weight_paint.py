import bpy

# This operator is to make entering weight paint mode less of a pain in the ass.

# It registers an operator called "Toggle Weight Paint Mode" that does the following:
# 	Set active object to weight paint mode
# 	Set shading mode to a white MatCap, Single Color shading
# 	Find first armature via modifiers and set it to pose mode.
# When running the operator again, it should restore all modes and shading settings.
# You need to set up your own keybind for this operator.

class ToggleWeightPaint(bpy.types.Operator):
	""" Toggle weight paint mode properly with a single operator. """
	bl_idname = "object.weight_paint_toggle"
	bl_label = "Toggle Weight Paint Mode"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		obj = context.object

		mode = obj.mode
		enter_wp = not (mode == 'WEIGHT_PAINT')

		# Finding armature.
		armature = None
		for m in obj.modifiers:
			if(m.type=='ARMATURE'):
				armature = m.object
				if not armature.visible_get():
					# Armature is hidden, ignore (for now).
					armature = None


		if(enter_wp):
			### Entering weight paint mode. ###
			# Set modes.
			if(armature):
				context.view_layer.objects.active = armature
				bpy.ops.object.mode_set(mode='POSE')
			context.view_layer.objects.active = obj
			bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

			# Store old shading settings in a dict custom property
			if('wpt' not in context.screen):
				context.screen['wpt'] = {}
			wpt = context.screen['wpt'].to_dict()
			if('last_switch_in' not in wpt or wpt['last_switch_in']==False):	# Only save shading info if we exitted weight paint mode using this operator.
				context.screen['wpt']['light'] = context.space_data.shading.light
				context.screen['wpt']['color_type'] = context.space_data.shading.color_type
				context.screen['wpt']['studio_light'] = context.space_data.shading.studio_light
				context.screen['wpt']['active_object'] = obj
			context.screen['wpt']['last_switch_in'] = True	# Store whether the last time the operator ran, were we switching into or out of weight paint mode.
			context.screen['wpt']['mode'] = mode
			
			# Set shading
			context.space_data.shading.light = 'MATCAP'
			context.space_data.shading.color_type = 'SINGLE'
			context.space_data.shading.studio_light = 'basic_1.exr'

		else:
			### Leaving weight paint mode. ###
			if('wpt' in context.screen):
				info = context.screen['wpt'].to_dict()
				# Restore mode.
				bpy.ops.object.mode_set(mode=info['mode'])
				context.screen['wpt']['last_switch_in'] = False

				# Restore shading options.
				context.space_data.shading.light = info['light']
				context.space_data.shading.color_type = info['color_type']
				context.space_data.shading.studio_light = info['studio_light']
			else:
				# If we didn't enter weight paint mode with this operator, just go into object mode when trying to leave WP mode with this operator.
				bpy.ops.object.mode_set(mode='OBJECT')

		return { 'FINISHED' }

def register():
	from bpy.utils import register_class
	register_class(ToggleWeightPaint)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(ToggleWeightPaint)
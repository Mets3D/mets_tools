import bpy
from bpy.props import *

# In order to apply (UNIFORM) scale on an armature without breaking the rigging, we need to apply the scale factor to all location values used by the rig.
# This includes:
# - Every property of every constraint that references a location/distance/length value.
# - Every location curve used by Action constraints.
# - Every driver expression that references a variable that is a location.

class ApplyArmatureScale(bpy.types.Operator):
	""" Apply uniform scaling to an armature while adjusting constraints and used Actions so the armature behaves identically on the new scale.
	Does not adjust drivers that might affect or read locations.
	Does not apply scale of child objects.
	"""
	bl_idname = "object.apply_armature_scale"
	bl_label = "Apply Armature Scale"
	bl_options = {'REGISTER', 'UNDO'}

	do_round: BoolProperty(name="Round Values", description="Round some less important values, like bone shape size", default=True)	# Actually it currently only does bone shape size.
	do_actions: BoolProperty(name="Adjust Actions", description="Adjust location curves of Actions that are used by any Action constraint", default=True)
	all_actions: BoolProperty(name="Adjust ALL Actions", description="Adjust location curves of ALL Actions in the scene, regardless of whether the action is used by the armature or not", default=False)
	#do_drivers: BoolProperty(name="Adjust Driver Expressions", description="Try to adjust driver expressions that read or write location")	# TODO, this seems tricky and I don't need it right now.
	
	def execute(self, context):
		o = context.object
		if(o.scale[0] != o.scale[1] or o.scale[0] != o.scale[2]):
			return {['CANCELLED']}	# Scale must be uniform!

		org_mode = o.mode
		bpy.ops.object.mode_set(mode='OBJECT')

		scale = o.scale[0]
		props = []
		actions = []

		for b in o.pose.bones:
			# Adjust bone properties
			if(not b.use_custom_shape_bone_size):
				b.custom_shape_scale *= scale
				if(self.do_round):
					b.custom_shape_scale = round(b.custom_shape_scale, 2)
			
			# Adjust constraints
			for c in b.constraints:
				if(c.type in ['LIMIT_LOCATION', 'LIMIT_SCALE']):
					props = ['min_x', 'max_x',
							'min_y', 'max_y',
							'min_z', 'max_z',
					]
				elif(c.type=='LIMIT_DISTANCE'):
					props = ['distance']
				elif(c.type=='TRANSFORM'):
					props = [
						"from_min_x", "from_max_x", "to_min_x", "to_max_x",
						"from_min_y", "from_max_y", "to_min_y", "to_max_y",
						"from_min_z", "from_min_z", "to_min_z", "to_max_z"
					]
				elif(c.type=='STRETCH_TO'):
					props = ["rest_length"]
				elif(c.type=='ACTION'):
					if(c.action not in actions):
						actions.append(c.action)
					props = ["min", "max"]
				elif(c.type=='FLOOR'):
					props = ["offset"]
				else:
					continue
				
				for prop in props:
					new_value = getattr(c, prop) * scale
					setattr(c, prop, new_value)
		
		# Adjust Actions
		if(self.do_actions):
			if(self.all_actions):
				actions = bpy.data.actions
			for action in actions:
				for cur in action.fcurves:
					if( ("location" in cur.data_path) ):
						for kf in cur.keyframe_points:
							kf.co[1] *= scale
							kf.handle_left[1] *= scale
							kf.handle_right[1] *= scale
		
		bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

		bpy.ops.object.mode_set(mode=org_mode)
		
		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	register_class(ApplyArmatureScale)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(ApplyArmatureScale)
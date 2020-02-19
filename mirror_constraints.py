import bpy
from math import *
from . import utils
from bpy.props import *

# When mirroring from right to left side, it seems like it doesn't flip names correctly, and also doesn't delete existing constraints.
# Child Of constraints' inverse matrices still don't always seem right.
# Split constraint mirror into a util function.

def mirror_drivers(armature, from_bone, to_bone, from_constraint=None, to_constraint=None):
	# Mirrors all drivers from one bone to another. from_bone and to_bone should be pose bones.
	# If from_constraint is specified, to_constraint also must be, and then copy and mirror drivers between constraints instead of bones.
	# TODO: This should use new abstraction implementation, and be split up to copy_driver and flip_driver, each of which should handle only one driver at a time.
	#	Actually, copy_driver would just be reading a driver into an abstract driver and then making it real somewhere else.
	if(not armature.animation_data): return	# No drivers to mirror.

	for d in armature.animation_data.drivers:					# Look through every driver on the armature
		if not ('pose.bones["' + from_bone.name + '"]' in d.data_path): continue		# Driver doesn't belong to source bone, skip.
		if("constraints[" in d.data_path and from_constraint==None): continue			# Driver is on a constraint, but no source constraint was given, skip.
		if(from_constraint!=None and from_constraint.name not in d.data_path): continue	# Driver is on a constraint other than the given source constraint, skip.
		
		### Copying mirrored driver to target bone...
		
		# The way drivers on bones work is weird af. You have to create the driver relative to the bone, but you have to read the driver relative to the armature. So d.data_path might look like "pose.bones["bone_name"].bone_property" but when we create a driver we just need the "bone_property" part.
		data_path_from_bone = d.data_path.split("].", 1)[1]
		new_d = None
		if("constraints[" in data_path_from_bone):
			data_path_from_constraint = data_path_from_bone.split("].", 1)[1]
			# Armature constraints need special special treatment...
			if(from_constraint.type=='ARMATURE' and "targets[" in data_path_from_constraint):
				target_idx = int(data_path_from_constraint.split("targets[")[1][0])
				target = to_constraint.targets[target_idx]
				# Weight is the only property that can have a driver on an Armature constraint's Target object.
				target.driver_remove("weight")
				new_d = target.driver_add("weight")
			else:
				to_constraint.driver_remove(data_path_from_constraint)
				new_d = to_constraint.driver_add(data_path_from_constraint)
		else:
			to_bone.driver_remove(data_path_from_bone)
			new_d = to_bone.driver_add(data_path_from_bone)
			
		expression = d.driver.expression
		
		# Copy the variables
		for from_var in d.driver.variables:
			to_var = new_d.driver.variables.new()
			to_var.type = from_var.type
			to_var.name = from_var.name
			
			for i in range(len(from_var.targets)):
				target_bone = from_var.targets[i].bone_target
				new_target_bone = utils.flip_name(target_bone)
				if(to_var.type == 'SINGLE_PROP'):
					to_var.targets[i].id_type			= from_var.targets[i].id_type
				to_var.targets[i].id 				= from_var.targets[i].id
				to_var.targets[i].bone_target 		= new_target_bone
				data_path = from_var.targets[i].data_path
				if "pose.bones" in data_path:
					bone_name = data_path.split('pose.bones["')[1].split('"')[0]
					flipped_name = utils.flip_name(bone_name, only=False)
					data_path = data_path.replace(bone_name, flipped_name)
				# HACK
				if "left" in data_path:
					data_path = data_path.replace("left", "right")
				elif "right" in data_path:
					data_path = data_path.replace("right", "left")
				to_var.targets[i].data_path 		= data_path
				to_var.targets[i].transform_type 	= from_var.targets[i].transform_type
				to_var.targets[i].transform_space 	= from_var.targets[i].transform_space
				# TODO: If transform is X Rotation, have a "mirror" option, to invert it in the expression. Better yet, detect if the new_target_bone is the opposite of the original.
			
			# Below is some old terrible code to add or remove a "-" sign before the variable's name in the expression... 
			# It's technically needed to mirror a driver correctly in some cases, but I'm not sure how to 
			# figure out whether a variable needs to be flipped or not.
			"""
			print(from_var.targets[0].transform_type)
			if( to_var.targets[0].bone_target and
				"SCALE" not in from_var.targets[0].transform_type and
				(from_var.targets[0].transform_type.endswith("_X") and flip_x) or
				(from_var.targets[0].transform_type.endswith("_Y") and flip_y) or
				(from_var.targets[0].transform_type.endswith("_Z") and flip_z)
				):
				# Flipping sign - this is awful, I know.
				if("-"+to_var.name in expression):
					expression = expression.replace("-"+to_var.name, "+"+to_var.name)
					print(1)
				elif("+ "+to_var.name in expression):
					expression = expression.replace("+ "+to_var.name, "- "+to_var.name)
					print(2)
				else:
					expression = expression.replace(to_var.name, "-"+to_var.name)
					print("3")"""
		
		# Copy the expression

		new_d.driver.expression = expression

def mirror_constraint(armature, bone, constraint, allow_split=True):
	b = bone
	c = constraint
	flipped_constraint_name = utils.flip_name(c.name, only=False)
	flipped_bone_name = utils.flip_name(b.name)
	opp_b = armature.pose.bones.get(flipped_bone_name)
	
	if(b == opp_b and not allow_split): return	# No opposite bone found and we cannot split, so we skip.
	if(b == opp_b and c.name == flipped_constraint_name): return	# No opposite bone found and the constraint name could not be flipped, so we skip.
	
	split = (b==opp_b) and (opp_b.constraints.get(flipped_constraint_name) == None)	# If the opposite constraint doesn't already exist, split the influences.
	
	opp_c = utils.find_or_create_constraint(opp_b, c.type, flipped_constraint_name)
	utils.copy_attributes(c, opp_c, skip=['name'])
	opp_c.name = flipped_constraint_name

	if(split):
		c.influence /= 2
		opp_c.influence /= 2
	
	if(hasattr(opp_c, 'subtarget')):	# Flip sub-target (bone)
		opp_c.subtarget = utils.flip_name(c.subtarget)
	
	# Need to mirror the curves in the action to the opposite bone.
	if(c.type=='ACTION' and b != opp_b):
		action = c.action
		# Flip min/max in some cases.
		if(c.transform_channel in ['ROTATION_Z', 'LOCATION_X']):
			opp_c.min = c.max
			opp_c.max = c.min

		curves = []
		for cur in action.fcurves:
			if(b.name in cur.data_path):
				curves.append(cur)
		for cur in curves:
			opp_data_path = cur.data_path.replace(b.name, opp_b.name)
			
			# Nuke opposite curves, just to be safe.
			while True:
				opp_cur = action.fcurves.find(opp_data_path, index=cur.array_index)
				if not opp_cur: break
				action.fcurves.remove(opp_cur)

			# Create opposite curve
			opp_cur = action.fcurves.new(opp_data_path, index=cur.array_index, action_group=opp_b.name)
			utils.copy_attributes(cur, opp_cur, skip=["data_path", "group"])
			
			# Copy keyframes
			for kf in cur.keyframe_points:
				# TODO: Maybe this part is unneccessary if we do recursive copy attributes above?
				opp_kf = opp_cur.keyframe_points.insert(kf.co[0], kf.co[1])
				utils.copy_attributes(kf, opp_kf, skip=["data_path"])
				# Flip X location, Y and Z rotation... not sure if applies to all situations... probably not :S
				if( ("location" in cur.data_path and cur.array_index == 0) or
					("rotation" in cur.data_path and cur.array_index in [1, 2]) ):
						opp_kf.co[1] *= -1
						opp_kf.handle_left[1] *=-1
						opp_kf.handle_right[1] *=-1

	elif(c.type=='ARMATURE'):
		for t in c.targets:
			opp_t = opp_c.targets.new()
			flipped_target = bpy.data.objects.get( utils.flip_name(t.target.name) )
			opp_t.target = flipped_target
			flipped_subtarget = utils.flip_name(t.subtarget)
			opp_t.subtarget = flipped_subtarget
			opp_t.weight = t.weight

	elif(c.type=='CHILD_OF' and c.target!=None):
		return # I don't care about child of constraints anymore, I use Armature Constraints now instead.

		org_influence = opp_c.influence
		org_active = armature.data.bones.active
		
		# Setting inverse matrix based on https://developer.blender.org/T39891#222496 but it doesn't seem to work. Maybe because the drivers don't get deleted before being re-mirrored? Therefore influence=1 doesn't work. TODO: We should just figure out what math to apply to the inverse matrix.
		armature.data.bones.active = opp_data_b
		opp_c.influence = 1
		context_py = bpy.context.copy()
		context_py["constraint"] = opp_c
		bpy.ops.constraint.childof_set_inverse(context_py, constraint=opp_c.name, owner='BONE')

		#opp_c.influence = org_influence
		opp_c.influence=0
		armature.data.bones.active = org_active

	elif(c.type=='IK'):
		opp_c.pole_target = c.pole_target
		opp_c.pole_subtarget = utils.flip_name(c.pole_subtarget)
		opp_c.pole_angle = (-pi/2) - (c.pole_angle + pi/2)

	elif(c.type=='LIMIT_LOCATION'):
		# X: Flipped and inverted.
		opp_c.min_x = c.max_x *-1
		opp_c.max_x = c.min_x *-1
		
	elif(c.type=='TRANSFORM'):
		###### SOURCES #######
		
		### Source Locations
		# X Loc: Flipped and Inverted
			opp_c.from_min_x = c.from_max_x *-1
			opp_c.from_max_x = c.from_min_x *-1
		# Y Loc: Same
		# Z Loc: Same

		### Source Rotations
		# X Rot: Same
		# Y Rot: Flipped and Inverted
			opp_c.from_min_y_rot = c.from_max_y_rot * -1
			opp_c.from_max_y_rot = c.from_min_y_rot * -1
		# Z Rot: Flipped and Inverted
			opp_c.from_min_z_rot = c.from_max_z_rot * -1
			opp_c.from_max_z_rot = c.from_min_z_rot * -1
		
		### Source Scales are same.
		
		###### DESTINATIONS #######
		
		### Destination Rotations
		
			### Location to Rotation
			if(c.map_from == 'LOCATION'):
				# X Loc to X Rot: Flipped
				if(c.map_to_x_from == 'X'):
					opp_c.to_min_x_rot = c.to_max_x_rot
					opp_c.to_max_x_rot = c.to_min_x_rot
				# X Loc to Y Rot: Same
				# X Loc to Z Rot: Flipped and Inverted
				if(c.map_to_z_from == 'X'):
					opp_c.to_min_z_rot = c.to_max_z_rot *-1
					opp_c.to_max_z_rot = c.to_min_z_rot *-1
				
				# Y Loc to X Rot: Same
				# Y Loc to Y Rot: Inverted
				if(c.map_to_y_from == 'Y'):
					opp_c.to_min_y_rot = c.to_min_y_rot *-1
					opp_c.to_max_y_rot = c.to_max_y_rot *-1
				# Y Loc to Z Rot: Inverted
				if(c.map_to_z_from == 'Y'):
					opp_c.to_min_z_rot = c.to_min_z_rot *-1
					opp_c.to_max_z_rot = c.to_max_z_rot *-1
				
				# Z Loc to X Rot: Same
				# Z Loc to Y Rot: Inverted
				if(c.map_to_y_from == 'Z'):
					opp_c.to_min_y_rot = c.to_min_y_rot *-1
					opp_c.to_max_y_rot = c.to_max_y_rot *-1
				# Z Loc to Z Rot: Inverted
				if(c.map_to_z_from == 'Z'):
					opp_c.to_min_z_rot = c.to_min_z_rot *-1
					opp_c.to_max_z_rot = c.to_max_z_rot *-1
		
			### Rotation to Rotation
			if(c.map_from == 'ROTATION'):
				# X Rot to X Rot: Same
				# X Rot to Y Rot: Inverted
				if(c.map_to_y_from == 'X'):
					opp_c.to_min_y_rot = c.to_min_y_rot *-1
					opp_c.to_max_y_rot = c.to_max_y_rot *-1
				# X Rot to Z Rot: Inverted
				if(c.map_to_z_from == 'X'):
					opp_c.to_min_z_rot = c.to_min_z_rot *-1
					opp_c.to_max_z_rot = c.to_max_z_rot *-1
				
				# Y Rot to X Rot: Flipped
				if(c.map_to_x_from == 'Y'):
					opp_c.to_min_x_rot = c.to_max_x_rot
					opp_c.to_max_x_rot = c.to_min_x_rot
				# Y Rot to Y Rot: Same
				# Y Rot to Z Rot: Flipped and Inverted
				if(c.map_to_z_from == 'Y'):
					opp_c.to_min_z_rot = c.to_max_z_rot * -1
					opp_c.to_max_z_rot = c.to_min_z_rot * -1
				
				# Z Rot to X Rot: Flipped
				if(c.map_to_x_from == 'Z'):
					opp_c.to_min_x_rot = c.to_max_x_rot
					opp_c.to_max_x_rot = c.to_min_x_rot
				# Z Rot to Y Rot: Flipped and Inverted
				if(c.map_to_y_from == 'Z'):
					opp_c.to_min_y_rot = c.to_max_y_rot * -1
					opp_c.to_max_y_rot = c.to_min_y_rot * -1
				# Z Rot to Z Rot: Flipped and Inverted
				if(c.map_to_z_from == 'Z'):
					opp_c.to_min_z_rot = c.to_max_z_rot * -1
					opp_c.to_max_z_rot = c.to_min_z_rot * -1
			
			### Scale to Rotation
			if(c.map_from == 'SCALE'):
				# ALL Scale to X Rot: Same
				# All Scale to Y Rot: Inverted
					opp_c.to_min_y_rot = c.to_min_y_rot *-1
					opp_c.to_max_y_rot = c.to_max_y_rot *-1
				# All Scale to Z Rot: Inverted
					opp_c.to_min_z_rot = c.to_min_z_rot *-1
					opp_c.to_max_z_rot = c.to_max_z_rot *-1
			
		### Destination Locations
			### Location to Location
			if(c.map_from == 'LOCATION'):
				# X Loc to X Loc: Flipped and Inverted
				if(c.map_to_x_from == 'X'):
					opp_c.to_min_x = c.to_max_x *-1
					opp_c.to_max_x = c.to_min_x *-1
				# X Loc to Y Loc: Flipped
				if(c.map_to_y_from == 'X'):
					opp_c.to_min_y = c.to_max_y
					opp_c.to_max_y = c.to_min_y
				# X Loc to Z Loc: Flipped
				if(c.map_to_z_from == 'X'):
					opp_c.to_min_z = c.to_max_z
					opp_c.to_max_z = c.to_min_z
				
				# Y Loc to X Loc: Inverted
				if(c.map_to_x_from == 'Y'):
					opp_c.to_min_x = c.to_min_x *-1
					opp_c.to_max_x = c.to_max_x *-1
				# Y Loc to Y Loc: Same
				# Y Loc to Z Loc: Same
				
				# Z Loc to X Loc: Inverted
				if(c.map_to_x_from == 'Z'):
					opp_c.to_min_x = c.to_min_x *-1
					opp_c.to_max_x = c.to_max_x *-1
				# Z Loc to Y Loc: Same
				# Z Loc to Z Loc: Same
			
			### Rotation to Location
			if(c.map_from == 'ROTATION'):
				# X Rot to X Loc: Inverted
				if(c.map_to_x_from == 'X'):
					opp_c.to_min_x = c.to_min_x * -1
					opp_c.to_max_x = c.to_max_x * -1
				# X Rot to Y Loc: Same
				# X Rot to Z Loc: Same
				
				# Y Rot to X Loc: Flipped and Inverted
				if(c.map_to_x_from == 'Y'):
					opp_c.to_min_x = c.to_max_x * -1
					opp_c.to_max_x = c.to_min_x * -1
				# Y Rot to Y Loc: Flipped
				if(c.map_to_y_from == 'Y'):
					opp_c.to_min_y = c.to_max_y
					opp_c.to_max_y = c.to_min_y
				# Y Rot to Z Loc: Flipped
				if(c.map_to_z_from == 'Y'):
					opp_c.to_min_z = c.to_max_z
					opp_c.to_max_z = c.to_min_z
				
				# Z Rot to X Loc: Flipped and inverted
				if(c.map_to_x_from == 'Z'):
					opp_c.to_min_x = c.to_max_x * -1
					opp_c.to_max_x = c.to_min_x * -1
				# Z Rot to Y Loc: Flipped
				if(c.map_to_y_from == 'Z'):
					opp_c.to_min_y = c.to_max_y
					opp_c.to_max_y = c.to_min_y
				# Z Rot to Z Loc: Flipped
				if(c.map_to_z_from == 'Z'):
					opp_c.to_min_z = c.to_max_z
					opp_c.to_max_z = c.to_min_z
			
			### Scale to Location
			if(c.map_from == 'SCALE'):
				# All Scale to X Loc: Inverted
				opp_c.to_min_x = c.to_min_x *-1
				opp_c.to_max_x = c.to_max_x *-1
				# All Scale to Y Loc: Same
				# All Scale to Z Loc: Same
		
		### Destination Scales
			# Location to Scale
			if(c.map_from == 'LOCATION'):
				# X Loc to All Scale: Flipped
				if(c.map_to_x_from == 'X'):
					opp_c.to_min_x_scale = c.to_max_x_scale
					opp_c.to_max_x_scale = c.to_min_x_scale
				if(c.map_to_y_from == 'X'):
					opp_c.to_min_y_scale = c.to_max_y_scale
					opp_c.to_max_y_scale = c.to_min_y_scale
				if(c.map_to_z_from == 'X'):
					opp_c.to_min_z_scale = c.to_max_z_scale
					opp_c.to_max_z_scale = c.to_min_z_scale
				# Y Loc to All Scale: Same
				# Z Loc to All Scale: Same
			
			# Rotation to Scale
			if(c.map_from == 'ROTATION'):
				# X Rot to All Scale: Same
				# Y Rot to All Scale: Flipped
				if(c.map_to_x_from == 'Y'):
					opp_c.to_min_x_scale = c.to_max_x_scale
					opp_c.to_max_x_scale = c.to_min_x_scale
				if(c.map_to_y_from == 'Y'):
					opp_c.to_min_y_scale = c.to_max_y_scale
					opp_c.to_max_y_scale = c.to_min_y_scale
				if(c.map_to_z_from == 'Y'):
					opp_c.to_min_z_scale = c.to_max_z_scale
					opp_c.to_max_z_scale = c.to_min_z_scale
				# Z Rot to All Scale: Flipped
				if(c.map_to_x_from == 'Z'):
					opp_c.to_min_x_scale = c.to_max_x_scale
					opp_c.to_max_x_scale = c.to_min_x_scale
				if(c.map_to_y_from == 'Z'):
					opp_c.to_min_y_scale = c.to_max_y_scale
					opp_c.to_max_y_scale = c.to_min_y_scale
				if(c.map_to_z_from == 'Z'):
					opp_c.to_min_z_scale = c.to_max_z_scale
					opp_c.to_max_z_scale = c.to_min_z_scale
			
			# Scale to Scale is all same.

	mirror_drivers(armature, b, opp_b, c, opp_c)

class XMirrorConstraints(bpy.types.Operator):
	""" Mirror constraints to the opposite of all selected bones. """
	bl_idname = "armature.x_mirror_constraints"
	bl_label = "X Mirror Selected Bones' Constraints"
	bl_options = {'REGISTER', 'UNDO'}

	allow_split: BoolProperty(name="Allow Splitting", 
		description="If a bone doesn't have an opposite, and its constraint name can be flipped, and a flipped constraint doesn't exist yet, mirror the constraint on the bone, and half its influence. Warning: If the influence has a driver on it, it can't be halved",
		default=True)

	@classmethod
	def poll(cls, context):
		return context.object.mode=='POSE'

	def execute(self, context):
		# TODO: We should fail with error on any bone that we don't find an opposite for, or any bone with unflippable name.
		# Opposite bone also selected should also be an error, since then the mirroring order is unpredictable.

		for b in context.selected_pose_bones:
			#TODO: Make a separate operator for "splitting" constraints in left/right parts. (by halving their influence, then mirror copying them onto the same bone)
			
			armature = context.object

			flipped_name = utils.flip_name(b.name)
			opp_b = armature.pose.bones.get(flipped_name)
			if(not opp_b): continue
			if(opp_b == b and not self.allow_split): continue
			opp_b.rotation_mode = b.rotation_mode
			opp_b.lock_rotation = b.lock_rotation
			opp_b.lock_rotation_w = b.lock_rotation_w
			opp_b.lock_scale = b.lock_scale
			opp_b.lock_location = b.lock_location

			# Mirror bone layers
			opp_b.bone.layers = b.bone.layers
			
			data_b = armature.data.bones.get(b.name)
			opp_data_b = armature.data.bones.get(opp_b.name)

			if(b != opp_b):
				# Mirror drivers on bone properties
				mirror_drivers(context.object, b, opp_b)
				# Wipe any existing constraints on the opposite side bone.
				for c in opp_b.constraints:
					opp_b.constraints.remove(c)

			# Mirror or split constraints and drivers on constraint properties.
			for c in b.constraints:
				mirror_constraint(armature, b, c)
		
			# Mirroring Bendy Bone settings
			opp_data_b.bbone_handle_type_start 		= data_b.bbone_handle_type_start
			opp_data_b.bbone_handle_type_end 		= data_b.bbone_handle_type_end
			if(data_b.bbone_custom_handle_start):
				opp_data_b.bbone_custom_handle_start 	= armature.data.bones.get(utils.flip_name(data_b.bbone_custom_handle_start.name))
			else:
				opp_data_b.bbone_custom_handle_start = None
			if(data_b.bbone_custom_handle_end):
				opp_data_b.bbone_custom_handle_end 		= armature.data.bones.get(utils.flip_name(data_b.bbone_custom_handle_end.name))
			else:
				opp_data_b.bbone_custom_handle_end = None
			opp_data_b.bbone_segments 				= data_b.bbone_segments
			# Inherit End Roll
			opp_data_b.use_endroll_as_inroll 		= data_b.use_endroll_as_inroll
			
			# Edit mode curve settings
			opp_data_b.bbone_curveinx = data_b.bbone_curveinx *-1
			opp_data_b.bbone_curveoutx = data_b.bbone_curveoutx *-1
			opp_data_b.bbone_curveiny = data_b.bbone_curveiny
			opp_data_b.bbone_curveouty = data_b.bbone_curveouty
			opp_data_b.bbone_rollin = data_b.bbone_rollin *-1
			opp_data_b.bbone_rollout = data_b.bbone_rollout *-1
			opp_data_b.bbone_scaleinx = data_b.bbone_scaleinx
			opp_data_b.bbone_scaleiny = data_b.bbone_scaleiny
			opp_data_b.bbone_scaleoutx = data_b.bbone_scaleoutx
			opp_data_b.bbone_scaleouty = data_b.bbone_scaleouty
			#TODO: Mirror bbone curve values.

			# Mirroring bone shape
			if(b.custom_shape and b != opp_b):
				opp_shape = bpy.data.objects.get(utils.flip_name(b.custom_shape.name))
				if(opp_shape):
					opp_b.custom_shape = opp_shape
				opp_data_b.show_wire = data_b.show_wire
				opp_b.custom_shape_scale = b.custom_shape_scale
				opp_b.use_custom_shape_bone_size = b.use_custom_shape_bone_size
				if(b.custom_shape_transform):
					opp_b.custom_shape_transform = armature.pose.bones.get(utils.flip_name(b.custom_shape_transform.name))

		return {"FINISHED"}

def register():
	from bpy.utils import register_class
	register_class(XMirrorConstraints)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(XMirrorConstraints)
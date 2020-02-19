import bpy

# I want an operator that sets up tangent controls for a BBone. Might need to be two operators, one for the start handle and one for the end handle.

# Usage:
# First select the first bbone
# Then select the 2nd bbone
# Run 'Create BBone Tangent' Operator.
# Parent the created bone to the control bone.

# Workings:
# Get unit vectors from each bone and average them (?)
# Spawn a bone at the head of the 2nd bone
# Tail = Head+that vector (maybe negative?)
# Set the bbone settings (First bone's end handle, second bone's start handle, is tangent of the new bone.)
# Name the new bone? First bone's name.replace('DEF', 'TAN')?

scalar = 0.005
bone_shape = bpy.data.objects.get('Shape_Arrow')

def CreateBBoneTangent(context):
	""" Create a tangent control for two connected BBones. """
	assert len(context.selected_pose_bones) == 2, "Only two bones should be selected."
	armature = context.object
	assert armature.data.use_mirror_x==False, "Things glitch out when X axis mirror is enabled, disable it plz."

	bpy.ops.object.mode_set(mode='EDIT')
	
	# Identifying bones
	eb1 = None
	eb2 = None
	for b in context.selected_editable_bones:
		# Removing bbone drivers
		for d in armature.animation_data.drivers:					# Look through every driver on the armature
			if('pose.bones["' + b.name + '"]' in d.data_path):	# If the driver belongs to the active bone
				# The way drivers on bones work is weird af. You have to create the driver relative to the bone, but you have to read the driver relative to the armature. So d.data_path might look like "pose.bones["bone_name"].bone_property" but when we create a driver we just need the "bone_property" part.
				data_path = d.data_path.split("].")[1]
				pb = armature.pose.bones[b.name]
				pb.driver_remove(data_path)
		
		if(b==context.active_bone):
			eb2 = b
		else:
			eb1 = b

	bone1_name = eb1.name
	bone2_name = eb2.name

	bone1_vec = (eb1.head - eb1.tail).normalized()
	bone2_vec = (eb2.head - eb2.tail).normalized()
	tan_eb_vec = (bone1_vec + bone2_vec) * 1/2 *-1

	bone_name = eb1.name.replace("DEF", "TAN")

	armature.data.use_mirror_x = False
	bpy.ops.armature.bone_primitive_add(name=bone_name)
	flipped_name = bone_name.replace(".L", ".R")#utils.flip_name(bone_name)
	if(flipped_name!=bone_name):
		bpy.ops.armature.bone_primitive_add(name=flipped_name)
	
	# For data and pose bone datablocks to be initialized, we need to enter pose mode.
	bpy.ops.object.mode_set(mode='POSE')
	bpy.ops.object.mode_set(mode='EDIT')
	# This apparently makes my bone pointers point to the wrong bones, so I'll re-initialize those too.
	eb1 = armature.data.edit_bones.get(bone1_name)
	eb2 = armature.data.edit_bones.get(bone2_name)

	tan_b = armature.data.bones.get(bone_name)
	tan_b.use_deform=False
	tan_b.layers = [False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
	tan_eb = armature.data.edit_bones.get(bone_name)
	tan_pb = armature.pose.bones.get(bone_name)
	
	if(bone_shape):
		tan_b.show_wire=True
		tan_pb.custom_shape = bone_shape
		tan_pb.use_custom_shape_bone_size = False

	# Setting parent
	ctr_bone_name = eb2.name.replace("DEF", "CTR")
	ctr_eb = armature.data.edit_bones.get(ctr_bone_name)
	if(ctr_eb):
		tan_eb.parent = ctr_eb
	
	armature.data.use_mirror_x = True # TODO: Set back to original value, and operate according to original value(ie. if it was set to off originally, don't do it on both sides)
	
	tan_eb.head = eb1.tail
	tan_eb.tail = tan_eb.head + tan_eb_vec * scalar
	tan_eb.roll = (eb1.roll + eb2.roll) / 2

	tan_eb.bbone_x = tan_eb.bbone_z = scalar * .05
	armature.data.use_mirror_x = False

	eb1.bbone_handle_type_end = 'TANGENT'
	eb1.bbone_custom_handle_end = tan_eb
	eb2.bbone_handle_type_start = 'TANGENT'
	eb2.bbone_custom_handle_start = tan_eb

	bpy.ops.object.mode_set(mode='POSE')

CreateBBoneTangent(bpy.context)
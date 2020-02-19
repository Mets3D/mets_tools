import bpy
from bpy.props import *
import mathutils
import math
import bmesh

def make_physics_bone_chain(armature, bones, pMesh=None):
	""" Apply physics to a single chain of bones. Armature needs to have clean transforms and be in rest pose.
		bones: list of bones in the chain, in correct hierarchical order"""
	# This function expects the armature with clean transforms and in rest pose.

	parent_bone = bones[0].parent	# Can be None.
	
	if(not pMesh):
		# Create physics mesh
		bpy.ops.mesh.primitive_plane_add(enter_editmode=True)
		# The new object is active and in edit mode
		pMesh = bpy.context.object
		bpy.context.object.name = "_Phys_" + bones[0].name

		# Deleting all verts
		bpy.ops.mesh.delete(type='VERT')
	
	bpy.context.view_layer.objects.active = pMesh
	bpy.ops.object.mode_set(mode='EDIT')
	bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

	# Using bmesh to add first vertex
	bm = bmesh.new()
	bm.from_mesh(pMesh.data)
	bm.verts.ensure_lookup_table()
	bpy.ops.object.mode_set(mode='OBJECT')
	for v in bm.verts:
		v.select_set(False)
	vert = bm.verts.new(bones[0].head)  # Add a new vert at first bone's location
	vert.select_set(True)
	bm.verts.ensure_lookup_table()
	bm.to_mesh(pMesh.data)
	bm.free()

	pin_group = pMesh.vertex_groups.get("Pin")
	if(not pin_group):
		pin_group = pMesh.vertex_groups.new(name='Pin')
		
	bpy.ops.object.mode_set(mode='EDIT')
	pMesh.vertex_groups.active_index = pin_group.index
	bpy.context.scene.tool_settings.vertex_group_weight = 1
	bpy.ops.object.vertex_group_assign()

	# Extruding verts to each bone's head
	for b in bones:
		bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value":(
		b.tail.x - b.head.x, 
		b.tail.y - b.head.y, 
		b.tail.z - b.head.z)})
		
		bpy.ops.object.vertex_group_remove_from()
		vg = pMesh.vertex_groups.new(name=b.name)
		pMesh.vertex_groups.active_index = vg.index
		bpy.ops.object.vertex_group_assign()

	bpy.ops.object.mode_set(mode='OBJECT')

	# Adding Cloth modifier
	bpy.ops.object.modifier_add(type='CLOTH')
	m_cloth = pMesh.modifiers["Cloth"]
	m_cloth.settings.vertex_group_mass = "Pin"

	if(parent_bone):
		bpy.ops.object.mode_set(mode='OBJECT')  		# Go to object mode
		bpy.ops.object.select_all(action='DESELECT')	# Deselect everything
		pMesh.select_set(True)  						# Select physics mesh
		armature.select_set(True)						# Select armature
		bpy.context.view_layer.objects.active = armature# Make armature active
		bpy.ops.object.mode_set(mode='POSE')			# Go into pose mode
		bpy.ops.pose.select_all(action='DESELECT')  	# Deselect everything
		parent_bone.bone.select = True   				# Select parent bone
		armature.data.bones.active = parent_bone.bone	# Make the parent bone active
		bpy.ops.object.parent_set(type='BONE')  		# Set parent (=Ctrl+P->Bone)
		parent_bone.bone.select = False

	# Setting up bone constraints
	bpy.context.view_layer.objects.active = armature
	for i, b in enumerate(bones):
		b.bone.select=True
		# Removing any existing constraints
		for c in b.constraints:
			b.constraints.remove(c)
		DT = bones[i].constraints.new(type='DAMPED_TRACK')
		DT.name = 'phys'
		DT.target = pMesh
		DT.subtarget = b.name

	bpy.ops.object.mode_set(mode='POSE')

	return pMesh

class MakePhysicsBones(bpy.types.Operator):
	""" Set up physics to all selected bone chains. Only the first bone of each chain should be selected. """
	bl_idname = "pose.make_physics_bones"
	bl_label = "Make Physics Bones"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):	
		armature = bpy.context.object

		if(armature.type!='ARMATURE'):
			print( "ERROR: Active object must be an armature. Select a chain of bones.")
			return { "CANCELLED" }

		# Preparing the armature and saving state
		org_pose = armature.data.pose_position
		armature.data.pose_position = 'REST'
		org_loc = armature.location[:]
		armature.location = (0,0,0)
		org_rot_euler = armature.rotation_euler[:]
		armature.rotation_euler = (0,0,0)
		org_rot_quat = armature.rotation_quaternion[:]
		armature.rotation_quaternion = (0,0,0,0)
		org_scale = armature.scale[:]
		armature.scale = (1,1,1)
		org_mode = armature.mode
		org_layers = armature.data.layers[:]
		armature.data.layers = [True]*32
		
		org_transform_orientation = bpy.context.scene.transform_orientation_slots[0].type
		bpy.context.scene.transform_orientation_slots[0].type = 'GLOBAL'
		org_cursor = bpy.context.scene.cursor.location[:]
		bpy.context.scene.cursor.location = ((0, 0, 0))

		bpy.ops.object.mode_set(mode='POSE')

		
		def get_chain(bone, ret=[]):
			""" Recursively build a list of the first children. """
			ret.append(bone)
			if(len(bone.children) > 0):
				return get_chain(bone.children[0], ret)
			return ret

		bones = bpy.context.selected_pose_bones
		pMesh = None
		for b in bones:
			if(b.parent not in bones):
				chain = get_chain(b, [])	# I don't know why but I have to pass the empty list for it to reset the return list.
				if(not pMesh):
					pMesh = make_physics_bone_chain(armature, chain)
				else:
					pMesh = make_physics_bone_chain(armature, chain, pMesh)
		

		# Extruding all verts to have faces, which is necessary for collision.
		# Additionally, the Angular bending model won't move if it has faces with 0 area, so I'm spreading the verts out a tiny amount on the X axis(picked arbitrarily).
		bpy.context.view_layer.objects.active = pMesh
		bpy.ops.object.mode_set(mode='EDIT')		
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value":(0.01, 0, 0)})
		bpy.ops.mesh.select_linked()
		bpy.ops.transform.translate(value=(-0.005, 0, 0))
		
		# Reset armature
		bpy.ops.object.mode_set(mode='OBJECT')
		bpy.context.view_layer.objects.active = armature
		armature.data.pose_position = org_pose
		armature.location = org_loc
		armature.rotation_euler = org_rot_euler
		armature.rotation_quaternion = org_rot_quat
		armature.scale = org_scale
		bpy.ops.object.mode_set(mode=org_mode)
		armature.data.layers = org_layers
		
		bpy.context.scene.transform_orientation_slots[0].type = org_transform_orientation
		bpy.context.scene.cursor.location = (org_cursor)

		return { 'FINISHED' }

def draw_func_MakePhysicsBones(self, context):
	self.layout.operator(MakePhysicsBones.bl_idname, text=MakePhysicsBones.bl_label)

def register():
	from bpy.utils import register_class
	register_class(MakePhysicsBones)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(MakePhysicsBones)
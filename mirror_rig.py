import bpy
import bmesh
from . import utils
from . import shape_key_utils

def mirror_mesh(obj):
	""" DEPRECATED, I THINK """
	mesh = obj.data
	# Mirror shape keys...
	# We assume that all shape keys ending in .L actually deform both sides, but are masked with a vertex group, which also ends in .L.
	# If the .R version of the shape key exists, delete it.
	# Save and temporarily remove the vertex group mask
	# Enable pinning and make this shape key active
	# New Shape From Mix
	# Rename the new shape key to .R and re-add vgroup masks.
	shape_keys = mesh.shape_keys.key_blocks
	# Remove shape keys if they already exist.
	sk_names = [sk.name for sk in shape_keys]
	done = []
	for skn in sk_names:
		if(skn in done): continue
		sk = shape_keys.get(skn)
		flipped_name = utils.flip_name(sk.name)
		if(flipped_name == sk.name): continue

		if(flipped_name in shape_keys):
			obj.active_shape_key_index = shape_keys.find(flipped_name)
			bpy.ops.object.shape_key_remove()
			done.append(skn)
			done.append(flipped_name)

	sk_names = [sk.name for sk in shape_keys]
	for skn in sk_names:
		sk = shape_keys.get(skn)
		flipped_name = utils.flip_name(sk.name)
		if(flipped_name == sk.name): continue
		
		flipped_vg = ""
		if(sk.vertex_group != ""):
			flipped_vg = utils.flip_name(sk.vertex_group)

		split_dict = {	# TODO maybe this should be built into the split function as some sort of preset or make another function that calls that after doing this.
			flipped_name : flipped_vg,
			}
		shape_key_utils.split_shapekey(obj, sk.name, split_dict)


class MirrorRig(bpy.types.Operator):
	""" Mirror rig stuff """
	bl_idname = "object.mirror_rig"
	bl_label = "Mirror Rig"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# TODO (due to shortage of time, do these manually for now)
		### MESH ###
		# Delete all verts with X<0
		# Add and apply mirror modifier
		# Split shape keys to left/right (automating this part is WIP)
		# Copy and mirror drivers
			# Need to figure out how to determine whether a variable in a driver should be inverted or not based on the transform axis. If it can't be done here, I don't understand why it could be done in the constraint mirror script - Maybe I made some incorrect assumptions in there??
		# 

		for o in context.selected_objects:
			context.view_layer.objects.active = o
			if(o.type=='MESH'):
				mirror_mesh(o)
			if(o.type=='ARMATURE'):
				mirror_armature(o)
		
		return { 'FINISHED' }


class MirrorObject(bpy.types.Operator):
	"""Mirror a mesh object around the X axis"""
	bl_idname = "object.mirror_object"
	bl_label = "Mirror Object"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# Work on single object for now.
		assert len(context.selected_objects)==1, "There must be exactly one selected object."
		o = context.object
		assert o.type=='MESH', "Active object is not a mesh."

		# Make sure transforms are zeroed
		assert o.location[:] == (0,0,0), "Location not 0,0,0."
		assert o.rotation_quaternion[:] == (1,0,0,0), "Rotation not 1,0,0,0."
		assert o.rotation_euler[:] == (0,0,0), "Rotation not 0,0,0."
		assert o.scale[:] == (1,1,1), "Scale not 1,1,1."

		# If there is a mirror modifier, remove it.
		for m in o.modifiers:
			if m.type=='MIRROR':
				o.modifiers.remove(m)
				break

		# Duplicate object
		bpy.ops.object.duplicate()
		flipped_o = bpy.context.object
		flipped_o.scale[0] = -1	# Scale X -1

		# Flipp vertex group and shape key names
		# TODO: Done this way, left and right shape keys are actually separate, which may not be what we want. Instead, we might want left and right shape keys to be duplicates of each other, simply using different mask vertex groups.
		done = []	# Don't flip names twice...
		things = [flipped_o.vertex_groups, flipped_o.data.shape_keys.key_blocks]
		for l in things:
			for vg in l:
				if(vg in done): continue
				old_name = vg.name
				flipped_name = utils.flip_name(vg.name)
				if(old_name == flipped_name): continue
				
				opp_vg = l.get(flipped_name)
				if(opp_vg):
					vg.name = "temp"
					opp_vg.name = old_name
					vg.name = flipped_name
					done.append(opp_vg)

				vg.name = flipped_name
				done.append(vg)
			done = []
		
		# Apply transforms
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

		# Fix normals
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.mesh.flip_normals()
		
		# Join into original
		bpy.ops.object.mode_set(mode='OBJECT')
		context.view_layer.objects.active = o
		o.select_set(True)
		bpy.ops.object.join()

		# Remove doubles on center line
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='DESELECT')

		bm = bmesh.from_edit_mesh(o.data)
		threshold = 0
		for v in bm.verts:
			if(v.co[0] <= threshold):
				v.select_set(True)
		bmesh.update_edit_mesh(o.data)
		bpy.ops.mesh.remove_doubles(threshold=0.00001)

		bpy.ops.object.mode_set(mode='OBJECT')

		return { 'FINISHED' }


def register():
	from bpy.utils import register_class
	register_class(MirrorRig)
	register_class(MirrorObject)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(MirrorRig)
	unregister_class(MirrorObject)
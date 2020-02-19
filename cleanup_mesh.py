import bpy
from math import pi
import bmesh

# TODO: test if removing useless UV maps works.

def cleanup_mesh(obj, 
		remove_doubles=False, 
		quadrangulate=False, 
		weight_normals=True, 
		seams_from_islands=True, 
		clear_unused_UVs=True, 
		rename_single_UV=True):
	
	# Mode management
	org_active = bpy.context.object
	org_mode = org_active.mode
	org_selected = bpy.context.selected_objects[:]
	bpy.ops.object.mode_set(mode='OBJECT')
	bpy.ops.object.select_all(action='DESELECT')
	bpy.context.view_layer.objects.active = obj
	obj.select_set(True)
	bpy.ops.object.mode_set(mode='EDIT')
	
	# Unhide and deselect verts
	bpy.ops.mesh.reveal()
	bpy.ops.mesh.select_all(action='DESELECT')

	# Renaming shape key blocks
	if(obj.data.shape_keys is not None):
		obj.data.shape_keys.name = "Keys_" + obj.name

	# Setting auto-smooth to 180 is necessary so that splitnormals_clear() doesn't mark sharp edges
	obj.data.use_auto_smooth = True
	org_angle = obj.data.auto_smooth_angle
	obj.data.auto_smooth_angle = pi
	bpy.ops.mesh.customdata_custom_splitnormals_clear()
	obj.data.auto_smooth_angle = org_angle

	# Tris to Quads
	if(quadrangulate):
		bpy.ops.mesh.tris_convert_to_quads(shape_threshold=1.0472, uvs=True, materials=True)
	
	# Remove Doubles / Merge By Distance
	if(remove_doubles):
		bpy.ops.mesh.remove_doubles(threshold=0.0001)
	
	bpy.ops.object.mode_set(mode='OBJECT')
	if(weight_normals):
		bpy.ops.object.calculate_weighted_normals()
	bpy.ops.object.mode_set(mode='EDIT')
	
	### Removing useless UVMaps
	if(clear_unused_UVs):
		mesh = obj.data
		bm = bmesh.from_edit_mesh(mesh)

		# Invalid UV maps usually have all the verts on the top left or top right corner, so that's what we'll be checking for.
		# If all verts of a UV map have an X coordinate of 0, we're deleting it.

		for uv_idx in reversed(range(0, len(mesh.uv_layers))):			# For each UV layer (in reverse, since we're deleting)
			delet_this=True
			mesh.uv_layers.active_index = uv_idx
			bm.faces.ensure_lookup_table()
			for f in bm.faces:						# For each face
				for l in f.loops:					# For each loop(whatever that means)
					if(l[bm.loops.layers.uv.active].uv[0] != 0.0):	# If the loop's UVs first vert's x coord is NOT 0
						delet_this=False
						break
				if(delet_this==False):
					break
			if(delet_this):
				obj.data.uv_layers.remove(obj.data.uv_layers[uv_idx])
	
		bmesh.update_edit_mesh(mesh, True)
		
	# Renaming single UV maps
	if(len(mesh.uv_layers)==1 and rename_single_UV):
		mesh.uv_layers[0].name = 'UVMap'
	
	# Seams from islands
	if(seams_from_islands):
		bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
	
	# Mode management
	bpy.ops.object.mode_set(mode='OBJECT')
	for o in org_selected:
		o.select_set(True)
	bpy.context.view_layer.objects.active = org_active
	bpy.ops.object.mode_set(mode=org_mode)
	
class CleanUpMesh(bpy.types.Operator):
	""" Clean up meshes of selected objects. """
	bl_idname = "object.mesh_cleanup"
	bl_label = "Clean Up Mesh"
	bl_options = {'REGISTER', 'UNDO'}
	
	# TODO: unhide all verts in edit mode.

	remove_doubles: bpy.props.BoolProperty(
		name="Remove Doubles",
		description="Enable remove doubles",
		default=False
	)
	
	quadrangulate: bpy.props.BoolProperty(
		name="Tris to Quads",
		description="Enable Tris to Quads (UV Seams enabledd)",
		default=False
	)
	
	weight_normals: bpy.props.BoolProperty(
		name="Weight Normals",
		description="Enable weighted normals",
		default=False
	)
	
	seams_from_islands: bpy.props.BoolProperty(
		name="Seams from Islands",
		description="Create UV seams based on UV islands",
		default=False
	)
	
	clear_unused_UVs: bpy.props.BoolProperty(
		name="Delete Unused UV Maps",
		description="If all UV verts' X coordinate is 0, the UV map will be deleted.",
		default=True
	)
	
	rename_single_UV: bpy.props.BoolProperty(
		name="Rename Singular UV Maps",
		description="If an object is only left with one UV map, rename it to the default name, 'UVMap'.",
		default=True
	)
	
	def execute(self, context):
		for o in bpy.context.selected_objects:
			cleanup_mesh(o, 
				self.remove_doubles, 
				self.quadrangulate, 
				self.weight_normals, 
				self.seams_from_islands, 
				self.clear_unused_UVs, 
				self.rename_single_UV)
		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	register_class(CleanUpMesh)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(CleanUpMesh)
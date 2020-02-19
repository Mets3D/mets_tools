import bpy
import bmesh
from bpy.props import *
from mathutils import Vector

def uv_from_vert_average(uv_layer, v):
	uv_average = Vector((0.0, 0.0))
	total = 0.0
	for loop in v.link_loops:
		uv_average += loop[uv_layer].uv
		total += 1.0

	if total != 0.0:
		return uv_average * (1.0 / total)
	else:
		return None

class JoinAsShapeKeyByUVs(bpy.types.Operator):
	""" Transfer the shape of selected objects into shape keys on the active object. The objects need to have identical topology and UV layout on UV layer 1. Those UV layers shouldn't have any overlapping UVs. """
	bl_idname = "object.join_as_shape_key_by_uvs"
	bl_label = "Join as Shape Key by UVs"
	bl_options = {'REGISTER', 'UNDO'}

	# Some of this code is from StackOverflow, but then again, what code isn't?

	precision: FloatProperty(
		name='Precision',
		default=0.0001,
		description="UV coord matching precision. Higher values are less precise. Too high will cause mismatches and too low will cause no matches. Ideally your UVs are absolutely exactly the same and you can keep this value very low without getting any non-matches."
	)

	def execute(self, context):
		# Saving active object's verts and average UV coords
		bpy.ops.object.mode_set(mode='EDIT')
		active = bpy.context.object
		active_bm = bmesh.from_edit_mesh(active.data)
		active_uv_layer = active_bm.loops.layers.uv.active
		active_verts = []
		active_verts_uv_averages = []
		for active_v in active_bm.verts:
			active_verts.append( Vector((active_v.co.x, active_v.co.y, active_v.co.z)) )
			active_verts_uv_averages.append(uv_from_vert_average(active_uv_layer, active_v))
		
		bpy.ops.object.mode_set(mode='OBJECT')

		for obj in bpy.context.selected_objects:
			if(obj == active): continue
			#if(len(obj.data.vertices) != len(active.data.vertices)): continue	# Forcing matching vert count is not important.
			
			if(active.data.shape_keys == None):
				active.shape_key_add(name='Basis', from_mix=False)
			sk = active.shape_key_add(name=obj.name, from_mix=False)
			
			bpy.ops.object.mode_set(mode='EDIT')
			
			obj_bm = bmesh.from_edit_mesh(obj.data)
			obj_uv_layer = obj_bm.loops.layers.uv.active
			obj_verts = []
			obj_verts_uv_averages = []
			for obj_v in obj_bm.verts:
				obj_verts.append( Vector((obj_v.co.x, obj_v.co.y, obj_v.co.z)) )
				obj_verts_uv_averages.append(uv_from_vert_average(obj_uv_layer, obj_v))
			
			# Changing the shape key data needs to be done in object mode, otherwise the shape key data disappears when leaving edit mode. I'm not sure if this is a 2.8 bug.
			# This is the whole reason I have to save the vert coords and UV coords before doing this. Otherwise everything could be done in multi-object edit mode.
			bpy.ops.object.mode_set(mode='OBJECT')
			
			for oi, obj_v in enumerate(obj_verts):
				obj_uv_average = obj_verts_uv_averages[oi]
				for ai, active_v in enumerate(active_verts):
					active_uv_average = active_verts_uv_averages[ai]
					diff = active_uv_average - obj_uv_average
					if(abs(diff.x) < self.precision and
						abs(diff.y) < self.precision):
						sk.data[ai].co = obj_v
						break
		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	register_class(JoinAsShapeKeyByUVs)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(JoinAsShapeKeyByUVs)
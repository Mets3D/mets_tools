bl_info = {
	"name": "Distance Weighted Shape Key Transfer",
	"description": "Smart Transfer Weights operator",
	"author": "Mets 3D",
	"version": (2, 0),
	"blender": (2, 80, 0),
	"location": "Search -> Smart Weight Transfer",
	"category": "Object"
}

import bpy
from bpy.props import *
import bmesh

import mathutils
from mathutils import Vector
import math

from mets_tools.armature_nodes.driver import Driver

def build_kdtree(vertices):
	kd = mathutils.kdtree.KDTree(len(vertices))
	for i, v in enumerate(vertices):
		kd.insert(v.co, i)
	kd.balance()
	return kd

def smart_sk_transfer(obj_from, obj_to, expand=2):
	""" Transfer Shape Key (This is actually dumb, not smart. Or at least, it works poorly.) """

	# For each target vertex
	# Find x number of nearest source vertices
	# Add up their vectors with an influence based on their distance from the target vertex
	#   In weight transfer we had the benefit that the values are normalized, but that won't be the case here. What do we do about that?
	#   We have to go back to the old solution we originally came up with, but deleted. We have to make sure that the "total" transferred influence adds up to "100%", whatever that means.
	#   So if we transfer from the 5 nearest verts, each a bit further away from the last one... An equal split would be taking 20% from each of them... But we want more from the closer one and less from the further one. But how much more or less?
	#   What if we did 
	#   nearest_influence = 1-nearest_distance/furthest_distance
	#   furthest_influence = nearest_distance/furthest_distance
	#   I think that would work if we only had 2 influences...
	
	#   What if we normalized the distances in the sense that, the furthest distance would be 1.0 and no distance would be 0.0? Would the resulting values help in determining the influence?
	#   Say if the distances were 10, 5, 2, 1 they would be normalized down to 1, 0.5, 0.2, 0.1 (divide by maximum)
	#   After that, invert them so they are closer to representing desired influence rather than distance, so it's 0, 0.5, 0.8, 0.9. This logic results in the furthest vertex always being ignored, but ohwell?
	#   Then normalize these numbers in a different sense, so that they add up to 1. So divide each by their sum.
	#   Sum= 0.5+0.8+0.9=2.2
	#   10,5,	 2,	  1
	#   0, 0.227, 0.3636, 0.409
	#   So then we would want to multiply the shape key vector by this scalar and hope that the sum of those would be what we want to apply to the target vertex.

	# Idea: What if we took the vector of the nearest vert and "normalized" our results to that, just like we normalized weights?
	# So the closest vert's offset is multiplied by the farthest vert's distance, and vice versa. Then we take the results and ensure that their sum magnitude is the same as the first vert's vector's magnitude? idk..

	# Due to a weird bug(?) where the mesh fails to stay written when changing back into object mode, we must make sure that the target mesh does NOT enter edit mode while we are modifying the shape key.
	# So deselect it.
	obj_to.select_set(False)

	source_sk = obj_from.active_shape_key
	new_sk = obj_to.shape_key_add(name=source_sk.name)

	kd = build_kdtree(source_sk.data)
	
	# Assuming obj_from is at least selected, but probably active. (Shouldn't matter thanks to multi-edit mode?)
	bpy.ops.object.mode_set(mode='EDIT')
	bm = bmesh.from_edit_mesh(obj_from.data)

	for t_i, v in enumerate(obj_to.data.vertices):
		# Finding the nearest vertex on source object
		nearest_co, nearest_idx, nearest_dist = kd.find(v.co)
		
		# NOTE: We do NOT want to find any more vertices by distance beside the nearest one. The rest of the considered vertices should be this one's neighbors.
		# TODO: Although that said, it would be nice if we could consider the nearest neighbors first. Right now we are just expanding the selection of verts that we draw from, which might not give us enough control, especially when the source mesh is low poly.
		# Find neighbouring verts to the nearest vert. Save their index to this list. Will later turn it into a list of (index, distance) tuples.
		
		if(False):   # TODO: pass a flag for whether we want to transfer from neighbors of nearest vert or list of nearest verts.
		
			bm.verts.ensure_lookup_table()
			bmv = bm.verts[nearest_idx]
		
			for i in range(0, expand):
				new_indices = []
				for v_idx in source_vert_indices:
					cur_bmv = bm.verts[v_idx]
					for e in cur_bmv.link_edges:
						v_other = e.other_vert(cur_bmv)
						if(v_other.index not in source_vert_indices):
							new_indices.append(v_other.index)
				source_vert_indices.extend(new_indices)

		source_verts = []
		for vi in source_vert_indices:
			distance = (v.co - bm.verts[vi].co).length
			source_verts.append((vi, distance))
		
		# Sort valid verts by distance (least to most distance)
		source_verts.sort(key=lambda tup: tup[1])

		influences = {} # index:influence dictionary
		# First, map the distance range to 0-1 by dividing each distance by the max distance.
		# Invert the value, since we want influence to be inversely proportional to distance.
		max_distance = source_verts[-1][1]
		influence_sum = 0
		for v in source_verts:
			influences[v] = 1 - v[1]/max_distance
			influence_sum = influence_sum + influences[v]
		
		# Then normalize the influences so their sum is 1.
		for idx in influences.keys():
			influences[idx] = influences[idx]/influence_sum

		# Calculate the resulting shape key vector of this target vertex by multiplying the source vertices vectors by their influence and taking the sum of those.
		result_vector = Vector((0,0,0))
		for idx in influences.keys():
			source_vert_co = obj_from.data.vertices[idx].co
			source_vert_sk_co = source_sk.data[idx].co
			source_vector = source_vert_sk_co - source_vert_co
			result_vector = result_vector + source_vector * influences[idx]
		
		# Apply result vector to this vertex in the new shape key.
		new_sk.data[t_i].co += result_vector

def surface_deform_transfer_sk(context, obj_from, obj_to, sk_indices=[]):
	# Enable pin button on shape key thingie on both objects
	# For each shape key name
		# Add a surface deform modifier to obj_to
		# set both objects to Basis shape
		# Bind surface deform modifier
		# Set obj_from to the desired(original) shape key
		# Apply surface deform modifier as shape key
		# Rename shape key to source shape key name
		# Bonus: Copy driver from source shape key's value if there is one.
	
	context.view_layer.objects.active = obj_to

	obj_from.show_only_shape_key = True
	obj_to.show_only_shape_key = True

	for i in sk_indices:
		sk = obj_from.data.shape_keys.key_blocks[i]
		obj_from.active_shape_key_index = 0

		surf_def = obj_to.modifiers.new(name=sk.name, type='SURFACE_DEFORM')
		surf_def.target = obj_from
		bpy.ops.object.surfacedeform_bind(modifier=sk.name)
		obj_from.active_shape_key_index = i

		bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=sk.name)

		new_sk = obj_from.data.shape_keys.key_blocks[-1]

		driver_data_path = 'key_blocks["' + sk.name + '"].value'
		driver = obj_from.data.shape_keys.animation_data.drivers.find(driver_data_path)
		if driver:
			Driver.copy_driver(driver, obj_to.data.shape_keys, driver_data_path)
	
	context.view_layer.objects.active = obj_from

class CheckBoxWithName(bpy.types.PropertyGroup):
	"""Checkbox with a name and index.
	"""
	
	index: IntProperty()
	value: BoolProperty(
		name='Boolean Value',
		description='',
	)

class ShapeKeyTransferOperatorSD(bpy.types.Operator):
	"""Transfer selected shape keys from active to selected objects using Surface Deform modifier."""
	bl_idname = "object.shape_key_transfer_sd"
	bl_label = "Transfer Shape Key With Surface Deform"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.object is not None

	def invoke(self, context, event):
		context.scene.shape_keys_transferred.clear()
		for i, sk in enumerate(context.object.data.shape_keys.key_blocks):
			checkbox = context.scene.shape_keys_transferred.add()
			checkbox.value = False
			checkbox.name = sk.name
			checkbox.index = i
		
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def draw(self, context):
		layout = self.layout
		col = layout.column()

		for checkbox in context.scene.shape_keys_transferred:
			col.prop(checkbox, 'value', text=checkbox.name)

	def execute(self, context):
		assert len(context.selected_objects) > 1, "At least two objects must be selected. Select the source object last."

		sk_indices = []
		for checkbox in context.scene.shape_keys_transferred:
			if checkbox.value == True:
				sk_indices.append(checkbox.index)
		
		for o in context.selected_objects:
			if o == context.object: continue
			if o.type!='MESH': continue
			if not o.data or not o.data.shape_keys: continue
			surface_deform_transfer_sk(context, context.object, o, sk_indices)
		
		context.scene.shape_keys_transferred.clear()

		return { 'FINISHED' }

class ShapeKeyTransferOperator(bpy.types.Operator):
	""" Transfer a shape key from active to selected objects based on weighted vert distances """
	bl_idname = "object.shape_key_transfer"
	bl_label = "Transfer Shape Key"
	bl_options = {'REGISTER', 'UNDO'}
	
	def get_vgroups(self, context):
		items = [('None', 'None', 'None')]
		for vg in context.object.vertex_groups:
			items.append((vg.name, vg.name, vg.name))
		return items

	opt_mask_vgroup: EnumProperty(name="Operator Mask",
		items=get_vgroups,
		description="The operator's effect will be masked by this vertex group, unless 'None'")
	
	@classmethod
	def poll(cls, context):
		return (context.object is not None)

	def execute(self, context):
		assert len(context.selected_objects) > 1, "At least two objects must be selected. Select the source object last."
		
		source_obj = context.object
		for o in context.selected_objects:
			if(o==source_obj or o.type!='MESH'): continue
			
			mask_vgroup = o.vertex_groups.get(self.opt_mask_vgroup)
			
			smart_sk_transfer(source_obj, o, mask_vgroup)
			
			bpy.context.view_layer.objects.active = o
		
		return { 'FINISHED' }

def register():
	from bpy.utils import register_class
	register_class(CheckBoxWithName)
	register_class(ShapeKeyTransferOperatorSD)
	bpy.types.Scene.shape_keys_transferred = bpy.props.CollectionProperty(type=CheckBoxWithName)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(CheckBoxWithName)
	register_class(ShapeKeyTransferOperatorSD)

register()
import bpy
import bmesh
from mathutils import Vector

# This is meant to identify identical vertices in two objects based on their vertex weights, and then copy shape keys from one to the other based on that mapping.
# TODO: I never actually made use of this code, but I think it works? Or at least worked in 2.7.
# Obviously, this relies on the assumption that the vertex weights are unique and matching between the two objects.
# This is meant as a plan D for when vertex indicies don't match, topology doesn't match, and UV coordinates don't match.

def build_weight_dict(obj, vgroups=None, mask_vgroup=None, bone_combine_dict=None):
	# Returns a dictionary that matches the vertex indicies of the object to a list of tuples containing the vertex group names that the vertex belongs to and the weight of the vertex in that group.
	# Optionally, if vgroups is passed, don't bother saving groups that aren't in vgroups.
	# Also optionally, bone_combine_dict can be specified if we want some bones to be merged into others, eg. passing in {'Toe_Main' : ['Toe1', 'Toe2', 'Toe3']} will combine the weights in the listed toe bones into Toe_Main. You would do this when transferring weights from a model of actual feet onto shoes.
	
	weight_dict = {}	# {vert index : [('vgroup_name', vgroup_value), ...], ...}
	
	if(vgroups==None):
		vgroups = obj.vertex_groups
	
	for v in obj.data.vertices:
		# TODO: instead of looking through all vgroups we should be able to get only the groups that this vert is assigned to via v.groups[0].group which gives the group id which we can use to get the group via Object.vertex_groups[id]
		# With this maybe it's useless altogether to save the weights into a dict? idk.
		# Although the reason we are doing it this way is because we wanted some bones to be considered the same as others. (eg. toe bones should be considered a single combined bone)
		for vg in vgroups:
			w = 0
			try:
				w = vg.weight(v.index)
			except:
				pass
			
			# Adding the weights from any sub-vertexgroups defined in bone_combine_dict
			if(vg.name in bone_combine_dict.keys()):
				for sub_vg_name in bone_combine_dict[vg.name]:
					sub_vg = obj.vertex_groups.get(sub_vg_name)
					if(sub_vg==None): continue
					try:
						w = w + sub_vg.weight(v.index)
					except RuntimeError:
						pass
			
			if(w==0): continue
			
			# Masking transfer influence
			if(mask_vgroup):
				try:
					multiplier = mask_vgroup.weight(v.index)
					w = w * multiplier
				except:
					pass
			
			# Create or append entry in the dict.
			if(v.index not in weight_dict):
				weight_dict[v.index] = [(vg.name, w)]
			else:
				weight_dict[v.index].append((vg.name, w))
	
	return weight_dict

active = bpy.context.object
active_weights = build_weight_dict(active)

for obj in bpy.context.selected_objects:
	if(obj == active): continue

	if(active.data.shape_keys == None):
		active.shape_key_add(name='Basis', from_mix=False)
	sk = active.shape_key_add(name=obj.name, from_mix=False)
	
	obj_weights = build_weight_dict(obj)
	
	for active_vert_index in active_weights.keys():
		active_vert_weights = active_weights[active_vert_index]
		for obj_vert_index in obj_weights.keys():
			obj_vert_weights = obj_weights[obj_vert_index]
			matching = True	# Stores whether this vert has the same weights as the active vert.
			for weight_tuple in obj_vert_weights:
				if(weight_tuple not in active_vert_weights):
					matching=False
					break
			if(matching):
				sk.data[active_vert_index].co = obj_vert_index
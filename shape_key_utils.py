import bpy

# The workflow this script helps us achieve, is to be able to sculpt a single shape in a shape key, 
# and then be able to split that shape up into multiple shape keys that are blended by different bones(using drivers, which are created manually)

# For example, we can sculpt a single shape key on the hand for how the hand should look like when all fingers are bent 90 degrees.
# Then we can split this shape key up into 4 parts, one for each finger, by:
# 	Duplicating the original shape key 4 times
#	Assigning mask vertex groups to these duplicates
#		Ensuring those mask vertex groups are normalized, such that their weights add up to 1 on any given vertex.

def normalize_vgroups(o, vgroups):
	"""Normalize a set of vertex groups, such that their weights add up to 1 on any given vertex that are assigned to any of the groups."""
	for v in o.data.vertices:
		# Find sum of weights in specified vgroups
		sum_weights = 0
		for vg in vgroups:
			w = 0
			try:
				sum_weights += vg.weight(v.index)
			except:
				pass
		for vg in vgroups:
			try:
				# set weight to original/sum
				vg.add([v.index], vg.weight(v.index)/sum_weights, 'REPLACE')
			except:
				pass

def split_shapekey(o, source_name, split_names):
	""" Make copies of source shape key, rename them to target names, and assign a mask vertex group.
		The use case is when we want to blend into a shape key using multiple masks. 
		split_names: Dictionary of {shape key name : mask vgroup name} # TODO this should be a tuple, not a dict.
	"""
	
	# TODO: We will use this to split left/right halves as well, I suppose.
	
	shape_keys = o.data.shape_keys.key_blocks
	# Ensure source shape key exists.
	source_sk = shape_keys.get(source_name)
	assert source_sk, "Error: Source shape key does not exist: " + source_name
	
	# For performance we have to turn off subsurf (otherwise changing shape key order takes for ever)
	org_levels = None
	subsurf_mod = None
	for m in o.modifiers:
		if(m.type=='SUBSURF'):
			subsurf_mod = m
			org_levels = m.levels
			m.levels = 0

	# Save active shape key
	active_sk_name = o.active_shape_key.name
	
	# Enable the source shape key and save mute state - This is needed because pin button doesn't work when shape key is disabled.
	org_mute = source_sk.mute
	source_sk.mute = False
	# Enable pin button
	o.show_only_shape_key = True
	# Save and remove mask
	mask_vg = source_sk.vertex_group
	source_sk.vertex_group = ""
	
	# Create copies
	for name in split_names.keys():
		# If already exists, delete it
		index = None
		if(name in shape_keys):
			index = shape_keys.find(name)
			o.shape_key_remove(shape_keys[name])

		o.active_shape_key_index = shape_keys.find(source_name)
		new_sk = o.shape_key_add(name=name, from_mix=True)
		vg = o.vertex_groups.get(split_names[name])
		if(vg):
			new_sk.vertex_group = vg.name
		new_sk.mute=org_mute

		# Restore shape key order
		if(index):
			o.active_shape_key_index = len(shape_keys) -1
			for i in range(index, len(shape_keys)-1):
				bpy.ops.object.shape_key_move(type='UP')
	
	# Restore mute state
	source_sk.mute = org_mute

	# Restore vertex mask
	source_sk.vertex_group = mask_vg

	# Restore subsurf level
	if(subsurf_mod):
		subsurf_mod.levels = org_levels
	
	# Restore active shape key
	o.active_shape_key_index = shape_keys.find(active_sk_name)

# To use, uncomment and customize the stuff below:
"""
o = bpy.context.object

### FINGERS ###
finger_mask_names = [
	"SK:Finger_Index.L",
	"SK:Finger_Middle.L",
	"SK:Finger_Ring.L",
	"SK:Finger_Pinky.L"
]
finger_mask_vgs = [vg for vg in o.vertex_groups if vg.name in finger_mask_names]
normalize_vgroups(o, finger_mask_vgs)

finger_bends1 = {
	"Finger_Index1.L" : "SK:Finger_Index.L",
	"Finger_Middle1.L" : "SK:Finger_Middle.L",
	"Finger_Ring1.L" : "SK:Finger_Ring.L",
	"Finger_Pinky1.L" : "SK:Finger_Pinky.L",
}
finger_bends2 = {
	"Finger_Index2.L" : "SK:Finger_Index.L",
	"Finger_Middle2.L" : "SK:Finger_Middle.L",
	"Finger_Ring2.L" : "SK:Finger_Ring.L",
	"Finger_Pinky2.L" : "SK:Finger_Pinky.L",
}
finger_bends3 = {
	"Finger_Index3.L" : "SK:Finger_Index.L",
	"Finger_Middle3.L" : "SK:Finger_Middle.L",
	"Finger_Ring3.L" : "SK:Finger_Ring.L",
	"Finger_Pinky3.L" : "SK:Finger_Pinky.L",
}

split_shapekey(o, "FingerBends1", finger_bends1)
split_shapekey(o, "FingerBends2", finger_bends2)
split_shapekey(o, "FingerBends3", finger_bends3)
"""
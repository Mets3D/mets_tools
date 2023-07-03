import bpy
from typing import List

def find_invalid_constraints(context, hidden_is_invalid=False):
	# If hidden=True, disabled constraints are considered invalid.
	o = context.object
	present = True

	if(present):
		o.data.layers = [True] * 32

	for b in o.pose.bones:
		if len(b.constraints) == 0:
			b.bone.hide = True
		for c in b.constraints:
			if not c.is_valid or (hidden_is_invalid and c.mute):
				b.bone.hide = False
				break
			else:
				b.bone.hide = True

def reset_stretch(armature):
	for b in armature.pose.bones:
		for c in b.constraints:
			if(c.type=='STRETCH_TO'):
				c.rest_length = 0
				c.use_bulge_min=True
				c.use_bulge_max=True
				c.bulge_min=1
				c.bulge_max=1
	

def connect_parent_bones():
	# If the active object is an Armature
	# For each bone
	# If there is only one child
	# Move the tail to the child's head
	# Set Child's Connected to True

	armature = bpy.context.object
	if(armature.type != 'ARMATURE'): return
	else:
		bpy.ops.object.mode_set(mode="EDIT")
		for b in armature.data.edit_bones:
			if(len(b.children) == 1):
				b.tail = b.children[0].head
				#b.children[0].use_connect = True

def uniform_scale():
	for o in bpy.context.selected_objects:
		o.dimensions = [1, 1, 1]
		o.scale = [min(o.scale), min(o.scale), min(o.scale)]

def find_or_create_constraint(pb, con_type, name=None):
	""" Create a constraint on a bone if it doesn't exist yet. 
		If a constraint with the given type already exists, just return that.
		If a name was passed, also make sure the name matches before deeming it a match and returning it.
		pb: Must be a pose bone.
	"""
	for con in pb.constraints:
		if con.type == con_type:
			if name:
				if con.name == name:
					return con
			else:
				return con
	con = pb.constraints.new(type=con_type)
	if name:
		con.name = name
	return con

def bone_search(armature, search=None, start=None, end=None, edit_bone=False, must_be_selected=True) -> List[bpy.types.Bone or bpy.types.EditBone]:
	"""Return a list of bones that match a search criteria.
	"search", "start" and "end" params are mutually exclusive, only first one passed will be used.
	"""
	bone_list = []
	if edit_bone:
		bone_list = armature.data.edit_bones
	else:
		bone_list = armature.pose.bones
	
	matching_bones = []
	if search:
		for b in bone_list:
			if search in b.name:
				if must_be_selected:
					if edit_bone:
						if b.select:
							matching_bones.append(b)
					else:
						if b.bone.select:
							matching_bones.append(b)
				else:
					matching_bones.append(b)
	elif start:
		for b in matching_bones:
			if not b.name.startswith(start):
				matching_bones.remove(b)
	elif end:
		for b in matching_bones:
			if not b.name.endswith(end):
				matching_bones.remove(b)
	else:
		assert False, "Nothing passed."
	
	return matching_bones

def find_nearby_edit_bones(armature, search_co, dist=0.0005, search_bones=None) -> List[bpy.types.EditBone]:
	"""
	Bruteforce search for bones that are within a given distance of the given coordinates.
	ebones: Only search in these bones.
	"""

	assert armature.mode=='EDIT'
	ret = []
	if not search_bones:
		search_bones = armature.data.edit_bones
	
	for eb in search_bones:
		if( (eb.head - search_co).length < dist):
			ret.append(eb)
	return ret


def copy_attributes(from_thing, to_thing, skip=[""], recursive=False):
	"""Copy attributes from one thing to another.
	from_thing: Object to copy values from. (Only if the attribute already exists in to_thing)
	to_thing: Object to copy attributes into (No new attributes are created, only existing are changed).
	skip: List of attribute names in from_thing that should not be attempted to be copied.
	recursive: Copy iterable attributes recursively.
	"""
	
	#print("\nCOPYING FROM: " + str(from_thing))
	#print(".... TO: " + str(to_thing))
	
	bad_stuff = skip + ['active', 'bl_rna', 'error_location', 'error_rotation']
	for prop in dir(from_thing):
		if "__" in prop: continue
		if prop in bad_stuff: continue

		if hasattr(to_thing, prop):
			from_value = getattr(from_thing, prop)
			# Iterables should be copied recursively, except str.
			if recursive and type(from_value) != str:
				# NOTE: I think This will infinite loop if a CollectionProperty contains a reference to itself!
				warn = False
				try:
					# Determine if the property is iterable. Otherwise this throws TypeError.
					iter(from_value)

					to_value = getattr(to_thing, prop)
					# The thing we are copying to must therefore be an iterable as well. If this fails though, we should throw a warning.
					warn = True
					iter(to_value)
					count = min(len(to_value), len(from_value))
					for i in range(0, count):
						copy_attributes(from_value[i], to_value[i], skip, recursive)
				except TypeError: # Not iterable.
					if warn:
						print("WARNING: Could not copy attributes from iterable to non-iterable field: " + prop + 
							"\nFrom object: " + str(from_thing) + 
							"\nTo object: " + str(to_thing)
						)

			# Copy the attribute.
			try:
				setattr(to_thing, prop, from_value)
				#print(prop + ": " + str(from_value))
			except AttributeError:	# Read-Only properties throw AttributeError. We ignore silently, which is not great.
				continue

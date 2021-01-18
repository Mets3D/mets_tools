import bpy

# Collection of functions that are either used by other parts of the addon, or random code snippets that I wanted to include but aren't actually used.

class EnsureVisible:
	"""Ensure an object is visible, then reset it to how it was before."""

	def __init__(self, obj):
		""" Ensure an object is visible, and create this small object to manage that object's visibility-ensured-ness. """
		self.obj_name = obj.name
		self.obj_hide = obj.hide_get()
		self.obj_hide_viewport = obj.hide_viewport
		self.temp_coll = None

		space = bpy.context.area.spaces.active
		if hasattr(space, 'local_view') and space.local_view:
			bpy.ops.view3d.localview()

		if not obj.visible_get():
			obj.hide_set(False)
			obj.hide_viewport = False

		if not obj.visible_get():
			# If the object is still not visible, we need to move it to a visible collection. To not break other scripts though, we should restore the active collection afterwards.
			active_coll = bpy.context.collection

			coll_name = "temp_visible"
			temp_coll = bpy.data.collections.get(coll_name)
			if not temp_coll:
				temp_coll = bpy.data.collections.new(coll_name)
			if coll_name not in bpy.context.scene.collection.children:
				bpy.context.scene.collection.children.link(temp_coll)

			if obj.name not in temp_coll.objects:
				temp_coll.objects.link(obj)

			self.temp_coll = temp_coll

			set_active_collection(active_coll)

	def restore(self):
		"""Restore visibility settings to their original state."""
		obj = bpy.data.objects.get(self.obj_name)
		if not obj: return

		obj.hide_set(self.obj_hide)
		obj.hide_viewport = self.obj_hide_viewport

		# Remove object from temp collection
		if self.temp_coll and obj.name in self.temp_coll.objects:
			self.temp_coll.objects.unlink(obj)

			# Delete temp collection if it's empty now.
			if len(self.temp_coll.objects) == 0:
				bpy.data.collections.remove(self.temp_coll)
				self.temp_coll = None

def recursive_search_layer_collection(collName, layerColl=None) -> bpy.types.LayerCollection:
	# Recursivly transverse layer_collection for a particular name
	# This is the only way to set active collection as of 14-04-2020.
	if not layerColl:
		layerColl = bpy.context.view_layer.layer_collection

	found = None
	if (layerColl.name == collName):
		return layerColl
	for layer in layerColl.children:
		found = recursive_search_layer_collection(collName, layer)
		if found:
			return found

def set_active_collection(collection):
	layer_collection = recursive_search_layer_collection(collection.name)
	bpy.context.view_layer.active_layer_collection = layer_collection

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
	
def assign_object_and_material_ids(start=1):
	counter = start

	for o in bpy.context.selected_objects:
		if(o.type=='MESH'):
			o.pass_index = counter
			counter = counter + 1

	counter = start
	for m in bpy.data.materials:
		m.pass_index = counter
		counter = counter + 1

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

def find_or_create_bone(armature, bonename, select=True):
	assert armature.mode=='EDIT', "Armature must be in edit mode"

	bone = armature.data.edit_bones.get(bonename)
	if(not bone):
		bone = armature.data.edit_bones.new(bonename)
	bone.select = select
	return bone

def find_or_create_constraint(pb, ctype, name=None):
	""" Create a constraint on a bone if it doesn't exist yet. 
		If a constraint with the given type already exists, just return that.
		If a name was passed, also make sure the name matches before deeming it a match and returning it.
		pb: Must be a pose bone.
	"""
	for c in pb.constraints:
		if(c.type==ctype):
			if(name):
				if(c.name==name):
					return c
			else:
				return c
	c = pb.constraints.new(type=ctype)
	if(name):
		c.name = name
	return c

def bone_search(armature, search=None, start=None, end=None, edit_bone=False, selected=True):
	""" Convenience function to get iterables for our for loops. """ #TODO: Could use regex.
	bone_list = []
	if(edit_bone):
		bone_list = armature.data.edit_bones
	else:
		bone_list = armature.pose.bones
	
	filtered_list = []
	if(search):
		for b in bone_list:
			if search in b.name:
				if selected:
					if edit_bone:
						if b.select:
							filtered_list.append(b)
					else:
						if b.bone.select:
							filtered_list.append(b)
				else:
					filtered_list.append(b)
	elif(start):
		for b in filtered_list:
			if not b.name.startswith(start):
				filtered_list.remove(b)
	elif(end):
		for b in filtered_list:
			if not b.name.endswith(end):
				filtered_list.remove(b)
	else:
		assert False, "Nothing passed."
	
	return filtered_list

def find_nearby_bones(armature, search_co, dist=0.0005, ebones=None):
	""" Bruteforce search for bones that are within a given distance of the given coordinates. """
	""" Active object must be an armature. """	# TODO: Let armature be passed, maybe optionally. Do some assert sanity checks.
	""" ebones: Only search in these bones. """
	
	assert armature.mode=='EDIT'	# TODO: Could use data.bones instead so we don't have to be in edit mode?
	ret = []
	if not ebones:
		ebones = armature.data.edit_bones
	
	for eb in ebones:
		if( (eb.head - search_co).length < dist):
			ret.append(eb)
	return ret

def get_bone_chain(bone, ret=[]):
	""" Recursively build a list of the first children. 
		bone: Can be pose/data/edit bone, doesn't matter. """
	ret.append(bone)
	if(len(bone.children) > 0):
		return get_bone_chain(bone.children[0], ret)
	return ret

def flip_name(from_name, only=True, must_change=False):
	# based on BLI_string_flip_side_name in https://developer.blender.org/diffusion/B/browse/master/source/blender/blenlib/intern/string_utils.c
	# If only==True, only replace the first occurrence of a side identifier in the string, eg. "Left_Eyelid.L" would become "Right_Eyelid.L". With only==False, it would instead return "Right_Eyelid.R"
	# if must_change==True, raise an error if the string couldn't be flipped.

	l = len(from_name)	# Number of characters from left to right, that we still care about. At first we care about all of them.
	
	# Handling .### cases
	if("." in from_name):
		# Make sure there are only digits after the last period
		after_last_period = from_name.split(".")[-1]
		before_last_period = from_name.replace("."+after_last_period, "")
		all_digits = True
		for c in after_last_period:
			if( c not in "0123456789" ):
				all_digits = False
				break
		# If that is so, then we don't care about the characters after this last period.
		if(all_digits):
			l = len(before_last_period)
	
	new_name = from_name[:l]
	
	left = 				['left',  'Left',  'LEFT', 	'.l', 	  '.L', 		'_l', 				'_L',				'-l',	   '-L', 	'l.', 	   'L.',	'l_', 			 'L_', 			  'l-', 	'L-']
	right_placehold = 	['*rgt*', '*Rgt*', '*RGT*', '*dotl*', '*dotL*', 	'*underscorel*', 	'*underscoreL*', 	'*dashl*', '*dashL', '*ldot*', '*Ldot', '*lunderscore*', '*Lunderscore*', '*ldash*','*Ldash*']
	right = 			['right', 'Right', 'RIGHT', '.r', 	  '.R', 		'_r', 				'_R',				'-r',	   '-R', 	'r.', 	   'R.',	'r_', 			 'R_', 			  'r-', 	'R-']
	
	def flip_sides(list_from, list_to, new_name):
		for side_idx, side in enumerate(list_from):
			opp_side = list_to[side_idx]
			if(only):
				# Only look at prefix/suffix.
				if(new_name.startswith(side)):
					new_name = new_name[len(side):]+opp_side
					break
				elif(new_name.endswith(side)):
					new_name = new_name[:-len(side)]+opp_side
					break
			else:
				if("-" not in side and "_" not in side):	# When it comes to searching the middle of a string, sides must Strictly a full word or separated with . otherwise we would catch stuff like "_leg" and turn it into "_reg".
					# Replace all occurences and continue checking for keywords.
					new_name = new_name.replace(side, opp_side)
					continue
		return new_name
	
	new_name = flip_sides(left, right_placehold, new_name)
	new_name = flip_sides(right, left, new_name)
	new_name = flip_sides(right_placehold, right, new_name)
	
	# Re-add trailing digits (.###)
	new_name = new_name + from_name[l:]

	if(must_change):
		assert new_name != from_name, "Failed to flip string: " + from_name
	
	return new_name

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
		if(prop in bad_stuff): continue

		if(hasattr(to_thing, prop)):
			from_value = getattr(from_thing, prop)
			# Iterables should be copied recursively, except str.
			if recursive and type(from_value) not in [str]:
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
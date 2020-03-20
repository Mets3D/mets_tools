# Data Container and utilities for de-coupling bone creation and setup from BPY.
# Lets us easily create bones without having to worry about edit/pose mode.
import bpy
from .id import *
from mathutils import *
import copy
from ..layers import group_defs, set_layers

# Attributes that reference an actual bone ID. These should get special treatment, because we don't want to store said bone ID. 
# Ideally we would store a BoneInfo, but a string is allowed too(less safe).
bone_attribs = ['parent', 'bbone_custom_handle_start', 'bbone_custom_handle_end']

def get_defaults(contype, armature):
	"""Return my preferred defaults for each constraint type."""
	ret = {
		"target" : armature,
	 }

	if contype not in ['STRETCH_TO', 'ARMATURE', 'IK', 'DAMPED_TRACK']:
		if contype not in ['LIMIT_SCALE']:
			ret["target_space"] = 'LOCAL'
		ret["owner_space"] = 'LOCAL'

	if contype == 'STRETCH_TO':
		ret["use_bulge_min"] = True
		ret["use_bulge_max"] = True
	elif contype in ['COPY_LOCATION', 'COPY_SCALE']:
		ret["use_offset"] = True
	elif contype == 'COPY_ROTATION':
		ret["use_offset"] = True
		ret["mix_mode"] = 'BEFORE'
	elif contype in ['COPY_TRANSFORMS', 'ACTION']:
		ret["mix_mode"] = 'BEFORE'
	elif contype == 'LIMIT_SCALE':
		ret["min_x"] = 1
		ret["max_x"] = 1
		ret["min_y"] = 1
		ret["max_y"] = 1
		ret["min_z"] = 1
		ret["max_z"] = 1
		ret["use_transform_limit"] = True
	elif contype in ['LIMIT_LOCATION', 'LIMIT_ROTATION']:
		ret["use_transform_limit"] = True
	elif contype == 'IK':
		ret["chain_count"] = 2
		ret["pole_target"] = armature
	elif contype == 'ARMATURE':
		# Create two targets in armature constraints.
		ret["targets"] = [{"target" : armature}, {"target" : armature}]
	
	return ret

def setattr_safe(thing, key, value):
	try:
		setattr(thing, key, value)
	except:
		print("ERROR: Wrong type assignment: key:%s, type:%s, expected:%s"%(key, type(key), type(getattr(thing, key)) ) )

class BoneInfoContainer(ID):
	# TODO: implement __iter__ and such.
	def __init__(self, cloudrig):
		self.bones = []
		self.armature = cloudrig.obj
		self.defaults = cloudrig.defaults	# For overriding arbitrary properties' default values when creating bones in this container.
		self.scale = cloudrig.scale

	def find(self, name):
		"""Find a BoneInfo instance by name, return it if found."""
		for bd in self.bones:
			if(bd.name == name):
				return bd
		return None

	def bone(self, name="Bone", source=None, armature=None, overwrite=True, **kwargs):
		"""Define a bone and add it to the list of bones. If it already exists, return or re-define it depending on overwrite param."""

		bi = self.find(name)
		if bi and not overwrite: 
			return bi
		elif bi:
			self.bones.remove(bi)

		bi = BoneInfo(self, name, source, armature, **kwargs)
		self.bones.append(bi)
		return bi			

	def create_multiple_bones(self, armature, bones):
		"""This will only switch between modes twice, so it is the preferred way of creating bones."""
		assert armature.select_get() or bpy.context.view_layer.objects.active == armature, "Armature must be selected or active."
		
		org_mode = armature.mode

		bpy.ops.object.mode_set(mode='EDIT')
		# First we create all the bones.
		for bd in bones:
			edit_bone = find_or_create_bone(armature, bd.name)
		
		# Now that all the bones are created, loop over again to set the properties.
		for bd in bones:
			edit_bone = armature.data.edit_bones.get(bd.name)
			bd.write_edit_data(armature, edit_bone)

		# And finally a third time, after switching to pose mode, so we can add constraints.
		bpy.ops.object.mode_set(mode='POSE')
		for bd in bones:
			pose_bone = armature.pose.bones.get(bd.name)
			bd.write_pose_data(pose_bone)
		
		bpy.ops.object.mode_set(mode=org_mode)

	def make_real(self, armature, clear=True):
		self.create_multiple_bones(armature, self.bones)
		if clear:
			self.clear()
	
	def clear(self):
		self.bones = []

class BoneInfo(ID):
	"""Container of all info relating to a Bone."""
	def __init__(self, container, name="Bone", source=None, armature=None, **kwargs):
		""" 
		container: Need a reference to what BoneInfoContainer this BoneInfo belongs to.
		source:	Bone to take transforms from (head, tail, roll, bbone_x, bbone_z).
			NOTE: Ideally a source should always be specified, or bbone_x/z specified, otherwise blender will use the default 0.1, which can result in giant or tiny bones.
		kwargs: Allow setting arbitrary bone properties at initialization.
		"""
		
		self.container = container

		### The following dictionaries store pure information, never references to the real thing. ###
		# PoseBone custom properties.
		self.custom_props = {}
		# EditBone custom properties.
		self.custom_props_edit = {}
		# data_path:Driver dictionary, where data_path is from the bone. Only for drivers that are directly on a bone property! Not a sub-ID like constraints.
		self.drivers = {}
		self.bone_drivers = {}

		# List of (Type, attribs{}) tuples where attribs{} is a dictionary with the attributes of the constraint.
		# "drivers" is a valid attribute which expects the same content as self.drivers, and it holds the constraints for constraint properties.
		# I'm too lazy to implement a container for every constraint type, or even a universal one, but maybe I should.
		self.constraints = []
		
		self.name = name
		self.head = Vector((0,0,0))
		self.tail = Vector((0,1,0))
		self.roll = 0
		self.layers = [False]*32	# NOTE: If no layers are enabled, Blender will force layers[0]=True without warning.
		self.rotation_mode = 'QUATERNION'
		self.hide_select = False
		self.hide = False

		### Properties that are shared between pose and edit mode.
		self.bbone_width = 0.1
		self._bbone_x = 0.1	# These get special treatment to avoid having to put self.scale everywhere.
		self._bbone_z = 0.1
		self.bbone_segments = 1
		self.bbone_handle_type_start = "AUTO"
		self.bbone_handle_type_end = "AUTO"
		self.bbone_custom_handle_start = None	# Bone name only!
		self.bbone_custom_handle_end = None		# Bone name only!

		### Edit Mode Only
		# Note that for these bbone properties, we are referring only to edit bone versions of the values.
		self.bbone_curveinx = 0
		self.bbone_curveiny = 0
		self.bbone_curveoutx = 0
		self.bbone_curveouty = 0
		self.bbone_easein = 1
		self.bbone_easeout = 1
		self.bbone_scaleinx = 1
		self.bbone_scaleiny = 1
		self.bbone_scaleoutx = 1
		self.bbone_scaleouty = 1

		self.parent = None	# Bone name only!

		### Pose Mode Only
		self.bone_group = ""
		self.custom_shape = None   # Object ID?
		self.custom_shape_scale = 1.0
		self.use_custom_shape_bone_size = False
		self.use_endroll_as_inroll = False
		self.use_connect = False
		self.use_deform = False
		self.use_inherit_rotation = True
		self.use_inherit_scale = True
		self.use_local_location = True
		self.use_relative_parent = False
		self.lock_location = [False, False, False]
		self.lock_rotation = [False, False, False]
		self.lock_rotation_w = False
		self.lock_scale = [False, False, False]

		self.envelope_distance = 0.25
		self.envelope_weight = 1.0
		self.use_envelope_multiply = False
		self.head_radius = 0.1
		self.tail_radius = 0.1

		self.custom_shape_transform = None # Bone name
		
		# Apply property values from container's defaults
		for key, value in self.container.defaults.items():
			setattr_safe(self, key, value)

		if source:
			self.head = copy.copy(source.head)
			self.tail = copy.copy(source.tail)
			self.roll = source.roll
			self.envelope_distance = source.envelope_distance
			self.envelope_weight = source.envelope_weight
			self.use_envelope_multiply = source.use_envelope_multiply
			self.head_radius = source.head_radius
			self.tail_radius = source.tail_radius
			if type(source)==BoneInfo:
				self.bbone_width = source.bbone_width
			else:
				self._bbone_x = source.bbone_x
				self._bbone_z = source.bbone_z
			if source.parent:
				if type(source)==bpy.types.EditBone:
					self.parent = source.parent.name
				else:
					self.parent = source.parent 

		# Apply property values from arbitrary keyword arguments if any were passed.
		for key, value in kwargs.items():
			setattr_safe(self, key, value)

	def __str__(self):
		return self.name

	@property
	def bbone_width(self):
		return self._bbone_x / self.container.scale

	@bbone_width.setter
	def bbone_width(self, value):
		self._bbone_x = value * self.container.scale
		self._bbone_z = value * self.container.scale
		self.envelope_distance = value * self.container.scale
		self.head_radius = value * self.container.scale
		self.tail_radius = value * self.container.scale

	@property
	def vec(self):
		"""Vector pointing from head to tail."""
		return self.tail-self.head

	def scale_width(self, value):
		"""Set bbone width relative to current."""
		self.bbone_width *= value

	def scale_length(self, value):
		"""Set bone length relative to its current length."""
		self.tail = self.head + self.vec * value

	@property
	def length(self):
		return (self.tail-self.head).length

	@length.setter
	def length(self, value):
		assert value > 0, "Length cannot be 0!"
		self.tail = self.head + self.vec.normalized() * value

	def flatten(self):
		"""Make bone world-aligned on its longest axis."""
		vec = self.tail - self.head
		maxabs = 0
		max_index = 0
		for i, x in enumerate(vec):
			if abs(x) > maxabs:
				maxabs = abs(x)
				max_index = i

		for i, co in enumerate(self.tail):
			if i != max_index:
				self.tail[i] = self.head[i]
		self.roll = 0
	
	@property
	def center(self):
		return self.head + self.vec/2

	def set_layers(self, layerlist, additive=False):
		# We can use the same code for setting bone layers as we do for setting the armature's active layers.
		set_layers(self, layerlist, additive)

	def put(self, loc, length=None, width=None, scale_length=None, scale_width=None):
		offset = loc-self.head
		self.head = loc
		self.tail = loc+offset
		
		if length:
			self.length=length
		if width:
			self.bbone_width = width
		if scale_length:
			self.scale_length(scale_length)
		if scale_width:
			self.scale_width(scale_width)
	
	def copy_info(self, bone_info):
		"""Called from __init__ to initialize using existing BoneInfo."""
		my_dict = self.__dict__
		skip = ["name"]
		for attr in my_dict.keys():
			if attr in skip: continue
			setattr_safe( self, attr, getattr(bone_info, copy.deepcopy(attr)) )

	def copy_bone(self, armature, edit_bone):
		"""Called from __init__ to initialize using existing bone."""
		my_dict = self.__dict__
		skip = ['name', 'constraints', 'bl_rna', 'type', 'rna_type', 'error_location', 'error_rotation', 'is_proxy_local', 'is_valid', 'children']
		
		for key, value in my_dict.items():
			if key in skip: continue
			if(hasattr(edit_bone, key)):
				target_bone = getattr(edit_bone, key)
				if key in bone_attribs and target_bone:
					value = target_bone.name
				else:
					# EDIT BONE PROPERTIES MUST BE DEEPCOPIED SO THEY AREN'T DESTROYED WHEN LEAVEING EDIT MODE. OTHERWISE IT FAILS SILENTLY!
					if key in ['layers']:
						value = list(getattr(edit_bone, key)[:])
					else:
						value = copy.deepcopy(getattr(edit_bone, key))
				setattr_safe(self, key, value)
				skip.append(key)

		# Read Pose Bone data (only if armature was passed)
		if not armature: return
		pose_bone = armature.pose.bones.get(edit_bone.name)
		if not pose_bone: return

		for attr in my_dict.keys():
			if attr in skip: continue

			if hasattr(pose_bone, attr):
				setattr_safe( self, attr, getattr(pose_bone, attr) )

		# Read Constraint data
		for c in pose_bone.constraints:
			constraint_data = (c.type, {})
			# TODO: Why are we using dir() here instead of __dict__?
			for attr in dir(c):
				if "__" in attr: continue
				if attr in skip: continue
				constraint_data[1][attr] = getattr(c, attr)

			self.constraints.append(constraint_data)

	def disown(self, new_parent):
		""" Parent all children of this bone to a new parent. """
		for b in self.container.bones:
			if b.parent==self or b.parent==self.name:
				b.parent = new_parent

	def add_constraint(self, armature, contype, true_defaults=False, prepend=False, **kwargs):
		"""Add a constraint to this bone.
		contype: Type of constraint, eg. 'STRETCH_TO'.
		props: Dictionary of properties and values.
		true_defaults: When False, we use a set of arbitrary default values that I consider better than Blender's defaults.
		"""
		props = kwargs
		# Override defaults with better ones.
		if not true_defaults:
			new_props = get_defaults(contype, armature)
			for key, value in kwargs.items():
				new_props[key] = value
			props = new_props
		
		if prepend:
			self.constraints.insert(0, (contype, props))
		else:
			self.constraints.append((contype, props))
		return props

	def clear_constraints(self):
		self.constraints = []

	def write_edit_data(self, armature, edit_bone):
		"""Write relevant data into an EditBone."""
		assert armature.mode == 'EDIT', "Armature must be in Edit Mode when writing bone data"

		# Check for 0-length bones. Warn and skip if so.
		if (self.head - self.tail).length == 0:
			print("WARNING: Skpping 0-length bone: " + self.name)
			return
		
		# Edit Bone Properties.
		for key, value in self.__dict__.items():
			if(hasattr(edit_bone, key)):
				if key == 'use_connect': continue	# TODO why does this break everything?
				if key in bone_attribs:
					real_bone = None
					if(type(value) == str):
						real_bone = armature.data.edit_bones.get(value)
					elif(type(value) == BoneInfo):
						real_bone = value.get_real(armature)
						if not real_bone:
							print("WARNING: Parent %s not found for bone: %s" % (self.parent.name, self.name))
					elif value != None:
						# TODO: Maybe this should be raised when assigning the parent to the variable in the first place(via @property setter/getter)
						assert False, "ERROR: Unsupported parent type: " + str(type(value))
					
					setattr_safe(edit_bone, key, real_bone)
				else:
					# We don't want Blender to destroy my object references(particularly vectors) when leaving edit mode, so pass in a deepcopy instead.
					setattr_safe(edit_bone, key, copy.deepcopy(value))
					
		# Custom Properties.
		for key, prop in self.custom_props_edit.items():
			prop.make_real(edit_bone)
		
		# Without this, ORG- bones' Copy Transforms constraints can't work properly.
		edit_bone.use_connect = False

	def write_pose_data(self, pose_bone):
		"""Write relevant data into a PoseBone."""
		armature = pose_bone.id_data

		assert armature.mode != 'EDIT', "Armature cannot be in Edit Mode when writing pose data"

		data_bone = armature.data.bones.get(pose_bone.name)

		my_dict = self.__dict__

		# Bone group
		if self.bone_group!="":
			bone_group = armature.pose.bone_groups.get(self.bone_group)

			# If the bone group doesn't already exist, warn about it. It should've been created in cloud_utils.init_bone_groups().
			if not bone_group:
				print("Warning: Could not find bone group %s for bone %s." %(self.bone_group, self.name))
			else:
				pose_bone.bone_group = bone_group

				# Set layers if specified in the group definition.
				if self.bone_group in group_defs:
					group_def = group_defs[self.bone_group]
					if 'layers' in group_def:
						self.set_layers(group_def['layers'])
						pose_bone.bone.layers = self.layers[:]

		# Pose bone data.
		skip = ['constraints', 'head', 'tail', 'parent', 'children', 'length', 'use_connect', 'bone_group']
		for attr in my_dict.keys():
			value = my_dict[attr]
			if(hasattr(pose_bone, attr)):
				if attr in skip: continue
				if 'bbone' in attr: continue
				if(attr in ['custom_shape_transform'] and value):
					value = armature.pose.bones.get(value.name)
				setattr_safe(pose_bone, attr, value)
		
		# Constraints.
		for cd in self.constraints:
			con_type = cd[0]
			cinfo = cd[1]
			c = pose_bone.constraints.new(con_type)
			if 'name' in cinfo:
				c.name = cinfo['name'] 
			#c = find_or_create_constraint(pose_bone, con_type, name)
			for key, value in cinfo.items():
				if con_type == 'ARMATURE' and key=='targets':
					# Armature constraint targets need special treatment. D'oh!
					# We assume the value of "targets" is a list of dictionaries describing a target.
					for tinfo in value:	# For each of those dictionaries
						target = c.targets.new()	# Create a target
						# Set armature as the target by default so we don't have to always specify it.
						target.target = armature
						# Copy just these three values.
						copy = ['weight', 'target', 'subtarget']
						for prop in copy:
							if prop in tinfo:
								setattr_safe(target, prop, tinfo[prop])
				elif(hasattr(c, key)):
					setattr_safe(c, key, value)
		
		# Custom Properties.
		for key, prop in self.custom_props.items():
			prop.make_real(pose_bone)
		
		# Pose Bone Property Drivers.
		for path, d in self.drivers.items():
			data_path = 'pose.bones["%s"].%s' %(pose_bone.name, path)
			driv = d.make_real(pose_bone.id_data, data_path)
	
		# Data Bone Property Drivers.
		for path, d in self.bone_drivers.items():
			#HACK: If we want to add drivers to bone properties that are shared between pose and edit mode, they aren't stored under armature.pose.bones[0].property but instead armature.bones[0].property... The entire way we handle drivers should be scrapped tbh. :P
			# But scrapping that requires scrapping the way we handle bones, so... just keep making it work.
			data_path = 'bones["%s"].%s' %(pose_bone.name, path)
			driv = d.make_real(pose_bone.id_data.data, data_path)
			
	def make_real(self, armature):
		# Create a single bone and its constraints. Needs to switch between object modes.
		# It is preferred to create bones in bulk via BoneDataContainer.create_all_bones().
		armature.select_set(True)
		bpy.context.view_layer.objects.active = armature
		org_mode = armature.mode

		bpy.ops.object.mode_set(mode='EDIT')
		edit_bone = find_or_create_bone(armature, self.name)
		self.write_edit_data(edit_bone)

		bpy.ops.object.mode_set(mode='POSE')
		pose_bone = armature.pose.bones.get(self.name)
		self.write_pose_data(pose_bone)

		bpy.ops.object.mode_set(mode=org_mode)
	
	def get_real(self, armature):
		"""If a bone with the name in this BoneInfo exists in the passed armature, return it."""
		if armature.mode == 'EDIT':
			return armature.data.edit_bones.get(self.name)
		else:
			return armature.pose.bones.get(self.name)
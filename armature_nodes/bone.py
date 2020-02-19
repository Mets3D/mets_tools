# Data Container and utilities for de-coupling bone creation and setup from BPY.
# Lets us easily create bones without having to worry about edit/pose mode.
import bpy
from .id import *
from mathutils import *
from mets_tools.utils import *
import copy

# Attributes that reference an actual bone ID. These should get special treatment, because we don't want to store said bone ID. 
# Ideally we would store a BoneInfo, but a string is allowed too(less safe).
bone_attribs = ['parent', 'bbone_custom_handle_start', 'bbone_custom_handle_end']

def get_defaults(contype, armature):
	"""Return my preferred defaults for each constraint type."""
	ret = {
		"target_space" : 'LOCAL',
		"owner_space" : 'LOCAL',
		"target" : armature,
	 }

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

class BoneInfoContainer(ID):
	# TODO: implement __iter__ and such.
	def __init__(self, defaults={}):
		# TODO: Bone layers and groups go here too I think? Actually, maybe not. We need an even higher level place to store those, so that it's associated with the cloudrig featureset.
		self.bones = []
		self.defaults = defaults	# For overriding arbitrary properties' default values when creating bones in this container.

	def find(self, name):
		"""Find a BoneInfo instance by name, if it exists."""
		for bd in self.bones:
			if(bd.name == name):
				return bd
		return None
	
	def new(self, name="Bone", source=None, armature=None, **kwargs):
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
			bd.write_pose_data(armature, pose_bone)
		
		bpy.ops.object.mode_set(mode=org_mode)

	def make_real(self, armature, clear=True):
		self.create_multiple_bones(armature, self.bones)
		if clear:
			self.clear()
	
	def clear(self):
		self.bones = []

class BoneInfo(ID):
	"""Container of all info relating to a Bone."""
	def __init__(self, container, name="Bone", source=None, armature=None, only_transform=False, **kwargs):
		self.container = container # Need a reference to what BoneInfoContainer this BoneInfo belongs to.
		
		# All of the following store abstractions, not the real thing.
		self.custom_props = {}		# PoseBone custom properties.
		self.custom_props_edit = {}	# EditBone custom properties.
		self.drivers = {}
		self.constraints = []	# List of (Type, attribs{}) tuples where attribs{} is a dictionary with the attributes of the constraint. I'm too lazy to implement a container for every constraint type...
		
		# TODO: Let us specify Custom Properties, for both EditBone and PoseBone.
		self.name = name
		self.head = Vector((0,0,0))
		self.tail = Vector((0,1,0))
		self.roll = 0
		self.rotation_mode = 'QUATERNION'
		self.bbone_curveinx = 0
		self.bbone_curveiny = 0
		self.bbone_curveoutx = 0
		self.bbone_curveouty = 0
		self.bbone_handle_type_start = "AUTO"
		self.bbone_handle_type_end = "AUTO"
		self.bbone_easein = 0
		self.bbone_easeout = 0
		self.bbone_scaleinx = 0
		self.bbone_scaleiny = 0
		self.bbone_scaleoutx = 0
		self.bbone_scaleouty = 0
		self.segments = 1
		self.bbone_x = 0.1
		self.bbone_z = 0.1
		self.bone_group = None
		self.custom_shape = None   # Object ID?
		self.custom_shape_scale = 1.0
		self.use_custom_shape_bone_size = False
		self.use_endroll_as_inroll = False
		# self.use_connect = False
		self.use_deform = False
		self.use_inherit_rotation = True
		self.use_inherit_scale = True
		self.use_local_location = True
		self.use_envelope_multiply = False
		self.use_relative_parent = False

		# We don't want to store a real Bone ID because we want to be able to set the parent before the parent was really created. So this is either a String or a BoneInfo instance.
		# TODO: These should be handled uniformally.
		# TODO: Maybe they should be forced to be BoneInfo instance, and don't allow str. Seems pointless and unneccessarily non-foolproof.
		self.custom_shape_transform = None # Bone name
		self.parent = None
		self.bbone_custom_handle_start = None
		self.bbone_custom_handle_end = None
		
		if only_transform:
			assert source, "If only_transform==True, source cannot be None!"
			self.head=source.head
			self.tail=source.tail
			self.roll=source.roll
			self.bbone_x=source.bbone_x
			self.bbone_z=source.bbone_z
		else:
			if(source and type(source)==BoneInfo):
				self.copy_info(source)
			elif(source and type(source)==bpy.types.EditBone):
				self.copy_bone(armature, source)
		
		# Override copied properties with arbitrary keyword arguments if any were passed.
		for key, value in kwargs.items():
			setattr(self, key, value)

	@property
	def bbone_width(self):
		return self.bbone_x

	@bbone_width.setter
	def bbone_width(self, value):
		self.bbone_x = value
		self.bbone_z = value

	@property
	def vec(self):
		"""Vector pointing from head to tail."""
		return self.tail-self.head

	@property
	def length(self):
		return (self.tail-self.head).size

	@property
	def center(self):
		return self.head + self.vec/2

	@length.setter
	def length(self, value):
		assert value > 0, "Length cannot be 0!"
		self.tail = self.head + self.vec.normalized() * value

	def put(self, loc, length=None, width=None):
		offset = loc-self.head
		self.head = loc
		self.tail = loc+offset
		
		if length:
			self.length=length
		
		if width:
			self.bbone_width = width
	
	def copy_info(self, bone_info):
		"""Called from __init__ to initialize using existing BoneInfo."""
		my_dict = self.__dict__
		skip = ["name"]
		for attr in my_dict.keys():
			if attr in skip: continue
			setattr( self, attr, getattr(bone_info, copy.deepcopy(attr)) )

	def copy_bone(self, armature, edit_bone):
		"""Called from __init__ to initialize using existing bone."""
		my_dict = self.__dict__
		skip = ['name', 'constraints', 'bl_rna', 'type', 'rna_type', 'error_location', 'error_rotation', 'is_proxy_local', 'is_valid']
		
		for attr in my_dict.keys():
			if attr in skip: continue
			if(hasattr(edit_bone, attr)):
				value = getattr(edit_bone, attr)
				# EDIT BONE CLASSES CANNOT BE SAVED SO EASILY. THEY NEED TO BE DEEPCOPIED. OTHERWISE THEY ARE DESTROYED WHEN RIGIFY LEAVES EDIT MODE. FURTHER ACCESS TO THEM SHOULD, IDEALLY, CAUSE A CRASH. BUT SOMETIMES IT JUST SO HAPPENS TO LAND CONSISTENTLY ON SOME OTHER VECTOR'S MEMORY ADDRESS, THEREFORE FAILING COMPLETELY SILENTLY. NEVER SAVE REFERENCES TO EDIT BONE PROPERTIES!
				if attr in bone_attribs and value:
					# TODO: Instead of just saving the name as a string, we should check if our BoneInfoContainer has a bone with this name, and if not, even go as far as to create it.
					# Look for the BoneInfo object corresponding to this bone in our BoneInfoContainer.
					bone_info = self.container.find(value.name)
					if not bone_info:
						# If it doesn't exist, create it.
						bone_info = self.container.new(name=value.name, armature=armature, source=value)
					value = bone_info
				else:
					value = copy.deepcopy(getattr(edit_bone, attr))
				setattr(self, attr, value)
				skip.append(attr)

		# Read Pose Bone data (only if armature was passed)
		if not armature: return
		pose_bone = armature.pose.bones.get(edit_bone.name)
		if not pose_bone: return

		for attr in my_dict.keys():
			if attr in skip: continue

			if hasattr(pose_bone, attr):
				setattr( self, attr, getattr(pose_bone, attr) )

		# Read Constraint data
		for c in pose_bone.constraints:
			constraint_data = (c.type, {})
			# TODO: Why are we using dir() here instead of __dict__?
			for attr in dir(c):
				if "__" in attr: continue
				if attr in skip: continue
				constraint_data[1][attr] = getattr(c, attr)

			self.constraints.append(constraint_data)

	def add_constraint(self, contype, props={}, armature=None, true_defaults=False):
		"""Add a constraint to this bone.
		contype: Type of constraint, eg. 'STRETCH_TO'.
		props: Dictionary of properties and values.
		true_defaults: When False, we use a set of arbitrary default values that I consider better than Blender's defaults.
		"""
		
		# Override defaults with better ones.
		if not true_defaults:
			new_props = get_defaults(contype)
			for k in props.keys():
				new_props[k] = props[k]
			props = new_props
		
		self.constraints.append((contype, props))

	def clear_constraints(self):
		self.constraints = []

	def write_edit_data(self, armature, edit_bone):
		"""Write relevant data into an EditBone."""
		assert armature.mode == 'EDIT', "Armature must be in Edit Mode when writing bone data"
		
		print("HELLO??")
		print(edit_bone.name)

		# Check for 0-length bones. Warn and skip if so.
		if (self.head - self.tail).length == 0:
			print("WARNING: Skpping 0-length bone: " + self.name)
			return

		# Edit Bone Properties.
		my_dict = self.__dict__
		for attr in my_dict.keys():
			if(hasattr(edit_bone, attr)):
				if(attr in bone_attribs):
					self_value = self.__dict__[attr]
					if not self_value: continue

					real_bone = None
					if(type(self_value) == str):
						real_bone = armature.data.edit_bones.get(self_value)
					elif(type(self_value) == BoneInfo):
						real_bone = self_value.get_real(armature)
						if not real_bone:
							print("WARNING: Parent %s not found for bone: %s" % (self.parent.name, self.name))
					else:
						# TODO: Maybe this should be raised when assigning the parent to the variable in the first place(via @property setter/getter)
						assert False, "ERROR: Unsupported parent type: " + str(type(self_value))
					
					if(real_bone):
						setattr(edit_bone, attr, real_bone)
				else:
					# We don't want Blender to destroy my object references(particularly vectors) when leaving edit mode, so pass in a deepcopy instead.
					setattr(edit_bone, attr, copy.deepcopy(my_dict[attr]))
		
		# Custom Properties.
		for key, prop in self.custom_props_edit.items():
			print("Edit bone custom property on bone: " + edit_bone.name)
			print(key)
			print(prop)
			print(prop.default)
			prop.make_real(edit_bone)

	def write_pose_data(self, armature, pose_bone):
		"""Write relevant data into a PoseBone and its (Data)Bone."""
		assert armature.mode != 'EDIT', "Armature cannot be in Edit Mode when writing pose data"

		data_bone = armature.data.bones.get(pose_bone.name)

		my_dict = self.__dict__

		# Pose bone data.
		skip = ['constraints', 'head', 'tail', 'parent', 'length', 'use_connect']
		for attr in my_dict.keys():
			value = my_dict[attr]
			if(hasattr(pose_bone, attr)):
				if attr in skip: continue
				if 'bbone' in attr: continue
				if(attr in ['custom_shape_transform'] and value):
					value = armature.pose.bones.get(value.name)
				setattr(pose_bone, attr, value)

		# Data bone data.
		for attr in my_dict.keys():
			if(hasattr(data_bone, attr)):
				value = my_dict[attr]
				if attr in skip: continue
				# TODO: It should be more explicitly defined what properties we want to be setting here exactly, because I don't even know. Same for Pose and Edit data.
				if attr in ['bbone_custom_handle_start', 'bbone_custom_handle_end']:
					if(type(value)==str):
						value = armature.data.bones.get(value)
				setattr(data_bone, attr, value)
		
		# Constraints.
		for cd in self.constraints:
			name = cd[1]['name'] if 'name' in cd[1] else None
			c = find_or_create_constraint(pose_bone, cd[0], name)
			for attr in cd[1].keys():
				if(hasattr(c, attr)):
					setattr(c, attr, cd[1][attr])
		
		# Custom Properties.
		for key, prop in self.custom_props.items():
			prop.make_real(pose_bone)
	
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
		self.write_pose_data(armature, pose_bone)

		bpy.ops.object.mode_set(mode=org_mode)
	
	def get_real(self, armature):
		if armature.mode == 'EDIT':
			return armature.data.edit_bones.get(self.name)
		else:
			return armature.pose.bones.get(self.name)
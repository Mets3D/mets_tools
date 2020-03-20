import bpy
from .id import *
from .. import utils
import copy

# Data Container and utilities for de-coupling driver management from BPY.
# Lets us easily apply similar drivers to many properties.

class Driver(ID):
	def __init__(self, source=None, **kwargs):
		super().__init__()
		self.expression = "var"
		self.variables = []
		self.use_self = False
		self.type = ['SCRIPTED', 'AVERAGE', 'SUM', 'MIN', 'MAX'][0]
		self.last_data_path = ""	# Data path of the Blender Driver that this Driver object was last applied to.

		if source:
			if type(source) == bpy.types.FCurve:
				# Allow passing FCurves?
				source = source.driver
			if type(source) == bpy.types.Driver:
				# If a Blender driver object is passed, read its data into this instance.	# TODO: How could we just do this with a recursive copy_attributes, without fucking up the list types?
				utils.copy_attributes(source, self, skip=["variables"])
				for i_v in range(len(source.variables)):
					bpy_v = source.variables[i_v]
					v = DriverVariable()
					self.variables.append(v)
					utils.copy_attributes(bpy_v, v, skip=["targets"])
					for i_t in range(len(bpy_v.targets)):
						utils.copy_attributes(bpy_v.targets[i_t], v.targets[i_t])
		
		# Apply property values from arbitrary keyword arguments if any were passed.
		for key, value in kwargs.items():
			setattr(self, key, value)

	def clone(self):
		"""Return a copy of this Driver description."""
		new = Driver()
		new.expression = self.expression
		new.use_self = self.use_self
		new.type = self.type
		for var in self.variables:
			new.variables.append(var.clone())
		return new

	# TODO: Isn't this redundant? I think there's a builtin find() function for this.
	@staticmethod
	def get_driver_by_data_path(obj, data_path):
		if not obj.animation_data: return

		for d in obj.animation_data.drivers:
			if(d.data_path == data_path):
				return d.driver

	def flip(self, targets=False, subtargets=True, paths=True):
		"""Mirror this driver around the X axis.
		targets: Attempt to flip target object names.
		subtargets: Attempt to flip subtarget names(bones, vertex groups)
		paths: Attempt to flip Single Property data paths.
		"""
		#TODO: Pass as parameter whatever information is required in order to do this correctly. Try to keep parameters in this function specific to the driver itself(eg. don't pass bone orientation. That stuff should be figured out outside of this, and something conclusive passed into this that relates directly to the driver and its variables.)

		# Flip variable target bones.
		pass

	def make_var(self, name="var"):
		"""Shorthand for creating a variable with a name and add it to the driver. 
		You can always add variable definitions to the driver's variable list directly."""
		new_var = DriverVariable(name)
		self.variables.append(new_var)
		return new_var

	def make_real(self, target, data_path, index=-1):
		"""Add this driver to a property."""
		assert hasattr(target, "driver_add"), "Target does not have driver_add(): " + str(target)
		driver_removed = target.driver_remove(data_path, index)
		# index 0 is not allowed to be passed...
		BPY_fcurve = None
		if index == 0:
			BPY_fcurve = target.driver_add(data_path)
		else:
			BPY_fcurve = target.driver_add(data_path, index)
		self.last_data_path = BPY_fcurve.data_path
		BPY_driver = BPY_fcurve.driver

		BPY_driver.expression = self.expression
		BPY_driver.use_self = self.use_self
		BPY_driver.type = self.type

		for v in self.variables:
			v.make_real(BPY_driver)
		
		return BPY_driver
	
	def __str__(self):
		return "Driver Object last applied to: " + self.last_data_path

class DriverVariable(ID):
	def __init__(self, name="var"):
		super().__init__()
		self.targets = [DriverVariableTarget(), DriverVariableTarget()]
		self.name = name
		self.type = ['SINGLE_PROP', 'TRANSFORMS', 'ROTATION_DIFF', 'LOC_DIFF'][0]
	
	def clone(self):
		new = DriverVariable(self.name)
		new.type = self.type
		for i, t in enumerate(self.targets):
			#I guess let's clone targets here instead of making them copy themselves, because we should never create targets outside of the __init__
			new.targets[i].id_type = self.targets[i].id_type
			new.targets[i].id = self.targets[i].id
			new.targets[i].bone_target = self.targets[i].bone_target
			new.targets[i].data_path = self.targets[i].data_path
			new.targets[i].transform_type = self.targets[i].transform_type
			new.targets[i].transform_space = self.targets[i].transform_space
			new.targets[i].rotation_mode = self.targets[i].rotation_mode
		return new
	
	def make_real(self, BPY_driver):
		"""Add this variable to a driver."""
		BPY_d_var = BPY_driver.variables.new()
		super().make_real(BPY_d_var)
		self.targets[0].make_real(BPY_d_var, 0)
		if self.type in ['ROTATION_DIFF', 'LOC_DIFF']:
			self.targets[1].make_real(BPY_d_var, 1)

class DriverVariableTarget(ID):
	def __init__(self):
		super().__init__()
		self.id_type = 'OBJECT'
		self.id = None
		self.bone_target = ""
		self.data_path = ""
		self.transform_type = 'ROT_X'
		self.transform_space = 'LOCAL_SPACE'
		self.rotation_mode = 'AUTO'

	def make_real(self, BPY_variable, index):
		"""Set this target on a variable."""
		BPY_target = BPY_variable.targets[index]
		if BPY_variable.type == 'SINGLE_PROP':
			BPY_target.id_type = self.id_type
		BPY_target.id = self.id
		BPY_target.bone_target = self.bone_target
		BPY_target.data_path = self.data_path
		BPY_target.transform_type = self.transform_type
		BPY_target.transform_space = self.transform_space
		#BPY_target.rotation_mode = self.rotaion_mode
		return

		skip = []
		if BPY_variable.type != 'SINGLE_PROP':
			skip = ['id_type']
		if len(BPY_variable.targets) > index:
			super().make_real(BPY_variable.targets[index], skip)
		else:
			pass

	def __deepcopy__(self, memo):
		# We want to halt deepcopies here, since we don't store any compound objects beside a reference to an ID, which we cannot deepcopy.
		return copy.copy(self)

	def __str__(self):
		return "DriverVariableTarget " + str(self.id) + " " + self.bone_target + " " + self.transform_type


def copy_drivers(obj_from, obj_to):
	"""Copy all drivers from one object to another."""
	if not obj_from.animation_data: return

	# TODO: I guess we would also expect to copy things that are stored in obj_from.data to obj_to.data.
	for d in obj_from.animation_data.drivers:
		copy_driver(d, obj_to, d.data_path, d.array_index)
	for d in obj_from.data.animation_data.drivers:
		copy_driver(d, obj_to.data, d.data_path, d.array_index)

def copy_driver(BPY_driver, obj, data_path, index=-1):
	"""Copy a driver to some other data path."""
	driver = Driver(BPY_driver)
	driver.make_real(obj, data_path, index)
from rna_prop_ui import rna_idprop_ui_create
from .driver import DriverVariable
import bpy

class CustomProp:
	def __init__(self, name, *, default, _min=0.0, _max=1.0, soft_min=None, soft_max=None, description=None, overridable=True, subtype=True):
		self.name = name
		self.default = default
		self.min = _min
		self.max = _max
		self.soft_min = soft_min
		self.soft_max = soft_max
		self.description = description
		self.overridable = overridable
		self.subtype = subtype

	def make_real(self, owner):
		""" Apply this custom property to a real Blender ID, such as an object or a bone. """
		return rna_idprop_ui_create(
			owner, 
			self.name, 
			default = self.default,
			min = self.min, 
			max = self.max, 
			soft_min = self.soft_min, 
			soft_max = self.soft_max,
			description = self.description,
			overridable = self.overridable,
			subtype = self.subtype
		)
	
	def as_driver_variable(self, owner, id_type='OBJECT'):
		"""Convert this custom property definition into a driver variable definition, assuming this custom property was already applied to the given owner.."""
		var = DriverVariable(self.name)
		var.type = 'SINGLE_PROP'

		if type(owner) != bpy.types.Object and id_type != 'OBJECT':
			# TODO: This doesn't catch nearly all bad cases, we're just assuming here that we won't be making drivers to non-OBJECT id_types. To support that, we'd need a mapping of what id_type enum corresponds to what bpy.type.
			print("ERROR: Failed to convert custom property into driver variable description, wrong id_type: %s for owner: %s" % (id_type, str(owner)))
			return
		target = var.targets[0]
		target.id_type = id_type
		target.id = owner.id_data
		target.data_path = owner.path_from_id() + '["%s"]' % self.name

		return var

def copy_custom_properties(from_obj, keys, to_obj, safe=True):
	rna_ui = from_obj['_RNA_UI'].to_dict()
	for key in keys:
		data = rna_ui[key]
		custom_prop = CustomProp(
			key,
			default = from_obj[key],
			_min = data['min'],
			_max = data['max'],
			soft_min = data['soft_min'],
			soft_max = data['soft_max'],
		)
		if 'description' in data:
			custom_prop.description = data['description']
		custom_prop.make_real(to_obj)
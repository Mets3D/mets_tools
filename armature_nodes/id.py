import bpy
from mets_tools import utils

class ID:
	def __init__(self):
		self.name = ""
		self.custom_properties = {}	# (name : CustomProp()) dictionary

	def __str__(self):
		return self.name

	def make_real(self, target, skip=[], recursive=False):
		utils.copy_attributes(self, target, skip, recursive)
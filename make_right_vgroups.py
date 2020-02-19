import bpy
from . import utils
from bpy.props import *

class CreateMirrorVGroups(bpy.types.Operator):
	""" Create missing Vertex Groups for mirror modifier. """
	bl_idname = "armature.create_mirror_vgroups"
	bl_label = "Create Mirror Vertex Groups"
	bl_options = {'REGISTER', 'UNDO'}

	opt_objects: EnumProperty(name="Objects",
		items=[	('Active', 'Active', 'Active'),
				('Selected', 'Selected', 'Selected'),
				('All', 'All', 'All')
				],
		description="Which objects to operate on")

	def execute(self, context):
		objs = context.selected_objects
		if(self.opt_objects=='Active'):
			objs = [context.object]
		elif(self.opt_objects=='All'):
			objs = bpy.data.objects

		for o in objs:
			vgs = o.vertex_groups
			for v in vgs:
				flippedName = utils.flip_name(v.name)
				if(flippedName not in vgs):
					o.vertex_groups.new(name=flippedName)
	
		return {"FINISHED"}
	
	
	def draw_create_mirror_vgroups(self, context):
		operator = self.layout.operator(CreateMirrorVGroups.bl_idname, text="Create Mirror Groups")
		operator.opt_objects = 'Active'

def register():
	from bpy.utils import register_class
	bpy.types.MESH_MT_vertex_group_context_menu.prepend(CreateMirrorVGroups.draw_create_mirror_vgroups)
	register_class(CreateMirrorVGroups)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(CreateMirrorVGroups)
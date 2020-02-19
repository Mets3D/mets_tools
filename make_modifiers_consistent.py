import bpy
from bpy.props import *

class MakeModifiersConsistent(bpy.types.Operator):
	""" Set certain settings on modifiers of selected objects, or copy them from an active object. """
	bl_idname = "object.make_modifiers_consistent"
	bl_label = "Make Modifiers Consistent"
	bl_options = {'REGISTER', 'UNDO'}
	
	use_active: BoolProperty(
		name="From Active",
		default=False,
		description="If enabled, use the active object's modifier settings. Otherwise, use hard coded settings.")
	
	do_mirror: BoolProperty(
		name="Mirror",
		default=True,
		description="Affect Mirror modifiers")
	do_subsurf: BoolProperty(
		name="SubSurf",
		default=True,
		description="Affect SubSurf modifiers")
	do_armature: BoolProperty(
		name="Armature",
		default=True,
		description="Affect Armature modifiers")
	do_solidify: BoolProperty(
		name="Solidify",
		default=True,
		description="Affect Solidify modifiers")
	do_bevel: BoolProperty(
		name="Bevel",
		default=True,
		description="Affect Bevel modifiers")

	def execute(self, context):
		active = context.object
		active_mirror = None
		active_solidify = None
		active_subsurf = None
		active_bevel = None
		active_armature = None

		if(self.use_active):
			for m in active.modifiers:
				if(m.type=='MIRROR'):
					active_mirror = m
				if(m.type=='SOLIDIFY'):
					active_solidify = m
				if(m.type=='SUBSURF'):
					active_subsurf = m
				if(m.type=='BEVEL'):
					active_bevel = m
				if(m.type=='ARMATURE'):
					active_armature = m

		objs = context.selected_objects
		for obj in objs:
			if(obj.type != 'MESH'): continue
			
			obj.show_wire = False
			obj.show_all_edges = True
			for m in obj.modifiers:
				if(m.type == 'MIRROR' and self.do_mirror):
					m.name = 'Mirror'
					if(active_mirror):
						m.show_viewport = active_mirror.show_viewport
						m.show_render = active_mirror.show_render
						m.show_in_editmode = active_mirror.show_in_editmode
						m.use_clip = active_mirror.use_clip
					else:
						m.show_viewport = True
						m.show_render = True
						m.show_in_editmode = True
						m.use_clip = True
				elif(m.type == 'ARMATURE' and self.do_armature):
					m.name = 'Armature'
					if(active_armature):
						m.show_viewport = active_armature.show_viewport
						m.show_render = active_armature.show_render
						m.show_in_editmode = active_armature.show_in_editmode
						m.show_on_cage = active_armature.show_on_cage
					else:
						m.show_viewport = True
						m.show_render = True
						m.show_in_editmode = True
						m.show_on_cage = True
				elif(m.type == 'SOLIDIFY' and self.do_solidify):
					m.name = 'Solidify'
					if(active_solidify):
						m.show_viewport = False
						m.show_render = True
					else:
						m.show_viewport = False
						m.show_render = True
						#print("Object: "+o.name + " Only Rim: " + str(m.use_rim_only))
				elif(m.type == 'BEVEL' and self.do_bevel):
					m.name = 'Bevel'
					if(active_bevel):
						m.show_viewport = active_bevel.show_viewport
						m.show_render = active_bevel.show_render
						m.segments = active_bevel.segments
						m.limit_method = active_bevel.limit_method
						m.offset_type = active_bevel.offset_type
						m.harden_normals = active_bevel.harden_normals
						m.width_pct = active_bevel.width_pct
						m.width = active_bevel.width
					else:
						m.show_viewport = False
						m.show_render = True
						m.segments = 2
						m.limit_method = 'WEIGHT'
						m.offset_type = 'PERCENT'
						m.harden_normals = True
						m.width_pct = 1
						m.width = 0.1
				elif(m.type == 'SUBSURF' and self.do_subsurf):
					m.name = 'Subdivision'
					if(active_subsurf):
						m.show_viewport = active_subsurf.show_viewport
						m.show_render = active_subsurf.show_render
						m.show_in_editmode = active_subsurf.show_in_editmode
						m.levels = active_subsurf.levels
						m.render_levels = active_subsurf.render_levels
						m.show_only_control_edges = active_subsurf.show_only_control_edges
						m.quality = active_subsurf.quality
					else:
						m.show_viewport = True
						m.show_render = True
						m.show_in_editmode = True
						m.levels = 0
						m.render_levels = 2
						m.show_only_control_edges = True
						m.quality = 3
		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	register_class(MakeModifiersConsistent)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(MakeModifiersConsistent)
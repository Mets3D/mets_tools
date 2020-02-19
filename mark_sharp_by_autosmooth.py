import bpy
import bmesh
from bpy.props import *

class MarkSharpByAutoSmooth(bpy.types.Operator):
	""" Marks hard edges of all selected meshes based on the Auto Smooth angle. Only works if auto smooth is turned on for the object."""
	bl_idname = "object.mark_sharp_by_auto_smooth"
	bl_label = "Mark Sharp By Auto Smooth"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		org_active = bpy.context.view_layer.objects.active
		org_mode = org_active.mode

		for o in bpy.context.selected_objects:
			bpy.context.view_layer.objects.active = o
			if(o.data.use_auto_smooth == False):
				print(str(o.name) + "Auto smooth is off, not doing anything")
			else:
				bpy.ops.object.mode_set(mode='EDIT')
				bpy.ops.mesh.select_all(action='SELECT')
				bpy.ops.mesh.faces_shade_smooth()
				#bpy.context.object.data.show_edge_sharp = True		# This is no longer per-object in 2.8, and the new setting in bpy.context.screen.overlays doesn't seem to be readable from python.
				
				bm = bmesh.from_edit_mesh(o.data)
				
				for e in bm.edges:
					if( e.calc_face_angle(0) >= o.data.auto_smooth_angle ):
						e.smooth = False
						
				bpy.ops.object.mode_set(mode='OBJECT')

		bpy.context.view_layer.objects.active = org_active
		bpy.ops.object.mode_set(mode=org_mode)
		
		return { 'FINISHED' }

def draw_func_MarkSharpByAutoSmooth(self, context):
	self.layout.operator(MarkSharpByAutoSmooth.bl_idname, text=MarkSharpByAutoSmooth.bl_label)

def register():
	from bpy.utils import register_class
	register_class(MarkSharpByAutoSmooth)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(MarkSharpByAutoSmooth)
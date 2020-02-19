import bpy
from bpy.props import *

class CreateLightMapUVs(bpy.types.Operator):
	""" Create Lightmap UVs using Smart UV Project on the second UV channel. Useful for exporting to UE4, since the result should be better than default UE4 generated lightmaps. """
	bl_idname = "object.create_lightmap_uvs"
	bl_label = "Create LightMap UVs"
	bl_options = {'REGISTER', 'UNDO'}
	
	opt_angle: IntProperty(name="Angle Limit",
				description="Angle limit for Smart UV Project Operator",
				default=66, min=1, max=89, soft_min=1, soft_max=89)
				
	opt_margin: FloatProperty(name="Island Margin",
				description="Island Margin for Smart UV Project Operator",
				default=0.01, min=0, max=1, soft_min=0, soft_max=1)

	opt_overwrite: BoolProperty(name="Overwrite Existing", 
				description="Overwrite any existing UV maps generated with by this operator",
				default=True)
	opt_reset_slot: BoolProperty(name="Keep active layer", 
				description="Keep the original active UV layer, rather than making the newly created one active",
				default=True)
	
	def execute(self, context):
        # For each selected object:
        #	Create new UV map (hopefully this will become selected by default)
        #	Rename it to UV_LightMap
        #	Make mesh active
        #	Go edit mode
        #	Select all
        #	Smart UV project with default values
        #	re-Select first UV map

		org_active = bpy.context.view_layer.objects.active
		org_mode = org_active.mode
		bpy.ops.object.mode_set(mode='OBJECT')

		for o in bpy.context.selected_objects:
			o_mode = o.mode
			bpy.context.view_layer.objects.active = o
			if(self.opt_overwrite):
				UVLayer = o.data.uv_layers.get("UV_LightMap")
				if(UVLayer is not None):
					UVLayer.active = True
					bpy.ops.mesh.uv_texture_remove()

			if(len(o.data.uv_layers) is 1):
				bpy.ops.object.mode_set(mode='EDIT')
				bpy.ops.mesh.uv_texture_add()
				o.data.uv_layers[-1].name = "UV_LightMap"
				bpy.ops.mesh.select_all(action='SELECT')
				bpy.ops.uv.smart_project(island_margin=self.opt_margin, angle_limit=self.opt_angle)
				if(self.opt_reset_slot):
					o.data.uv_layers[0].active = True
				
				bpy.ops.object.mode_set(mode=o_mode)

		bpy.context.view_layer.objects.active = org_active
		bpy.ops.object.mode_set(mode=org_mode)
		
		return { 'FINISHED' }
	
def draw_func_CreateLightMapUVs(self, context):
    # No UI beside spacebar menu.
	self.layout.operator(CreateLightMapUVs.bl_idname, text=CreateLightMapUVs.bl_label)

def register():
	from bpy.utils import register_class
	register_class(CreateLightMapUVs)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(CreateLightMapUVs)
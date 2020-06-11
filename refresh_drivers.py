import bpy
from bpy.props import BoolProperty

def refresh_drivers(datablock):
	if not datablock: return
	if not hasattr(datablock, "animation_data"): return
	if not datablock.animation_data: return
	for d in datablock.animation_data.drivers:
		d.driver.type = d.driver.type

class RefreshDrivers(bpy.types.Operator):
	"""Refresh drivers, ensuring no valid drivers are marked as invalid"""

	bl_idname = "object.refresh_drivers"
	bl_label = "Refresh Drivers"
	bl_options = {'REGISTER', 'UNDO'}

	selected_only: BoolProperty(name="Only Selected Objects", default=True)

	def execute(self, context):
		objs = context.selected_objects if self.selected_only else bpy.data.objects

		for o in objs:
			refresh_drivers(o)
			if hasattr(o, "data") and o.data:
				refresh_drivers(o.data)
			if o.type=='MESH':
				refresh_drivers(o.data.shape_keys)
			
			for ms in o.material_slots:
				if ms.material:
					refresh_drivers(ms.material)
					refresh_drivers(ms.material.node_tree)

		return { 'FINISHED' }

def register():
	from bpy.utils import register_class
	register_class(RefreshDrivers)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(RefreshDrivers)
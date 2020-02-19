import bpy

# Well, this is silly, but here it is.

class RefreshDrivers(bpy.types.Operator):
	"""Refresh drivers, ensuring no valid drivers are marked as invalid"""
	bl_idname = "object.refresh_drivers"
	bl_label = "Refresh Drivers on selected objects"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		def refresh_drivers(thing):
			if not thing.animation_data: return
			for d in thing.animation_data.drivers:
				if d.driver.type != 'SCRIPTED': continue
				d.driver.expression = d.driver.expression

		for o in context.selected_objects:
			refresh_drivers(o)
			refresh_drivers(o.data)
			if o.type=='MESH':
				refresh_drivers(o.data.shape_keys)

		return { 'FINISHED' }


def register():
	from bpy.utils import register_class
	register_class(RefreshDrivers)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(RefreshDrivers)
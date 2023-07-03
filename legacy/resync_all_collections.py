import bpy

def recursive_search_layer_collection(collName, layerColl=None) -> bpy.types.LayerCollection:
	# Recursivly transverse layer_collection for a particular name
	# This is the only way to set active collection as of 14-04-2020.
	if not layerColl:
		layerColl = bpy.context.view_layer.layer_collection

	found = None
	if (layerColl.name == collName):
		return layerColl
	for layer in layerColl.children:
		found = recursive_search_layer_collection(collName, layer)
		if found:
			return found

def set_active_collection(collection):
	layer_collection = recursive_search_layer_collection(collection.name)
	bpy.context.view_layer.active_layer_collection = layer_collection

class ResyncAll(bpy.types.Operator):
	"""Resync all overridden collections"""

	bl_idname = "object.resync_all_overridden_collections"
	bl_label = "Resync All Overridden Collections"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		ui_type = bpy.context.area.ui_type
		bpy.context.area.ui_type = 'OUTLINER'

		# Reload all libraries
		for l in bpy.data.libraries:
			print("Reloading library: " + l.name)
			l.reload()

		# Resync all collections
		for c in bpy.data.collections:
			if c.override_library:
				set_active_collection(c)
				print("Resyncing collection: " + c.name)
				bpy.ops.outliner.id_operation(type='OVERRIDE_LIBRARY_RESYNC_HIERARCHY')

		bpy.context.area.ui_type = ui_type
		return { 'FINISHED' }

	def draw(self, context):
		layout = self.layout
		layout.operator(ResyncAll.bl_idname)

def register():
	from bpy.utils import register_class
	register_class(ResyncAll)
	bpy.types.OUTLINER_MT_context_menu.append(ResyncAll.draw)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(ResyncAll)
	bpy.types.OUTLINER_MT_context_menu.remove(ResyncAll.draw)
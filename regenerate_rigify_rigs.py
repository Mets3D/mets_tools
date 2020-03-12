import bpy

def safe_generate(context, metarig, target_rig, coll):
	# Generating requires the metarig to be the active object, and the target rig to be visible.
	# To achieve this, we create a temporary collection, and link the metarig and target rig in there for generation.
	
	# Add both objects to the temp collection.
	if metarig.name not in coll.objects:
		coll.objects.link(metarig)
	if target_rig.name not in coll.objects:
		coll.objects.link(target_rig)

	# Save visibility states
	metarig_disabled = metarig.hide_viewport
	metarig_hide = metarig.hide_get()

	target_rig_disabled = target_rig.hide_viewport
	target_rig_hide = target_rig.hide_get()

	# Set visibility states
	metarig.hide_viewport = False
	metarig.hide_set(False)

	target_rig.hide_viewport = False
	target_rig.hide_set(False)

	# Generate.
	context.view_layer.objects.active = metarig
	bpy.ops.pose.rigify_generate()

	# Reset visibility states.
	metarig.hide_viewport = metarig_disabled
	metarig.hide_set(metarig_hide)

	target_rig.hide_viewport = target_rig_disabled
	target_rig.hide_set(target_rig_hide)

def rigify_cleanup(context, rig):
	""" Rigify does some nasty things so late in the generation process that it cannot be handled from a custom featureset's code, so I'll put it here. """
	# Delete driver on pass_index
	rig.driver_remove("pass_index")
	# Delete rig_ui.py from blend file
	text = bpy.data.texts.get("rig_ui.py")
	if text:
		bpy.data.texts.remove(text)

class Regenerate_Rigify_Rigs(bpy.types.Operator):
	""" Regenerate all Rigify rigs in the file. (Only works on metarigs that have an existing target rig.) """
	bl_idname = "object.regenerate_all_rigify_rigs"
	bl_label = "Regenerate All Rigify Rigs"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# Create temporary collection to work in
		coll_name = "temp_rigify_generate"
		coll = bpy.data.collections.get(coll_name)
		if not coll:
			coll = bpy.data.collections.new(coll_name)
		if coll_name not in context.scene.collection.children:
			context.scene.collection.children.link(coll)

		for o in bpy.data.objects:
			if o.type!='ARMATURE': continue
			if o.data.rigify_target_rig:
				metarig = o
				target_rig = o.data.rigify_target_rig
				safe_generate(context, metarig, target_rig, coll)
				rigify_cleanup(context, target_rig)

		bpy.data.collections.remove(coll)

		bpy.ops.object.refresh_drivers(selected_only=False)

		return { 'FINISHED' }

def register():
	from bpy.utils import register_class
	register_class(Regenerate_Rigify_Rigs)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(Regenerate_Rigify_Rigs)
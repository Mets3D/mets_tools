import bpy
from bpy.props import StringProperty, EnumProperty

def read_constraint(constraint):
	skip = []
	attribs = {}
	for k in dir(constraint):
		if "_" in k: continue
		if k in skip: continue
		attribs[k] = getattr(constraint, k)
	if constraint.type=='ARMATURE':
		target_list = []
		for t in constraint.targets:
			target_list.append( (t.subtarget, t.value) )
		attribs['targets'] = target_list
	return attribs

def write_constraint(obj, constraint_data):
	con_type = constraint_data[0]
	con_attribs = constraint_data[1]
	
	con = obj.constraints.new(constraint_data[0])
	for k in con_attribs.keys():
		try:
			setattr(con, k, con_attribs[k])
		except:
			pass
	if con_type=='ARMATURE':
		for t in con_attribs['targets']:
			target = con.targets.new()
			target.target = obj
			target.subtarget = t[0]
			target.value = t[1]
	return con

def constraints_in_file_with_object(obj):
	"""Go through every object and bone in the file(except self!!!), and return a list of constraints that target the given object."""
	ret = []
	for o in bpy.data.objects:
		if o == obj: continue
		for c in o.constraints:
			if c.target == obj:
				ret.append(c)
		if o.type=='ARMATURE':
			for b in o.pose.bones:
				for c in b.constraints:
					if c.type=='ARMATURE':
						for t in c.targets:
							if t.target == obj:	# NOTE: This only supports Armature constraints where every target object is the same.
								ret.append(c)
								break
					elif hasattr(c, 'target') and c.target == obj:
						ret.append(c)
	return ret

class ReProxy_Rigs(bpy.types.Operator):
	""" Reload a library associated with a selected proxy rig, and re-create the proxied rig while preserving constraints in the scene that target it, as well as constraints that were added to the proxy rig. """
	bl_idname = "object.reload_proxied_library"
	bl_label = "Reload Proxied Library"
	bl_options = {'REGISTER', 'UNDO'}

	blendfile: StringProperty(
		name="Blend File",
		description="Absolute path to the blendfile to re-link and re-proxy from"
	)
	collection_name: StringProperty(
		name="Collection Name",
		description="Name of the collection to link"
	)
	rig_name: StringProperty(
		name="Rig Name",
		description="Name of the rig to create a proxy of"
	)
	constraint_mode: EnumProperty(
		name="Copy Constraints", 
		items = [
			('LOCAL', 'Local Constraints', 'Only copy constraints to the re-proxied rig if the constraint has is_proxy_local==True. This is only the case when the constraint was created on the proxy armature AND the bone is in a protected layer.'),
			('ALL', 'All Constraints', "Copy all constraints to the re-proxied rig. Should only be used when the original armature didn't have any constraints.")
		],
		default='LOCAL'
	)

	def execute(self, context):
		""" Based on a selected proxy armature, reload the proxied collection and re-proxy the armature, while maintaining all local constraints."""
		bpy.ops.object.mode_set(mode='OBJECT')

		rig = context.object
		
		empty = rig.proxy_collection
		context.scene.cursor.location = empty.location[:]	# When we re-link, the new empty will be spawned at the cursor, so we want to make sure it lands in the same place.

		# Save Action
		anim_data = rig.animation_data
		action = None
		if anim_data:
			action = rig.animation_data.action

		# Save constraints on the proxy rig that are local(ie. added by the animators)
		# Dictionary of BoneName : [list of (type, {attribs}) tuples], where attribs is a dictionary of constraint attributes.
		object_constraints = []
		for c in rig.constraints:
			object_constraints.append( (c.type, read_constraint(c)) )

		constraints = {"BoneName" : [('COPY_ROTATION', {'name' : "Copy Rotation"})]}
		constraints = {}

		for b in rig.pose.bones:
			for c in b.constraints:
				if self.constraint_mode=='ALL' or c.is_proxy_local:
					if b.name not in constraints.keys():
						constraints[b.name] = []
					constraints[b.name].append( (c.type, read_constraint(c)) )

		# Save constraints that target the proxy rig
		constraints_targetting_proxy = constraints_in_file_with_object(rig)

		# Save collections
		rig_collections = rig.users_collection[:]
		empty_collections = empty.users_collection[:]
		
		# Make temp work collection so we can ensure visibility of the proxies and empties.
		coll_name = "temp_reproxy_coll"
		temp_coll = bpy.data.collections.get(coll_name)
		if not temp_coll:
			temp_coll = bpy.data.collections.new(coll_name)
		if coll_name not in context.scene.collection.children:
			context.scene.collection.children.link(temp_coll)
		
		if rig.name not in temp_coll.objects:
			temp_coll.objects.link(rig)
			rig.hide_set(False)
			rig.hide_viewport = False
		if empty.name not in temp_coll.objects:
			temp_coll.objects.link(empty)
			empty.hide_set(False)
			empty.hide_viewport = False
		
		# Delete objects
		bpy.data.objects.remove(rig) # Delete the proxy armature.
		bpy.data.objects.remove(empty)  # Delete the Empty object that references the collection

		#####################################################################################################

		# Re-link the collection.
		blendfile = self.blendfile
		collection_name = self.collection_name
		section = "\\Collection\\"
		bpy.ops.wm.link(
			filepath = blendfile + section + collection_name,
			filename = collection_name,
			directory = blendfile + section
		)
		empty = context.object

		# Re-proxy the rig.
		bpy.ops.object.proxy_make(object=self.rig_name)
		rig = context.object

		# Apply the constraints in the rig.
		for ob_con in object_constraints:
			write_constraint(rig, ob_con)

		for bone_name in constraints.keys():
			pbone = rig.pose.bones.get(bone_name)
			for constraint_data in constraints[bone_name]:
				write_constraint(pbone, constraint_data)

		# Fix constraints in the scene that should target the rig.
		for c in constraints_targetting_proxy:
			if c.type=='ARMATURE':
				for t in c.targets:
					t.target = rig
			else:
				c.target = rig

		# Apply the action.
		rig.driver_add("hide_render") # Just to initialize animation_data.
		rig.animation_data.action = action
		rig.driver_remove("hide_render")

		# Delete temp collection
		bpy.data.collections.remove(temp_coll)

		# Unlink objects from their current collections
		for coll in rig.users_collection:
			coll.objects.unlink(rig)
			coll.objects.unlink(empty)

		# Link to original collections
		for coll in rig_collections:
			coll.objects.link(rig)
		for coll in empty_collections:
			coll.objects.link(empty)
		empty_collections = empty.users_collection[:]

		return { 'FINISHED' }

	def invoke(self, context, event):
		wm = context.window_manager

		rig = context.object
		assert rig.type=='ARMATURE', "Error: Select an armature."
		original = rig.proxy	# Oddly named attribute. ID.proxy actually references what object this object is a proxy of. Very confusing.
		assert original, "Error: Selected armature is not a proxy!"

		library = original.library
		empty = rig.proxy_collection

		self.blendfile = bpy.path.abspath(library.filepath)
		self.collection_name = empty.name
		self.rig_name = original.name

		return wm.invoke_props_dialog(self)
	
	def draw(self, context):
		layout = self.layout

		layout.row().prop(self, "blendfile")
		layout.row().prop(self, "collection_name")
		layout.row().prop(self, "rig_name")

		layout.prop(self, "constraint_mode", expand=True)

def register():
	from bpy.utils import register_class
	register_class(ReProxy_Rigs)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(ReProxy_Rigs)
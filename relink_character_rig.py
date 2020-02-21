import bpy

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
	# Verbose as fuck.
	# Go through every object and bone in the file(except self!!!), and return a list of constraints that target the given object.
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
							if t.target == obj:
								ret.append(c)
								break
					elif hasattr(c, 'target') and c.target == obj:
						ret.append(c)
	return ret

class ReProxy_Rig(bpy.types.Operator):
	""" Reload a library associated with a selected proxy rig, and re-create the proxied rig while preserving constraints in the scene that target it, as well as constraints that were added to the proxy rig. """
	bl_idname = "object.reload_proxied_library"
	bl_label = "Reload Proxied Library"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# Prepare data

		rig = context.object
		assert rig.type=='ARMATURE', "Error: Select an armature."
		original = rig.proxy	# Oddly named attribute. ID.proxy actually references what object this object is a proxy of. Very confusing.
		assert original, "Error: Selected armature is not a proxy!"
		
		library = original.library
		blendfile = bpy.path.abspath(library.filepath)

		empty = rig.proxy_collection
		context.scene.cursor.location = empty.location[:]	# When we re-link, the new empty will be spawned at the cursor, so we want to make sure it lands in the same place.
		
		collection_name = empty.name
		original_name = original.name

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
				if c.is_proxy_local:
					if b.name not in constraints.keys():
						constraints[b.name] = []
					constraints[b.name].append( (c.type, read_constraint(c)) )

		bpy.ops.object.mode_set(mode='OBJECT')

		# Save constraints that target the proxy rig
		constraints_targetting_proxy = constraints_in_file_with_object(rig)

		# Save collections
		rig_collections = rig.users_collection[:]
		empty_collections = empty.users_collection[:]

		# Delete objects
		bpy.data.objects.remove(rig) # Delete the proxy armature.
		bpy.data.objects.remove(empty)  # Delete the Empty object that references the collection

		#####################################################################################################

		# Re-link the collection.
		section = "\\Collection\\"
		bpy.ops.wm.link(
			filepath = blendfile + section + collection_name,
			filename = collection_name,
			directory = blendfile + section
		)
		empty = context.object

		# Re-proxy the rig.
		bpy.ops.object.proxy_make(object=original_name)
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

def register():
	from bpy.utils import register_class
	register_class(ReProxy_Rig)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(ReProxy_Rig)

register()
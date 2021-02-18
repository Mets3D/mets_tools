import bpy

class MESH_OT_vertex_parent_bone(bpy.types.Operator):
	"""Parent selected pose bones to selected vertices using an Armature modifier"""

	bl_idname = "mesh.parent_bones_to_verts"
	bl_label = "Parent Pose Bones to Vertices"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		"""This operator is available when there is a selected armature and the user is in mesh edit mode."""
		if len(context.selected_objects) == 2:
			if context.mode=='EDIT_MESH':
				for o in context.selected_objects:
					if o.type=='ARMATURE':
						return True

	def execute(self, context):
		for o in context.selected_objects:
			if o.type=='ARMATURE':
				rig = o

		selected_pose_bones = []
		deforming_pose_bones = []
		for pb in rig.pose.bones:
			if pb.bone.select:
				selected_pose_bones.append(pb)
			if pb.bone.use_deform:
				deforming_pose_bones.append(pb)

		meshob = context.object
		mesh = meshob.data

		selected_verts = list(filter(lambda v: v.select, mesh.vertices))

		weights = {}	# pose bone name : total un-normalized weight
		for v in selected_verts:
			for pb in deforming_pose_bones:
				vg = meshob.vertex_groups.get(pb.name)
				if not vg: continue

				try:
					w = vg.weight(v.index)
					if vg.name not in weights:
						weights[vg.name] = 0
					weights[vg.name] += w
				except:
					pass

		# Normalize the weights
		sum_weights = sum(weights.values())
		weights = {bonename:v/sum_weights for (bonename, v) in weights.items()}
		for pb in selected_pose_bones:
			arm_con = pb.constraints.new('ARMATURE')
			for bonename in weights.keys():
				t = arm_con.targets.new()
				t.target = rig
				t.subtarget = bonename
				t.weight = weights[bonename]

		return {'FINISHED'}

def register():
	bpy.utils.register_class(MESH_OT_vertex_parent_bone)

def unregister():
	bpy.utils.unregister_class(MESH_OT_vertex_parent_bone)

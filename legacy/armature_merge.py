import bpy
import time

# In order to merge multiple armatures into one cleanly, we need to:
# For each source armature:
	# - Remap Users to the target armature (This should fix modifiers and parenting)
	# For each bone group:
		# Check if already exists in target armature and has matching colors. 
			# If not, create it in the target armature and rename the sourcegroup to whatever name the new group ends up with (for .00x suffix).
	# For each bone:
		# Check if a bone with this name already exists in target rig. If yes, add .001 ending. Increment until bone name is available.

	# Save mapping of bones to bone groups
	
	# Merge the (TWO) armatures.
	# Assign bone groups to bones based on the mapping.

class Timer:
	"""Quick timer class to help debug performance."""
	def __init__(self):
		self.start = time.time()
		self.last = self.start

	def tick(self, msg=""):
		now = time.time()
		print(msg + ": " + str(now-self.last))
		self.last = now

class MergeArmatures(bpy.types.Operator):
	"""Merge armatures correctly"""

	bl_idname = "object.merge_armatures"
	bl_label = "Merge Armatures"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		timer = Timer()
		
		# Remap Users.
		armature.user_remap(target_armature)

		target_armature = context.object
		if target_armature.type != 'ARMATURE':
			self.report({'ERROR'}, "Active object must be an armature!")
			return {'CANCELLED'}

		# Find list of armatures to be merged.
		source_armatures = []
		for o in context.selected_objects:
			if o.type=='ARMATURE' and o != target_armature:
				source_armatures.append(o)
		
		if len(source_armatures) < 1:
			self.report({'ERROR'}), "Select more than one armature!"
			return {'CANCELLED'}

		for armature in source_armatures[:]:
			print("Merging " + armature.name + " into " + target_armature.name)
			# Bone Groups
			for source_group in armature.pose.bone_groups:
				target_group = target_armature.pose.bone_groups.get(source_group.name)
				matching = False	# If the target group exists and matches the source group's color settings, we don't need to create a new target group.
				if target_group:
					if target_group.color_set==source_group.color_set:
						if target_group.color_set!='CUSTOM':
							matching = True
						else:
							if target_group.colors.normal == source_group.colors.normal \
								and target_group.colors.select == source_group.colors.select \
								and target_group.colors.active == source_group.colors.active:
								matching = True

				if not matching:
					# Create the target group with the correct colors, and rename the source group to whatever name it got created with.
					target_group = target_armature.pose.bone_groups.new(name=source_group.name)
					target_group.color_set = source_group.color_set
					if target_group.color_set == 'CUSTOM':
						target_group.colors.normal = source_group.colors.normal[:]
						target_group.colors.select = source_group.colors.select[:]
						target_group.colors.active = source_group.colors.active[:]
					source_group.name = target_group.name

			bone_groups = {}

			# Bones
			for pb in armature.pose.bones:
				counter = 1
				base_name = pb.name
				if len(pb.name) > 4 and pb.name[-4] == '.':
					base_name = pb.name[:-4]
					try:
						counter = int(pb.name[-4:])
					except: pass
				name = pb.name
				while name in target_armature.pose.bones:
					name = base_name + ".%03d" %(counter)
					counter += 1
					if counter > 999:
						self.report({'ERROR'}, "Whoa there, that's a lot of bones with the same name.")
						return {'CANCELLED'}
				pb.name = name
			
				# Save bone to bone group mapping
				bg = pb.bone_group
				if bg:
					if bg.name not in bone_groups:
						bone_groups[bg.name] = [pb.name]
					else:
						bone_groups[bg.name].append(pb.name)
			
			# Save modifiers referencing the source armature
			modifiers = []
			for o in bpy.data.objects:
				if o.type!='MESH': continue
				for m in o.modifiers:
					if m.type=='ARMATURE' and m.object==armature:
						modifiers.append(m)
			
			# Save child transforms
			children = {}
			for c in armature.children:
				children[c] = c.matrix_world.copy()
			timer.tick("Prep")

			# Merge this armature into the target armature.
			with context.temp_override(selected_editable_objects=[armature, target_armature], object=target_armature):
				bpy.ops.object.join()
			timer.tick("Join")	# The Join operator itself is taking FOR EVER!!

			# Restore modifier targets
			for m in modifiers:
				m.object = target_armature

			# Restore child transforms
			for c in children.keys():
				c.matrix_world = children[c]

			# Assign bone groups
			for bg_name in bone_groups.keys():
				bone_names = bone_groups[bg_name]
				for bn in bone_names:
					pb = target_armature.pose.bones.get(bn)
					pb.bone_group = target_armature.pose.bone_groups.get(bg_name)
			timer.tick("Restore")

		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	register_class(MergeArmatures)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(MergeArmatures)
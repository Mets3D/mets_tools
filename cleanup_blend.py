import bmesh
import bpy
from bpy.props import *
from . import utils

# TODO testing:
# Mirror modifier vertex groups getting spared when they should
# Oh, and also everything else.
# More specifically, I wonder if the "All" settings, to operate on bpy.data.objects, will work, when some objects are hidden or disabled, etc.

class DeleteUnusedMaterialSlots(bpy.types.Operator):
	""" Delete material slots on selected objects that have no faces assigned. """
	bl_idname = "object.delete_unused_material_slots"
	bl_label = "Delete Unused Material Slots"
	bl_options = {'REGISTER', 'UNDO'}

	# TODO: Add this to the UI, to the material arrow panel, with opt_active_only=True.

	opt_objects: EnumProperty(name="Objects",
		items=[	('Active', 'Active', 'Active'),
				('Selected', 'Selected', 'Selected'),
				('All', 'All', 'All')
				],
		default='Selected',
		description="Which objects to operate on")

	def draw(self, context):
		operator = self.layout.operator(DeleteUnusedMaterialSlots.bl_idname, text="Delete Unused Slots", icon='X')
		operator.opt_objects = 'Active'
	
	def execute(self, context):
		org_active = context.object

		objs = context.selected_objects
		if(self.opt_objects=='Active'):
			objs = [context.object]
		elif(self.opt_objects=='All'):
			objs = bpy.data.objects

		for obj in objs:
			if(type(obj)!=bpy.types.Object or 
				obj.type!='MESH' or 
				len(obj.data.polygons)==0): continue

			bpy.context.view_layer.objects.active = obj
			used_mat_indices = []
			for f in obj.data.polygons:
				if(f.material_index not in used_mat_indices):
					used_mat_indices.append(f.material_index)

			# To remove the material slots, we iterate in reverse.
			for i in range(len(obj.material_slots)-1, -1, -1):
				if(i not in used_mat_indices):
					obj.active_material_index = i
					print("Removed material slot " + str(i))
					bpy.ops.object.material_slot_remove()

		bpy.context.view_layer.objects.active = org_active
		return {'FINISHED'}

class DeleteUnusedVGroups(bpy.types.Operator):
	""" Delete vertex groups that have no weights AND aren't being used by any modifiers(including Mirror) AND aren't used as mask by any shape keys AND don't correlate to any bones """
	bl_idname = "object.delete_unused_vgroups"
	bl_label = "Delete Unused Vertex Groups"
	bl_options = {'REGISTER', 'UNDO'}
	
	# TODO: Should also consider vertex groups used by any kinds of constraints. 
	# Oof. We'd have to look through the objects and bones of the entire scene for that. Maybe worth?

	# TODO: Should also consider shape keys masks.

	opt_objects: EnumProperty(name="Objects",
		items=[	('Active', 'Active', 'Active'),
				('Selected', 'Selected', 'Selected'),
				('All', 'All', 'All')
				],
		description="Which objects to operate on")

	opt_save_bone_vgroups: BoolProperty(name="Save Bone Vertex Groups",
		default=True,
		description="Don't delete vertex groups that correspond with a bone name in any of the object's armatures, even if there are no weights assigned to it")

	opt_save_nonzero_vgroups: BoolProperty(name="Save Any Weights",
		default=False,
		description="Don't delete vertex groups that have any non-zero weights. Considers Mirror modifier")
	
	opt_save_modifier_vgroups: BoolProperty(name="Save Modifier Groups",
		default=True,
		description="Don't delete vertex groups that are referenced by a modifier, including physics settings")

	opt_save_shapekey_vgroups: BoolProperty(name="Save Shape Key Groups",
		default=True,
		description="Don't delete vertex groups that are used by a shape key as a mask")
	
	@classmethod
	def poll(cls, context):
		return len(context.object.vertex_groups) > 0
	
	def draw_delete_unused(self, context):
		operator = self.layout.operator(DeleteUnusedVGroups.bl_idname, text="Delete Unused Groups", icon='X')
		operator.opt_objects = 'Active'

	def execute(self, context):
		org_active = context.object

		objs = context.selected_objects
		if(self.opt_objects=='Active'):
			objs = [context.object]
		elif(self.opt_objects=='All'):
			objs = bpy.data.objects

		for obj in objs:
			if(len(obj.vertex_groups) == 0): continue
			
			bpy.context.view_layer.objects.active = obj

			# Clean 0 weights
			bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0)

			# Saving vertex groups that are used by modifiers and therefore should not be removed
			safe_groups = []
			def save_groups_by_attributes(owner):
				# Look through an object's attributes. If its value is a string, try to find a vertex group with the same name. If found, make sure we don't delete it.
				for attr in dir(owner):
					value = getattr(owner, attr)
					if(type(value)==str):
						vg = obj.vertex_groups.get(value)
						if(vg):
							safe_groups.append(vg)

			# Save any vertex groups used by modifier parameters.
			if(self.opt_save_modifier_vgroups):
				for m in obj.modifiers:
					save_groups_by_attributes(m)
					if(hasattr(m, 'settings')):	#Physics modifiers
						save_groups_by_attributes(m.settings)

			# Save any vertex groups used by shape keys.
			if(self.opt_save_shapekey_vgroups):
				for sk in obj.data.shape_keys.key_blocks:
					vg = obj.vertex_groups.get(sk.vertex_group)
					if(vg and vg not in safe_groups):
						safe_groups.append(vg)

			# Getting a list of bone names from all armature modifiers.
			bone_names = []
			for m in obj.modifiers:
				if(m.type == 'ARMATURE'):
					armature = m.object
					if armature is None:
						continue
					if(bone_names is None):
						bone_names = [b.name for b in armature.data.bones]
					else:
						bone_names.extend([b.name for b in armature.data.bones])
			
			# Saving any vertex groups that correspond to a bone name
			if(self.opt_save_bone_vgroups):
				for bn in bone_names:
					vg = obj.vertex_groups.get(bn)
					if(vg):
						safe_groups.append(vg)
				
			# Saving vertex groups that have any weights assigned to them, also considering mirror modifiers
			if(self.opt_save_nonzero_vgroups):
				for vg in obj.vertex_groups:	# For each vertex group
					for i in range(0, len(obj.data.vertices)):	# For each vertex
						try:
							vg.weight(i)							# If there's a weight assigned to this vert (else exception)
							if(vg not in safe_groups):
								safe_groups.append(vg)
								
								opp_name = utils.flip_name(vg.name)
								opp_group = obj.vertex_groups.get(opp_name)
								if(opp_group):
									safe_groups.append(opp_group)
								break
						except RuntimeError:
							continue
			
			# Clearing vertex groups that didn't get saved
			for vg in obj.vertex_groups:
				if(vg not in safe_groups):
					print("Unused vgroup removed: "+vg.name)
					obj.vertex_groups.remove(vg)
		
		bpy.context.view_layer.objects.active = org_active
		return {'FINISHED'}

def get_linked_nodes(nodes, node):	# Recursive function to collect all nodes connected BEFORE the second parameter.
	nodes.append(node)
	for i in node.inputs:
		if(len(i.links) > 0):
			get_linked_nodes(nodes, i.links[0].from_node)
	return nodes

def clean_node_tree(node_tree, delete_unused_nodes=True, fix_groups=False, center_nodes=True, fix_tex_refs=False, rename_tex_nodes=True, hide_sockets=False, min_sockets=2, tex_width=300):	# nodes = nodeTree.nodes
	nodes = node_tree.nodes
	if(len(nodes)==0): return

	if(delete_unused_nodes):
		# Deleting unconnected nodes
		output_nodes = list(filter(lambda x: x.type in ['OUTPUT_MATERIAL', 'OUTPUT_WORLD', 'COMPOSITE', 'VIEWER'], nodes))
		used_nodes = []
		for on in output_nodes:
			used_nodes.extend(get_linked_nodes([], on))

		for n in nodes:
			if(n not in used_nodes and n.type != 'FRAME'):
				print("Removing unconnected node: Type: " + n.type + " Name: " + n.name + " Label: " + n.label)
				nodes.remove(n)
				continue

	# Finding bounding box of all nodes
	x_min = min(n.location.x for n in nodes if n.type!= 'FRAME')
	x_max = max(n.location.x for n in nodes if n.type!= 'FRAME')
	y_min = min(n.location.y for n in nodes if n.type!= 'FRAME')
	y_max = max(n.location.y for n in nodes if n.type!= 'FRAME')
	
	# Finding bounding box center
	x_mid = (x_min+x_max)/2
	y_mid = (y_min+y_max)/2

	for n in nodes:
		if(fix_tex_refs):
			# Changing .xxx texture references
			if(n.type == 'TEX_IMAGE'):
				if(n.image is not None and n.image.name[-4] == '.'):
					existing = bpy.data.images.get(n.image.name[:-4])
					if(existing):
						print("Changed a texture reference to: "+n.image.name)
						n.image = bpy.data.images.get(n.image.name[:-4])
					else:
						n.image.name = n.image.name[:-4]
		
		if(n.type=='TEX_IMAGE'):
			# Resizing image texture nodes
			if(tex_width!=-1):
				n.width=tex_width
				n.width_hidden=tex_width
			
			if(rename_tex_nodes):
				# Renaming and relabelling image texture nodes
				if(n.image is not None):
					extension = "." + n.image.filepath.split(".")[-1]
					n.name = n.image.name.replace(extension, "")
					n.label = n.name
					if(n.label[-4] == '.'):
						n.label = n.label[:-4]
		
		if(hide_sockets):
			# Hiding unplugged sockets, if there are more than min_sockets.
			unplugged = []
			for i in n.inputs:
				if(len(i.links) == 0):
					unplugged.append(i)
			if(len(unplugged) > min_sockets):
				for u in unplugged:
					u.hide = True
			
			for i in n.outputs:
				if(len(i.links) == 0):
					unplugged.append(i)
			if(len(unplugged) > min_sockets):
				for u in unplugged:
					u.hide = True
		
		if(center_nodes):
			# Moving all nodes by the amount of the bounding box center(therefore making the center 0,0) - except Frame nodes, which move by themselves.
			if(n.type != 'FRAME'):
				n.location.x -= x_mid
				n.location.y -= y_mid

		if(fix_groups):
			# Changing references to nodegroups ending in .00x to their original. If the original doesn't exist, rename the nodegroup.
			for n in nodes:
				if(n.type=='GROUP'):
					if('.00' in n.node_tree.name):
						existing = bpy.data.node_groups.get(n.node_tree.name[:-4])
						if(existing):
							n.node_tree = existing
						else:
							n.node_tree.name = n.node_tree.name[:-4]

class CleanUpAction(bpy.types.Operator):
	"""Remove keyframes and curves that don't do anything from Actions."""
	bl_idname = "action.clean_up"
	bl_label = "Clean Up Action"
	bl_options = {'REGISTER', 'UNDO'}

	opt_all: BoolProperty(name="All Actions", default=False)
	opt_method: EnumProperty(name="Cleanup Method",
		items=(
			("INDIVIDUAL", "Individual", "If an individual curve doesn't do anything, remove it."),
			("TRANSFORM", "Per Transform Group", "If an entire group of curves don't do anything, remove them. Eg, only remove rotation curves if none of the rotation curves do anything."),
			("BONE", "Per Bone", "Only remove curves if all curves belonging to that bone don't do anything.")
		),
		default="TRANSFORM")
	opt_delete_default: BoolProperty(name="Delete Base Keyframes", description="If a curve only has one keyframe, and that keyframe is the default pose, delete it.", default=True)

	def execute(self, context):
		actions = bpy.data.actions if self.opt_all else [context.object.animation_data.action]

		for action in actions:
			bad_curves = {}	# Dict of data_path:[curves] where the list of curves is all curves for that data path(different array_index value though)
			for curve in action.fcurves:
				bad_kfs = []
				for i, kf in enumerate(curve.keyframe_points):
					if i==0: continue

					if kf.co[1] == curve.keyframe_points[i-1].co[1]: 			# Keyframe same as previous one
						if i != len(curve.keyframe_points)-1: 					# This is not the last keyframe
							if kf.co[1] == curve.keyframe_points[i+1].co[1]:	# And keyframe same as next one
								bad_kfs.append(kf)
						else:
							bad_kfs.append(kf)
				
				# Delete marked keyframes.
				for bkf in bad_kfs:
					try:	# TODO Idk why but it seems bad_kfs is sometimes not re-initialized as an empty list???
						curve.keyframe_points.remove(bkf)
					except: pass

				# Mark bad curve if there is only one keyframe and it is a default pose keyframe.
				if len(curve.keyframe_points) == 1:
					kf = curve.keyframe_points[0]
					bad = False
					if "scale" in curve.data_path:
						if kf.co[1] == 1.0:
							bad = True
					else:
						if kf.co[1] == 1.0 and "rotation_quaternion" in curve.data_path and curve.array_index==0:
							bad = True
						elif kf.co[1] == 0.0:
							bad = True
					if bad:
						if curve.data_path not in bad_curves:
							bad_curves[curve.data_path] = []
						bad_curves[curve.data_path].append(curve)
			
			for group in bad_curves.keys():
				# For now, just delete all bad curves.
				for curve in bad_curves[group]:
					action.fcurves.remove(curve)
					# TODO:
					# based on opt_method, check if other required curves are marked for delete.
					# If they all are, delete them all (and only then).

class CleanUpArmature(bpy.types.Operator):
	# TODO: turn into a valid operator
	# TODO: disable Deform tickbox on bones with no corresponding vgroups. (This would ideally be done before vgroup cleanup) - Always print a warning for this.
	# TODO: vice versa, warn if a non-deform bone has a corresponding vgroup.
	def execute(self, context):
		armature = context.object

		if(type(armature) != bpy.types.Object or 
			armature.type != 'ARMATURE' ): return {'CANCELLED'}

		for b in armature.pose.bones:
			# Closing and naming bone constraints
			for c in b.constraints:
				c.show_expanded = False
				if(c.type=='ACTION'):
					c.name = "Action_" + c.action.name
		
		# Making B-Bone thickness and envelope properties consistent
		for b in armature.data.bones:
			b.bbone_x = 0.005
			b.bbone_z = 0.005
			b.head_radius = 0.01
			b.tail_radius = 0.01
			b.envelope_distance = 0.03
			b.envelope_weight = 1
			
		return {'FINISHED'}

class CleanUpMaterials(bpy.types.Operator):
	bl_idname = "material.clean_up"
	bl_label = "Clean Up Material"
	bl_options = {'REGISTER', 'UNDO'}
	
	opt_objects: EnumProperty(name="Objects",
		items=[	('Active', 'Active', 'Active'),
				('Selected', 'Selected', 'Selected'),
				('All', 'All', 'All')
				],
		default='Selected',
		description="Which objects to operate on")

	opt_fix_name: BoolProperty(name="Fix .00x Material Names", 
		default=False, 
		description="Materials ending in .001 or similar will be attempted to be renamed")
		
	opt_delete_unused_nodes: BoolProperty(name="Clear Unused Nodes", 
		default=False, 
		description="Clear all nodes (except Frames) in all materials that aren't linked to the 'Material Output' node")
		
	opt_hide_sockets: BoolProperty(name="Hide Node Sockets", 
		default=False, 
		description="Hide all unplugged sockets on either side of group nodes if they have more than 2 unplugged sockets on either side")
	
	opt_fix_groups: BoolProperty(name="Fix .00x Group Nodes",
		default=True,
		description="If a group node's nodegroup ends in .00x but a nodegroup exists without it, replace the reference. If such nodegroup doesn't exist, rename it")

	opt_fix_tex_refs: BoolProperty(name="Fix .00x Texture References",
		default=True,
		description="If a texture node references a texture ending in .00x but a texture without it exists, change the reference. If such texture doesn't exist, rename it")

	opt_rename_nodes: BoolProperty(name="Rename Texture Nodes",
		default=False,
		description="Rename and relabel texture nodes to the filename of their image, without extension")

	opt_set_tex_widths: IntProperty(name="Set Texture Node Widths",
		default=400,
		description="Set all Texture Node widths to this value")

	# TODO: Can be added to the UI the same place as delete unused material slots.

	def execute(self, context):
		mats_done = []
		
		objs = context.selected_objects
		if(self.opt_objects=='Active'):
			objs = [context.object]
		elif(self.opt_objects=='All'):
			objs = bpy.data.objects
		
		for o in objs:
			for ms in o.material_slots:
				m = ms.material
				if(m==None or m in mats_done): continue
				if(self.opt_fix_name):
					# Clearing .00x from end of names
					if(('.' in m.name) and (m.name[-4] == '.')):
						existing = bpy.data.materials.get(m.name[:-4])
						if(not existing):
							m.name = m.name[:-4]
							print("...Renamed to " + m.name)
				# Cleaning nodetree
				if(m.use_nodes):
					clean_node_tree(m.node_tree, 
					delete_unused_nodes=self.opt_delete_unused_nodes, 
					fix_groups=self.opt_fix_groups, 
					center_nodes=True, 
					fix_tex_refs=self.opt_fix_tex_refs, 
					rename_tex_nodes=self.opt_rename_nodes, 
					hide_sockets=self.opt_hide_sockets, 
					min_sockets=2, 
					tex_width=self.opt_set_tex_widths)
				mats_done.append(m)
		return {'FINISHED'}

class CleanUpObjects(bpy.types.Operator):
	bl_idname = "object.clean_up"
	bl_label = "Clean Up Objects"
	bl_options = {'REGISTER', 'UNDO'}

	opt_objects: EnumProperty(name="Objects",
		items=[	('Active', 'Active', 'Active'),
				('Selected', 'Selected', 'Selected'),
				('All', 'All', 'All')
				],
		description="Which objects to operate on")

	opt_rename_data: BoolProperty(
		name="Rename Datas", 
		default=True, 
		description="If an object or armature is named 'Apple', its data will be renamed to 'Data_Apple'")
	
	opt_rename_uvs: BoolProperty(
		name="Rename UV Maps", 
		default=True, 
		description="If an object has only one UVMap, rename that to the default: 'UVMap'")

	opt_clean_material_slots: BoolProperty(
		name="Clean Material Slots",
		default=True,
		description="Delete material slots on selected objects that have no faces assigned")

	opt_rename_materials: BoolProperty(
		name="Fix .00x Material Names", 
		default=False, 
		description="Materials ending in .001 or similar will be attempted to be renamed")

	opt_clean_materials: BoolProperty(
		name="Clean Material Nodes",
		default=False,
		description="Remove unused nodes, resize and rename image nodes, hide unused group node sockets, and center nodes")

	opt_clean_vgroups: BoolProperty(name="Clear Unused Vertex Groups", 
		default=True, 
		description="Clear unused vertex groups")
	
	opt_create_mirror_vgroups: BoolProperty(
		name="Create Mirror Vertex Groups",
		default=True,
		description="If there is a Mirror modifier, create any missing left/right sided vertex groups")

	def execute(self, context):
		org_active = context.object

		objs = context.selected_objects
		if(self.opt_objects=='Active'):
			objs = [context.object]
		elif(self.opt_objects=='All'):
			objs = bpy.data.objects
		
		for obj in objs:
			if(type(obj) != bpy.types.Object or 
			(obj.type != 'MESH' and 
			obj.type != 'ARMATURE') ): continue

			bpy.ops.object.mode_set(mode="OBJECT")
			bpy.context.view_layer.objects.active = obj
			
			# Naming mesh/skeleton data blocks
			if(self.opt_rename_data):
				obj.data.name = "Data_" + obj.name
			
			# Closing and naming object constraints
			for c in obj.constraints:
				c.show_expanded = False
				if(c.type=='ACTION'):
					c.name = "Action_" + c.action.name
			
			# Closing modifiers
			for m in obj.modifiers:
				m.show_expanded = False

			# That's it for armatures.
			if(obj.type == 'ARMATURE'):
				continue
			
			# Wireframes
			obj.show_wire = False
			obj.show_all_edges = True

			# Sorting vertex groups by hierarchy
			bpy.ops.object.vertex_group_sort(sort_type='BONE_HIERARCHY')

			# Renaming UV map if there is only one
			if(self.opt_rename_uvs):
				if(len(obj.data.uv_layers) == 1):
					obj.data.uv_layers[0].name = "UVMap"
			
			# Creating missing vertex groups for Mirror modifier
			if(self.opt_create_mirror_vgroups):
				for m in obj.modifiers:
					if(m.type=='MIRROR'):
						vgs = obj.vertex_groups
						for vg in vgs:
							flippedName = utils.flip_name(vg.name)
							print(flippedName)
							if(flippedName not in vgs):
								obj.vertex_groups.new(name=flippedName)
						break
				
		# Deleting unused material slots
		if(self.opt_clean_material_slots):
			bpy.ops.object.delete_unused_material_slots(opt_objects=self.opt_objects)

		# Cleaning node trees
		bpy.ops.material.clean_up(opt_objects=self.opt_objects, 
			opt_fix_name=self.opt_rename_materials, 
			opt_delete_unused_nodes=self.opt_clean_materials, 
			opt_fix_groups=self.opt_clean_materials, 
			opt_fix_tex_refs=self.opt_clean_materials, 
			opt_rename_nodes=self.opt_clean_materials)

		if(self.opt_clean_vgroups):
			bpy.ops.object.delete_unused_vgroups(opt_objects=self.opt_objects)
		
		bpy.context.view_layer.objects.active = org_active
		return {'FINISHED'}

class CleanUpScene(bpy.types.Operator):
	bl_idname = "scene.clean_up"
	bl_label = "Clean Up Scene"
	bl_options = {'REGISTER', 'UNDO'}
	
	opt_freeze: BoolProperty(
		name="Freeze Operator", 
		default=False, 
		description="Freeze the operator to change settings without having to wait for the operator to run")
	
	opt_selected_only: BoolProperty(
		name="Selected Objects",
		default=True,
		description="DIsable to affect all objects")

	opt_removeUnusedMats: BoolProperty(
		name="Clean Material Slots", 
		default=True, 
		description="If a material has no faces assigned to it, it will be removed from the object. Objects with no faces are ignored")

	opt_clean_worlds: BoolProperty(
		name="Clean Worlds",
		default=True,
		description="Clean up World node setups")
	
	opt_clean_comp: BoolProperty(
		name="Clean Compositing",
		default=True,
		description="Clean up Compositing nodes")

	opt_clean_nodegroups: BoolProperty(
		name="Clean Nodegroups",
		default=True,
		description="Clean up Nodegroups")

	opt_clean_vgroups: BoolProperty(name="Clear Unused Vertex Groups", 
		default=True, 
		description="Clear unused vertex groups")

	opt_clean_material_slots: BoolProperty(
		name="Clean Material Slots",
		default=True,
		description="Delete material slots on selected objects that have no faces assigned")

	opt_rename_materials: BoolProperty(
		name="Fix .00x Material Names", 
		default=False, 
		description="Materials ending in .001 or similar will be attempted to be renamed")

	opt_clean_materials: BoolProperty(
		name="Clean Material Nodes",
		default=True,
		description="Remove unused nodes, resize and rename image nodes, hide unused group node sockets, and center nodes")

	def execute(self, context):
		if(self.opt_freeze):
			return {'FINISHED'}

		org_active = bpy.context.view_layer.objects.active

		if(self.opt_clean_worlds):
			for w in bpy.data.worlds:
				if(w.use_nodes):
					clean_node_tree(w.node_tree)

		if(self.opt_clean_comp):
			for s in bpy.data.scenes:
				if(s.use_nodes):
					clean_node_tree(s.node_tree)
		
		if(self.opt_clean_nodegroups):
			for nt in bpy.data.node_groups:
				clean_node_tree(nt)
		
		objects = 'Selected' if self.opt_selected_only else 'All'
		bpy.ops.object.clean_up(opt_objects=objects, 
			opt_clean_vgroups=self.opt_clean_vgroups, 
			opt_clean_material_slots=self.opt_clean_material_slots, 
			opt_rename_materials=self.opt_rename_materials, 
			opt_clean_materials=self.opt_clean_materials)
		
		bpy.context.view_layer.objects.active = org_active
		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	bpy.types.MATERIAL_MT_context_menu.prepend(DeleteUnusedMaterialSlots.draw)
	bpy.types.MESH_MT_vertex_group_context_menu.prepend(DeleteUnusedVGroups.draw_delete_unused)
	register_class(DeleteUnusedMaterialSlots)
	register_class(DeleteUnusedVGroups)
	register_class(CleanUpObjects)
	#register_class(CleanUpMeshes)
	#register_class(CleanUpArmatures)
	register_class(CleanUpMaterials)
	register_class(CleanUpScene)
	register_class(CleanUpAction)


def unregister():
	bpy.types.MATERIAL_MT_context_menu.remove(DeleteUnusedMaterialSlots.draw)
	bpy.types.TOPBAR_MT_file_import.remove(DeleteUnusedVGroups.draw_delete_unused)
	from bpy.utils import unregister_class
	unregister_class(DeleteUnusedMaterialSlots)
	unregister_class(DeleteUnusedVGroups)
	unregister_class(CleanUpObjects)
	#unregister_class(CleanUpMeshes)
	#unregister_class(CleanUpArmatures)
	unregister_class(CleanUpMaterials)
	unregister_class(CleanUpScene)
	unregister_class(CleanUpAction)
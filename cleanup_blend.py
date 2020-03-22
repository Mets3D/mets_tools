import bmesh
import bpy
from bpy.props import *
from . import utils
from math import pi

# TODO testing:
# Mirror modifier vertex groups getting spared when they should
# Oh, and also everything else.
# Make sure operators that are meant to operate on ALL objects work (including hidden shit, via utils.EnsureVisible)

class DeleteUnusedMaterialSlots(bpy.types.Operator):
	""" Delete material slots that have no faces assigned. """
	bl_idname = "object.delete_unused_material_slots"
	bl_label = "Delete Unused Material Slots"
	bl_options = {'REGISTER', 'UNDO'}

	opt_objects: EnumProperty(name="Objects",
		items=[	('Active', 'Active', 'Active'),
				('Selected', 'Selected', 'Selected'),
				('All', 'All', 'All')
				],
		default='Selected',
		description="Which objects to operate on")
	
	def execute(self, context):
		org_active = context.object

		objs = [context.object]
		if(self.opt_objects=='Selected'):
			objs = context.selected_objects
		elif(self.opt_objects=='All'):
			objs = bpy.data.objects

		for obj in objs:
			if(type(obj)!=bpy.types.Object or
				obj.type!='MESH' or
				len(obj.data.polygons)==0): continue

			utils.EnsureVisible.ensure(context, obj)
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.material_slot_remove_unused()
			utils.EnsureVisible.restore(obj)

		bpy.context.view_layer.objects.active = org_active

		return {'FINISHED'}

class DeleteUnusedVGroups(bpy.types.Operator):
	""" Delete unused vertex groups. Is aware of modifier fields that take vertex groups, including physics and Mirror modifier, and also checks shape key mask vertex groups. """
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
		description="Don't delete vertex groups that have any non-zero weights. Considers Mirror modifier.")
	
	@classmethod
	def poll(cls, context):
		return len(context.object.vertex_groups) > 0
	
	def draw_delete_unused(self, context):
		operator = self.layout.operator(DeleteUnusedVGroups.bl_idname, text="Delete Unused Groups", icon='X')
		operator.opt_objects = 'Active'

	def execute(self, context):
		org_active = context.object

		objs = [context.object]
		if(self.opt_objects=='Selected'):
			objs = context.selected_objects
		elif(self.opt_objects=='All'):
			objs = bpy.data.objects

		for obj in objs:
			if obj.type != 'MESH': continue
			if(len(obj.vertex_groups) == 0): continue
			
			utils.EnsureVisible.restore(obj)
			utils.EnsureVisible.ensure(context, obj)
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
							safe_groups.append(vg.name)

			for m in obj.modifiers:
				save_groups_by_attributes(m)
				if(hasattr(m, 'settings')):	#Physics modifiers
					save_groups_by_attributes(m.settings)

			# Save any vertex groups used by shape keys.
			if obj.data.shape_keys:
				for sk in obj.data.shape_keys.key_blocks:
					vg = obj.vertex_groups.get(sk.vertex_group)
					if(vg and vg.name not in safe_groups):
						safe_groups.append(vg.name)

			# Saving any vertex groups that correspond to a deform bone name
			for m in obj.modifiers:
				if(m.type == 'ARMATURE'):
					armature = m.object
					if armature is None:
						continue
					safe_groups.extend([b.name for b in armature.data.bones if b.use_deform])
				
			# Saving vertex groups that have any weights assigned to them, also considering mirror modifiers
			if(self.opt_save_nonzero_vgroups):
				for vg in obj.vertex_groups:	# For each vertex group
					for i in range(0, len(obj.data.vertices)):	# For each vertex
						try:
							vg.weight(i)							# If there's a weight assigned to this vert (else exception)
							if(vg.name not in safe_groups):
								safe_groups.append(vg.name)
								
								opp_name = utils.flip_name(vg.name)
								opp_group = obj.vertex_groups.get(opp_name)
								if(opp_group):
									safe_groups.append(opp_group.name)
								break
						except RuntimeError:
							continue
			
			# Clearing vertex groups that didn't get saved
			for vg in obj.vertex_groups:
				if(vg.name not in safe_groups):
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
		default=True, 
		description="Materials ending in .001 or similar will be attempted to be renamed")
		
	opt_delete_unused_nodes: BoolProperty(name="Clear Unused Nodes", 
		default=True, 
		description="Clear all nodes (except Frames) in all materials that aren't linked to an output node")
		
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
		default=True,
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
			if o.type!='MESH': continue
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
						delete_unused_nodes	= self.opt_delete_unused_nodes, 
						fix_groups			= self.opt_fix_groups, 
						center_nodes		= True, 
						fix_tex_refs		= self.opt_fix_tex_refs, 
						rename_tex_nodes	= self.opt_rename_nodes, 
						hide_sockets		= self.opt_hide_sockets, 
						min_sockets			= 2, 
						tex_width			= self.opt_set_tex_widths
					)
				mats_done.append(m)
		return {'FINISHED'}
	
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

class CleanUpObjects(bpy.types.Operator):
	bl_idname = "object.clean_up"
	bl_label = "Clean Up Objects"
	bl_options = {'REGISTER', 'UNDO'}

	opt_objects: EnumProperty(
		name		= "Objects",
		items		= [	('Active', 'Active', 'Active'),
						('Selected', 'Selected', 'Selected'),
						('All', 'All', 'All')
					],
		description = "Which objects to operate on")

	opt_rename_data: BoolProperty(
		name		= "Rename Datas", 
		default		= True, 
		description = "If an object or armature is named 'Apple', its data will be renamed to 'Data_Apple'")

	opt_rename_uvs: BoolProperty(
		name		= "Rename UV Maps", 
		default		= True, 
		description = "If an object has only one UVMap, rename that to the default: 'UVMap'")

	opt_create_mirror_vgroups: BoolProperty(
		name		= "Create Mirror Vertex Groups",
		default		= True,
		description = "If there is a Mirror modifier, create any missing left/right sided vertex groups")

	def execute(self, context):
		bpy.ops.object.mode_set(mode="OBJECT")
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

			utils.EnsureVisible.ensure(context, obj)
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
		
			utils.EnsureVisible.restore(obj)

		bpy.context.view_layer.objects.active = org_active
		
		return {'FINISHED'}

class CleanUpMeshes(bpy.types.Operator):
	""" Clean up meshes of selected objects. """
	bl_idname = "object.mesh_cleanup"
	bl_label = "Clean Up Mesh"
	bl_options = {'REGISTER', 'UNDO'}

	remove_doubles: bpy.props.BoolProperty(
		name="Remove Doubles",
		description="Enable remove doubles",
		default=False
	)
	quadrangulate: bpy.props.BoolProperty(
		name="Tris to Quads",
		description="Enable Tris to Quads (UV Seams enabledd)",
		default=False
	)
	weight_normals: bpy.props.BoolProperty(
		name="Weight Normals",
		description="Enable weighted normals",
		default=False
	)
	seams_from_islands: bpy.props.BoolProperty(
		name="Seams from Islands",
		description="Create UV seams based on UV islands",
		default=False
	)
	clear_unused_UVs: bpy.props.BoolProperty(
		name="Delete Unused UV Maps",
		description="If all UV verts' X coordinate is 0, the UV map will be deleted.",
		default=True
	)
	
	def execute(self, context):
		for obj in bpy.context.selected_objects:
			# Mode management
			org_active = bpy.context.object
			org_mode = org_active.mode
			org_selected = bpy.context.selected_objects[:]
			bpy.ops.object.mode_set(mode='OBJECT')
			bpy.ops.object.select_all(action='DESELECT')
			obj.select_set(True)

			
			utils.EnsureVisible.ensure(context, obj)
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.mode_set(mode='EDIT')
			
			# Unhide and deselect verts
			bpy.ops.mesh.reveal()
			bpy.ops.mesh.select_all(action='DESELECT')

			# Renaming shape key blocks
			if(obj.data.shape_keys is not None):
				obj.data.shape_keys.name = "Keys_" + obj.name

			# Setting auto-smooth to 180 is necessary so that splitnormals_clear() doesn't mark sharp edges
			obj.data.use_auto_smooth = True
			org_angle = obj.data.auto_smooth_angle
			obj.data.auto_smooth_angle = pi
			bpy.ops.mesh.customdata_custom_splitnormals_clear()
			obj.data.auto_smooth_angle = org_angle

			# Tris to Quads
			if(self.quadrangulate):
				bpy.ops.mesh.tris_convert_to_quads(shape_threshold=1.0472, uvs=True, materials=True)
			
			# Remove Doubles / Merge By Distance
			if(self.remove_doubles):
				bpy.ops.mesh.remove_doubles(threshold=0.0001)
			
			bpy.ops.object.mode_set(mode='OBJECT')
			if(self.weight_normals):
				bpy.ops.object.calculate_weighted_normals()
			bpy.ops.object.mode_set(mode='EDIT')
			
			### Removing useless UVMaps
			if(self.clear_unused_UVs):
				mesh = obj.data
				bm = bmesh.from_edit_mesh(mesh)

				# Invalid UV maps usually have all the verts on the top left or top right corner, so that's what we'll be checking for.
				# If all verts of a UV map have an X coordinate of 0, we're deleting it.

				for uv_idx in reversed(range(0, len(mesh.uv_layers))):			# For each UV layer (in reverse, since we're deleting)
					delet_this=True
					mesh.uv_layers.active_index = uv_idx
					bm.faces.ensure_lookup_table()
					for f in bm.faces:						# For each face
						for l in f.loops:					# For each loop(whatever that means)
							if(l[bm.loops.layers.uv.active].uv[0] != 0.0):	# If the loop's UVs first vert's x coord is NOT 0
								delet_this=False
								break
						if(delet_this==False):
							break
					if(delet_this):
						obj.data.uv_layers.remove(obj.data.uv_layers[uv_idx])
			
				bmesh.update_edit_mesh(mesh, True)
			
			# Seams from islands
			if(self.seams_from_islands):
				bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
			
			# Mode management
			bpy.ops.object.mode_set(mode='OBJECT')
			for o in org_selected:
				o.select_set(True)
				
			utils.EnsureVisible.restore(obj)
			bpy.context.view_layer.objects.active = org_active
			bpy.ops.object.mode_set(mode=org_mode)

		return {'FINISHED'}
		
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

def register():
	from bpy.utils import register_class
	bpy.types.MESH_MT_vertex_group_context_menu.prepend(DeleteUnusedVGroups.draw_delete_unused)
	register_class(DeleteUnusedMaterialSlots)
	register_class(DeleteUnusedVGroups)
	register_class(CleanUpMaterials)
	register_class(CleanUpObjects)
	register_class(CleanUpMeshes)

def unregister():
	bpy.types.TOPBAR_MT_file_import.remove(DeleteUnusedVGroups.draw_delete_unused)
	from bpy.utils import unregister_class
	unregister_class(DeleteUnusedMaterialSlots)
	unregister_class(DeleteUnusedVGroups)
	unregister_class(CleanUpMaterials)
	unregister_class(CleanUpObjects)
	unregister_class(CleanUpMeshes)
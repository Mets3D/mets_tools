import bmesh
import bpy
from bpy.props import *
from .. import utils
from math import pi

# TODO: Make sure operators that are meant to operate on ALL objects work 
# 	(including hidden shit, via utils.EnsureVisible)

"""

### Delete Unused Material Slots
This just calls the built-in "Remove Unused Slots" operator, except it can work on all selected objects, or all objects, instead of just the active object.

### Clean Up Materials
Deletes unused nodes, centers node graphs, fixes .00x names on materials and textures, sets names and labels for texture nodes, and sets width for texture nodes.

### Clean Up Objects
Renames object datas to "Data_ObjectName", UV maps to "UVMap" when there is only one, and creates missing vertex groups for Mirror modifier. (eg. when your mesh has a Mirror modifier and Leg.L vertex group exists but Leg.R doesn't)

### Clean Up Meshes
Unhide All, Removes Doubles, Quadrangulate(Compare UVs), Weight Normals, Seams From Islands.  
Also removes UV Maps that don't actually contain a UV layout (every UV vertex in default position)

"""


class EnsureVisible:
	"""Ensure an object is visible, then reset it to how it was before."""

	def __init__(self, obj):
		""" Ensure an object is visible, and create this small object to manage that object's visibility-ensured-ness. """
		self.obj_name = obj.name
		self.obj_hide = obj.hide_get()
		self.obj_hide_viewport = obj.hide_viewport
		self.temp_coll = None

		space = bpy.context.area.spaces.active
		if hasattr(space, 'local_view') and space.local_view:
			bpy.ops.view3d.localview()

		if not obj.visible_get():
			obj.hide_set(False)
			obj.hide_viewport = False

		if not obj.visible_get():
			# If the object is still not visible, we need to move it to a visible collection. To not break other scripts though, we should restore the active collection afterwards.
			active_coll = bpy.context.collection

			coll_name = "temp_visible"
			temp_coll = bpy.data.collections.get(coll_name)
			if not temp_coll:
				temp_coll = bpy.data.collections.new(coll_name)
			if coll_name not in bpy.context.scene.collection.children:
				bpy.context.scene.collection.children.link(temp_coll)

			if obj.name not in temp_coll.objects:
				temp_coll.objects.link(obj)

			self.temp_coll = temp_coll

			set_active_collection(active_coll)

	def restore(self):
		"""Restore visibility settings to their original state."""
		obj = bpy.data.objects.get(self.obj_name)
		if not obj: return

		obj.hide_set(self.obj_hide)
		obj.hide_viewport = self.obj_hide_viewport

		# Remove object from temp collection
		if self.temp_coll and obj.name in self.temp_coll.objects:
			self.temp_coll.objects.unlink(obj)

			# Delete temp collection if it's empty now.
			if len(self.temp_coll.objects) == 0:
				bpy.data.collections.remove(self.temp_coll)
				self.temp_coll = None

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

			visible = EnsureVisible(obj)
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.material_slot_remove_unused()
			visible.restore()

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

			visible = EnsureVisible(obj)
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
			if len(obj.vertex_groups)>1 and obj.visible_get():
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
							flippedName = bpy.utils.flip_name(vg.name)
							print(flippedName)
							if(flippedName not in vgs):
								obj.vertex_groups.new(name=flippedName)
						break
		
			visible.restore()

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
		description="If all UV verts' X coordinate is 0, the UV map will be deleted",
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

			
			visible = EnsureVisible(obj)
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
			
			visible.restore()
			bpy.context.view_layer.objects.active = org_active
			bpy.ops.object.mode_set(mode=org_mode)

		return {'FINISHED'}
		
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

classes = [
	DeleteUnusedMaterialSlots
	,CleanUpMaterials
	,CleanUpObjects
	,CleanUpMeshes
]

def register():
	from bpy.utils import register_class
	for c in classes:
		register_class(c)

def unregister():
	from bpy.utils import unregister_class
	for c in reversed(classes):
		unregister_class(c)
import os
import bpy
from mathutils import Matrix
from bpy.props import BoolProperty, StringProperty, EnumProperty

from .utils import EnsureVisible

widgets_visible = []
widget_items = []

def restore_all_widgets_visibility():
	global widgets_visible

	if widgets_visible != []:
		for w in widgets_visible[:]:
			try:
				w.restore()
			except:
				pass
	widgets_visible = []

def assign_to_collection(obj, collection):
	if not collection:
		return
	if obj.name not in collection.objects:
		collection.objects.link(obj)

def ensure_widget(context, wgt_name, ob_name="", collection=None):
	"""Load a single widget from Widgets.blend."""

	# If widget already exists locally, return it.
	wgt_ob = bpy.data.objects.get((wgt_name, None))
	if wgt_ob and ob_name in ["", wgt_ob.name]:
		return wgt_ob

	# Loading widget object from file.
	filename = "Widgets.blend"
	filedir = os.path.dirname(os.path.realpath(__file__))
	blend_path = os.path.join(filedir, filename)

	with bpy.data.libraries.load(blend_path) as (data_from, data_to):
		for o in data_from.objects:
			if o == wgt_name:
				data_to.objects.append(o)

	wgt_ob = bpy.data.objects.get((wgt_name, None))

	if not wgt_ob:
		print("WARNING: Failed to load widget: " + wgt_name)
		return

	if not collection:
		collection = context.scene.collection
	assign_to_collection(wgt_ob, collection)

	if ob_name:
		wgt_ob.name = ob_name

	return wgt_ob

def get_widget_list(self, context):
	"""This is needed because bpy.props.EnumProperty.items needs to be a dynamic list,
	which it can only be with a function callback."""
	global widget_items

	local_widgets = []
	for o in bpy.data.objects:
		if o.name.startswith("WGT"):
			ui_name = o.name.replace("WGT-", "").replace("_", " ")
			item = (o.name, ui_name, ui_name)
			local_widgets.append(item)

			for existing in widget_items:
				if existing == item:
					widget_items.remove(existing)
					break

	local_widgets.append(None)

	local_widgets.extend(widget_items)

	return local_widgets

def refresh_widget_list():
	"""Build a list of available custom shapes by checking inside Widgets.blend."""

	global widget_items
	widget_items = []

	filename = "Widgets.blend"
	filedir = os.path.dirname(os.path.realpath(__file__))
	blend_path = os.path.join(filedir, filename)

	with bpy.data.libraries.load(blend_path) as (data_from, data_to):
		for o in data_from.objects:
			if o.startswith("WGT-"):
				ui_name = o.replace("WGT-", "").replace("_", " ")
				widget_items.append((o, ui_name, ui_name))

	return widget_items

def transform_widget_to_bone(pb: bpy.types.PoseBone, select=False):
	"""Transform a pose bone's custom shape object to match the bone's visual transforms."""
	shape = pb.custom_shape
	if not shape:
		return

	if select:
		shape.select_set(True)

	transform_bone = pb
	if pb.custom_shape_transform:
		transform_bone = pb.custom_shape_transform

	# Step 1: Account for additional scaling from use_custom_shape_bone_size, 
	# which scales the shape by the bone length.
	scale = pb.custom_shape_scale_xyz.copy()
	if pb.use_custom_shape_bone_size:
		scale *= pb.bone.length

	# Step 2: Create a matrix from the custom shape translation, rotation
	# and this scale which already accounts for bone length.
	custom_shape_matrix = Matrix.LocRotScale(pb.custom_shape_translation, pb.custom_shape_rotation_euler, scale)

	# Step 3: Multiply the pose bone's world matrix by the custom shape matrix.
	final_matrix = transform_bone.matrix @ custom_shape_matrix

	# Step 4: Apply this matrix to the object. 
	# It should now match perfectly with the visual transforms of the pose bone, 
	# unless there is skew.
	shape.matrix_world = final_matrix

class POSE_OT_toggle_edit_widget(bpy.types.Operator):
	"""Toggle entering and leaving edit mode on a bone widget"""

	bl_idname = "pose.toggle_edit_widget"
	bl_label = "Toggle Edit Widget"
	bl_options = {'REGISTER', 'UNDO'}

	def update_name(self, context):
		if not self.use_custom_widget_name:
			self.widget_name = self.widget_shape
		else:
			# Use the active bone for the initial naming of the shape.
			self.widget_name = "WGT-" + context.active_pose_bone.name

	widget_name: StringProperty(name="Widget Name")
	widget_shape: EnumProperty(name="Widget Shape",
		items = get_widget_list,
		update = update_name
	)
	use_custom_widget_name: BoolProperty(name="Custom Name", update=update_name)

	@classmethod
	def poll(cls, context):
		if context.mode=='EDIT_MESH':
			if context.scene.widget_edit_armature != "":
				return True

		pb = context.active_pose_bone
		return context.mode=='POSE' and pb

	def invoke(self, context, event):
		if context.mode=='EDIT_MESH':
			return self.execute(context)

		refresh_widget_list()

		# If no selected bone has a bone shape, we will be creating one,
		# so ask for some input.
		ask_for_input = True
		for pb in context.selected_pose_bones:
			if pb.custom_shape:
				ask_for_input = False
				break

		if ask_for_input:
			self.update_name(context)
			wm = context.window_manager
			return wm.invoke_props_dialog(self)
		else:
			return self.execute(context)

	def draw(self, context):
		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False

		# We want to put a textbox and a toggle button underneath an enum drop-down
		# in a way that they align, which is sadly an absolute nightmare.
		row1 = layout.row()
		split1 = row1.split(factor=0.4)
		split1.alignment = 'RIGHT'
		split1.label(text="Widget Shape")
		split1.prop(self, 'widget_shape', text="")

		row2 = layout.row()
		split2 = row2.split(factor=0.4)
		split2.alignment = 'RIGHT'
		split2.label(text="Widget Name")
		row = split2.row(align=True)
		sub1 = row.row()
		sub1.enabled = self.use_custom_widget_name
		sub1.prop(self, 'widget_name', text="")

		sub2 = row.row()
		sub2.prop(self, 'use_custom_widget_name', text="", icon='GREASEPENCIL')

	def load_and_assign_widget(self, context, widget_name, ob_name=""):
		rig = context.object
		collection = context.scene.collection
		if hasattr(rig.data, 'cloudrig_parameters') and rig.data.cloudrig_parameters.widget_collection:
			# CloudRig integration: If we're on a metarig, use the widget collection.
			collection = rig.data.cloudrig_parameters.widget_collection
		shape = ensure_widget(context, widget_name, ob_name=ob_name, collection=collection)

		# Assign to selected bones.
		for pb in context.selected_pose_bones:
			pb.custom_shape = shape

	def execute_from_pose_mode(self, context):
		rig = context.object

		# If multiple bones are selected, make a list of their bone shapes.
		selected_pbs = context.selected_pose_bones[:]
		shapes = list(set([b.custom_shape for b in selected_pbs if b.custom_shape]))

		if shapes == []:
			# If none of the selected bones had a shape, user was prompted to pick one.
			self.load_and_assign_widget(context, self.widget_shape, self.widget_name)
			return

		# If bones with a shape were selected, make sure all previous shapes' 
		# visibility is restored before ensuring the current shapes' visibility.
		global widgets_visible
		restore_all_widgets_visibility()
		for s in shapes:
			widgets_visible.append(EnsureVisible(s))

		# Enter mesh edit mode on all shapes of selected bones.
		active_pb = context.active_pose_bone
		bpy.ops.object.mode_set(mode='OBJECT')
		
		context.scene.widget_edit_armature = rig.name
		context.view_layer.objects.active = shapes[0]
		bpy.ops.object.select_all(action='DESELECT')
		for pb in selected_pbs:
			if pb.custom_shape == active_pb.custom_shape and pb != active_pb:
				# Don't snap active bone's shape to some other bone.
				continue
			transform_widget_to_bone(pb, select=True)
			context.view_layer.update()

		bpy.ops.object.mode_set(mode='EDIT')

	def execute_from_edit_mode(self, context):
		"""Restore widget visibilities, rig selection state and mode."""
		bpy.ops.object.mode_set(mode='OBJECT')
		context.view_layer.objects.active = bpy.data.objects.get(context.scene.widget_edit_armature)
		context.scene.widget_edit_armature = ""
		bpy.ops.object.mode_set(mode='POSE')
		restore_all_widgets_visibility()

		context.scene.is_widget_edit_mode = not context.scene.is_widget_edit_mode
		context.view_layer.update()

	def execute(self, context):
		if context.mode == 'POSE':
			self.execute_from_pose_mode(context)
		elif context.mode == 'EDIT_MESH':
			self.execute_from_edit_mode(context)

		return {'FINISHED'}

class POSE_OT_make_widget_unique(bpy.types.Operator):
	"""Re-assign this bone's shape to a unique duplicate, so it can be edited without affecting other bones using the same widget"""

	bl_idname = "pose.make_widget_unique"
	bl_label = "Make Unique Duplicate of Widget"
	bl_options = {'REGISTER', 'UNDO'}

	new_name: StringProperty(name="Object Name")

	@classmethod
	def poll(cls, context):
		pb = context.active_pose_bone
		return context.mode=='POSE' and pb and pb.custom_shape

	def invoke(self, context, event):
		pb = context.active_pose_bone
		self.new_name = "WGT-"+pb.name
		
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def draw(self, context):
		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False

		layout.row().prop(self, "new_name")

	def execute(self, context):
		pb = context.active_pose_bone
		shape = pb.custom_shape
		rig = context.object

		mesh = bpy.data.meshes.new_from_object(shape)
		mesh.name = self.new_name
		obj = bpy.data.objects.new(self.new_name, mesh)
		for c in shape.users_collection:
			c.objects.link(obj)

		pb.custom_shape = obj

		bpy.ops.pose.toggle_edit_widget()

		return {'FINISHED'}

def register():
	bpy.utils.register_class(POSE_OT_toggle_edit_widget)
	bpy.utils.register_class(POSE_OT_make_widget_unique)

	bpy.types.Scene.is_widget_edit_mode = BoolProperty()
	bpy.types.Scene.widget_edit_armature = StringProperty()

def unregister():
	bpy.utils.unregister_class(POSE_OT_toggle_edit_widget)
	bpy.utils.unregister_class(POSE_OT_make_widget_unique)

	del bpy.types.Scene.is_widget_edit_mode
	del bpy.types.Scene.widget_edit_armature

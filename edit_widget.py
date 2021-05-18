import bpy
from bpy.props import BoolProperty, StringProperty
from .utils import EnsureVisible

widgets_visible = []

class POSE_OT_toggle_edit_widget(bpy.types.Operator):
	"""Toggle entering and leaving edit mode on a bone widget"""

	bl_idname = "pose.toggle_edit_widget"
	bl_label = "Toggle Edit Widget"
	bl_options = {'REGISTER', 'UNDO'}

	shape_name: StringProperty(name="Object Name")

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
		
		# If none of the selected bones have a bone shape, we will be creating one, so ask for a name!
		ask_for_name = True
		for pb in context.selected_pose_bones:
			if pb.custom_shape:
				ask_for_name = False
				break
		if ask_for_name:
			pb = context.active_pose_bone
			self.new_name = "WGT-"+pb.name
			wm = context.window_manager
			print("weeeee I'm retard")
			return wm.invoke_props_dialog(self)
		else:
			return self.execute(context)

	def draw(self, context):
		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False

		layout.row().prop(self, "shape_name")

	def execute(self, context):
		global widgets_visible

		if context.mode=='POSE':
			rig = context.object

			# If multiple bones are selected, list all their bone shapes.
			shapes = []
			for pb in context.selected_pose_bones:
				if pb.custom_shape:
					shapes.append(pb.custom_shape)
			# If none of the selected bones had a bone shape, create a new bone shape that is shared across all selected bones.
			# Use the active bone for naming the shape.
			if shapes==[]:
				name = self.shape_name
				mesh = bpy.data.meshes.new(name)
				shape = bpy.data.objects.new(name, mesh)
				# CloudRig integration! if we're on a metarig, use the widget collection.
				collection = context.scene.collection
				if hasattr(rig.data, 'cloudrig_parameters') and rig.data.cloudrig_parameters.widget_collection:
					collection = rig.data.cloudrig_parameters.widget_collection
				collection.objects.link(shape)
				# In case we just moved the shape to a disabled collection, make sure it's visible!
				if not shape.visible_get():
					widgets_visible = [EnsureVisible(shape)]
				for pb in context.selected_pose_bones:
					pb.custom_shape = shape

				bpy.ops.object.mode_set(mode='OBJECT')
				context.view_layer.objects.active = shape
				shapes.append(shape)
				bpy.ops.object.mode_set(mode='EDIT')
				bpy.ops.mesh.primitive_cube_add(location=(0,0,0), rotation=(0,0,0), scale=(0.5,0.5,0.5))
				bpy.ops.object.mode_set(mode='OBJECT')
				context.view_layer.objects.active = rig
				bpy.ops.object.mode_set(mode='POSE')
			# If one or bones with a bone shape were selected, make sure all previous shapes' visibility is restored before ensuring the current shapes' visibility.
			else:
				if widgets_visible != []:
					for w in widgets_visible[:]:
						try:
							w.restore()
						except:
							widgets_visible.remove(w)
				for s in shapes:
					widgets_visible.append(EnsureVisible(s))

			# Enter mesh edit mode on all bone shapes.
			# Bones without a bone shape are ignored for this case.

			pose_bones = list(context.selected_pose_bones)[:]
			active_pb = context.active_pose_bone
			bpy.ops.object.mode_set(mode='OBJECT')
			context.scene.widget_edit_armature = rig.name
			context.view_layer.objects.active = shapes[0]
			bpy.ops.object.select_all(action='DESELECT')
			for pb in pose_bones:
				shape = pb.custom_shape
				if shape == active_pb.custom_shape and pb != active_pb: continue
				shape.select_set(True)

				transform_bone = pb
				if pb.custom_shape_transform:
					transform_bone = pb.custom_shape_transform

				shape.matrix_world = transform_bone.matrix
				if pb.use_custom_shape_bone_size:
					shape.scale = [pb.length*pb.custom_shape_scale]*3
				else:
					shape.scale = [pb.custom_shape_scale]*3
			bpy.ops.object.mode_set(mode='EDIT')
		
		elif context.mode=='EDIT_MESH':
			# Restore everything to how it was before we entered edit mode on the widgets.
			bpy.ops.object.mode_set(mode='OBJECT')
			context.view_layer.objects.active = bpy.data.objects.get(context.scene.widget_edit_armature)
			context.scene.widget_edit_armature = ""
			bpy.ops.object.mode_set(mode='POSE')
			if widgets_visible != []:
				for w in widgets_visible:
					w.restore()
			widgets_visible = []

		context.scene.is_widget_edit_mode = not context.scene.is_widget_edit_mode

		return {'FINISHED'}

class POSE_OT_make_widget_unique(bpy.types.Operator):
	"""Re-assign this bone's shape to a unique duplicate, so it can be edited without affecting other bones using the same widget."""

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

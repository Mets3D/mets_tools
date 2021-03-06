import bpy
from bpy.props import BoolProperty, StringProperty
from .utils import EnsureVisible

widget_visible = None

class POSE_OT_toggle_edit_widget(bpy.types.Operator):
	"""Toggle entering and leaving edit mode on a bone widget"""

	bl_idname = "pose.toggle_edit_widget"
	bl_label = "Toggle Edit Widget"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		if context.mode=='EDIT_MESH':
			if context.scene.widget_edit_armature != "":
				return True

		pb = context.active_pose_bone
		if context.mode=='POSE' and pb:
			return pb.custom_shape

	def execute(self, context):
		global widget_visible

		if context.mode=='POSE':
			pb = context.active_pose_bone
			shape = pb.custom_shape
			if widget_visible:
				widget_visible.restore()
			widget_visible = EnsureVisible(shape)
			bpy.ops.object.mode_set(mode='OBJECT')
			context.scene.widget_edit_armature = context.object.name
			context.view_layer.objects.active = shape
			shape.matrix_world = pb.matrix
			if pb.use_custom_shape_bone_size:
				shape.scale = [pb.length*pb.custom_shape_scale]*3
			else:
				shape.scale = [pb.custom_shape_scale]*3
			bpy.ops.object.mode_set(mode='EDIT')
		elif context.mode=='EDIT_MESH':
			bpy.ops.object.mode_set(mode='OBJECT')
			context.view_layer.objects.active = bpy.data.objects.get(context.scene.widget_edit_armature)
			context.scene.widget_edit_armature = ""
			bpy.ops.object.mode_set(mode='POSE')
			if widget_visible:
				widget_visible.restore()
			widget_visible = None
		
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
		if context.mode=='POSE' and pb:
			return pb.custom_shape

	def invoke(self, context, event):
		pb = context.active_pose_bone
		shape = pb.custom_shape
		self.new_name = shape.name
		
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def draw(self, context):
		pb = context.active_pose_bone
		shape = pb.custom_shape

		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False

		layout.row().prop(self, "new_name")

	def execute(self, context):
		pb = context.active_pose_bone
		shape = pb.custom_shape

		duplicate_mesh = bpy.data.meshes.new_from_object(shape)
		duplicate_obj = bpy.data.objects.new(self.new_name, duplicate_mesh)
		pb.custom_shape = duplicate_obj

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

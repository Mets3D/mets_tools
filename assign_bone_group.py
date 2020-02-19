import bpy
from bpy.props import *

# This is meant as a replacement for the built-in Ctrl+G bone group menu in pose mode.

# These are the bone group color presets from Blender default (dark) theme.
# PresetName : [(vec3 normal), (vec3 select), (vec3 active)]
presets = {
	'PRESET01' : [(0.6039215922355652, 0.0, 0.0), (0.7411764860153198, 0.06666667014360428, 0.06666667014360428), (0.9686275124549866, 0.03921568766236305, 0.03921568766236305)],
	'PRESET02' : [(0.9686275124549866, 0.250980406999588, 0.0941176563501358), (0.9647059440612793, 0.4117647409439087, 0.07450980693101883), (0.9803922176361084, 0.6000000238418579, 0.0)],
	'PRESET03' : [(0.11764706671237946, 0.5686274766921997, 0.03529411926865578), (0.3490196168422699, 0.7176470756530762, 0.04313725605607033), (0.5137255191802979, 0.9372549653053284, 0.11372549831867218)],
	'PRESET04' : [(0.03921568766236305, 0.21176472306251526, 0.5803921818733215), (0.21176472306251526, 0.40392160415649414, 0.874509871006012), (0.3686274588108063, 0.7568628191947937, 0.9372549653053284)],
	'PRESET05' : [(0.6627451181411743, 0.16078431904315948, 0.30588236451148987), (0.7568628191947937, 0.2549019753932953, 0.41568630933761597), (0.9411765336990356, 0.364705890417099, 0.5686274766921997)],
	'PRESET06' : [(0.26274511218070984, 0.0470588281750679, 0.4705882668495178), (0.3294117748737335, 0.22745099663734436, 0.6392157077789307), (0.529411792755127, 0.3921568989753723, 0.8352941870689392)],
	'PRESET07' : [(0.1411764770746231, 0.4705882668495178, 0.3529411852359772), (0.2352941334247589, 0.5843137502670288, 0.4745098352432251), (0.43529415130615234, 0.7137255072593689, 0.6705882549285889)],
	'PRESET08' : [(0.29411765933036804, 0.4392157196998596, 0.4862745404243469), (0.41568630933761597, 0.5254902243614197, 0.5686274766921997), (0.6078431606292725, 0.760784387588501, 0.803921639919281)],
	'PRESET09' : [(0.9568628072738647, 0.7882353663444519, 0.0470588281750679), (0.9333333969116211, 0.760784387588501, 0.21176472306251526), (0.9529412388801575, 1.0, 0.0)],
	'PRESET10' : [(0.11764706671237946, 0.125490203499794, 0.1411764770746231), (0.2823529541492462, 0.2980392277240753, 0.33725491166114807), (1.0, 1.0, 1.0)],
	'PRESET11' : [(0.43529415130615234, 0.18431372940540314, 0.41568630933761597), (0.5960784554481506, 0.2705882489681244, 0.7450980544090271), (0.8274510502815247, 0.1882353127002716, 0.8392157554626465)],
	'PRESET12' : [(0.4235294461250305, 0.5568627715110779, 0.13333334028720856), (0.49803924560546875, 0.6901960968971252, 0.13333334028720856), (0.7333333492279053, 0.9372549653053284, 0.35686275362968445)],
	'PRESET13' : [(0.5529412031173706, 0.5529412031173706, 0.5529412031173706), (0.6901960968971252, 0.6901960968971252, 0.6901960968971252), (0.8705883026123047, 0.8705883026123047, 0.8705883026123047)],
	'PRESET14' : [(0.5137255191802979, 0.26274511218070984, 0.14901961386203766), (0.545098066329956, 0.3450980484485626, 0.06666667014360428), (0.7411764860153198, 0.41568630933761597, 0.06666667014360428)],
	'PRESET15' : [(0.0313725508749485, 0.19215688109397888, 0.05490196496248245), (0.1098039299249649, 0.26274511218070984, 0.04313725605607033), (0.2039215862751007, 0.38431376218795776, 0.16862745583057404)],
}

class AssignBoneGroup(bpy.types.Operator):
	"""Assign or remove bone groups from the selected pose bones."""
	bl_idname = "armature.assign_group"
	bl_label = "Assign Selected Bones to Bone Group"
	bl_options = {'REGISTER', 'UNDO'}

	bone_group: StringProperty(name="Bone Group", default="Group")
	operation: EnumProperty(
		name="Operation", 
		items=(
			('ASSIGN', "Existing", "Assign selected bones to an existing group."),
			('NEW', "New", "Assign selected bones to a new group."),
			('REMOVE', "None", "Remove selected bones from their current group."),
		),
		default = 'ASSIGN'
	)

	color_normal: FloatVectorProperty(name="Regular", description="Color used for unselected bones", subtype='COLOR', min=0, max=1)
	color_selected: FloatVectorProperty(name="Selected", description="Color used for selected bones", subtype='COLOR', min=0, max=1)
	color_active: FloatVectorProperty(name="Active", description="Color used for the active bone", subtype='COLOR', min=0, max=1)

	def update_colors(self, context):
		self.color_normal = presets[self.color_preset][0]
		self.color_selected = presets[self.color_preset][1]
		self.color_active = presets[self.color_preset][2]

	color_preset: EnumProperty(
		name="Color Preset",
		items=(
			('DEFAULT', "Default Colors", ""),
			('PRESET01', "01 - Red", ""),
			('PRESET02', "02 - Orange", ""),
			('PRESET03', "03 - Green", ""),
			('PRESET04', "04 - Blue", ""),
			('PRESET05', "05 - Salmon Pink", ""),
			('PRESET06', "06 - Purple", ""),
			('PRESET07', "07 - Aqua", ""),
			('PRESET08', "08 - Cloudy", ""),
			('PRESET09', "09 - Yellow", ""),
			('PRESET10', "10 - Gray", ""),
			('PRESET11', "11 - Pink", ""),
			('PRESET12', "12 - Lime", ""),
			('PRESET13', "13 - White", ""),
			('PRESET14', "14 - Brown", ""),
			('PRESET15', "15 - Dark Green", ""),
		),
		default = 'DEFAULT',
		update=update_colors
	)

	@classmethod
	def poll(cls, context):
		return (context.object and context.object.type == 'ARMATURE' and context.object.mode=='POSE')

	def draw(self, context):
		layout = self.layout

		layout.prop(self, "operation", expand=True)

		if self.operation == 'REMOVE': return

		layout.separator()

		if self.operation == 'ASSIGN':
			layout.prop_search(self, "bone_group", context.object.pose, "bone_groups", text="Bone Group")
		elif self.operation == 'NEW':
			layout.prop(self, "bone_group", text="Name")

		# Draw color options of the chosen group
		if self.operation == 'ASSIGN' and self.bone_group != "":
			group = context.object.pose.bone_groups.get(self.bone_group)
			
			split = layout.split()
			split.active = (context.object.proxy is None)

			col = split.column()
			col.prop(group, "color_set")
			if group.color_set:
				col = split.column()
				sub = col.row(align=True)
				sub.enabled = group.is_custom_color_set  # only custom colors are editable
				sub.prop(group.colors, "normal", text="")
				sub.prop(group.colors, "select", text="")
				sub.prop(group.colors, "active", text="")
		
		# Draw color options for creating a new group
		if self.operation == 'NEW':
			split = layout.split()
			split.active = (context.object.proxy is None)

			col = split.column()
			col.prop(self, "color_preset")

			col = split.column()
			sub = col.row(align=True)
			if self.color_preset!='DEFAULT':
				#sub.enabled = group.is_custom_color_set  # only custom colors are editable
				sub.prop(self, "color_normal", text="")
				sub.prop(self, "color_selected", text="")
				sub.prop(self, "color_active", text="")
	
	def invoke(self, context, event):
		if context.active_pose_bone and context.active_pose_bone.bone_group:
			self.bone_group = context.active_pose_bone.bone_group.name
		
		if len(context.object.pose.bone_groups) == 0:
			self.operation = 'NEW'
		
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def execute(self, context):
		bones = context.selected_pose_bones
		group = context.object.pose.bone_groups.get(self.bone_group)
		
		if self.operation == 'ASSIGN':
			if not group: return {'CANCELLED'}

			for b in bones:
				b.bone_group = group
		
		if self.operation == 'NEW':
			group = context.object.pose.bone_groups.new(name=self.bone_group)
			group.color_set = 'CUSTOM'
			group.colors.normal = self.color_normal
			group.colors.select = self.color_selected
			group.colors.active = self.color_active

			for b in bones:
				b.bone_group = group

		if self.operation == 'REMOVE':
			for b in bones:
				b.bone_group = None

		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	register_class(AssignBoneGroup)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(AssignBoneGroup)
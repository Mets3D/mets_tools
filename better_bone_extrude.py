import bpy
from bpy.utils import flip_name

class Better_Bone_Extrude(bpy.types.Operator):
    bl_idname = "armature.better_extrude"
    bl_description = "Extrude a bone and increment its name"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Better Extrude Bone"

    @classmethod
    def poll(cls, context):
        b = context.active_bone
        return context.mode=='EDIT_ARMATURE' and b \
            and b.select_head != b.select_tail \
            and len(context.selected_bones)==0

    def execute(self, context):
        rig = context.object
        source_bone = context.active_bone
        name = source_bone.name
        # Increment LAST number in the name.
        new_name = ""
        incremented = False
        for i, c in enumerate(list(reversed(name))):
            if not incremented and c.isdecimal():
                num = int(c)
                if num < 9:
                    new_name = str(num+1) + new_name
                    incremented = True
                    continue
            new_name = c+new_name

        # Extrude it!
        bpy.ops.armature.extrude_move()

        if rig.data.use_mirror_x:
            opp_bone = rig.data.edit_bones.get(flip_name(context.active_bone.name))
            if opp_bone:
                opp_bone.name = flip_name(new_name)

        # Fix the name!
        new_bone = context.active_bone
        new_bone.name = new_name

        # This should happen on its own but it doesn't...?
        new_bone.select_tail = True

        return {'FINISHED'}

def register():
    bpy.utils.register_class(Better_Bone_Extrude)

def unregister():
    bpy.utils.unregister_class(Better_Bone_Extrude)

import bpy
from bpy.utils import flip_name
import re

def increment_name(name: str, increment: int) -> str:
    # Increment LAST number in the name.
    # Negative numbers will be clamped to 0.
    # Digit length will be preserved, so 10 will decrement to 09.
    # 99 will increment to 100, not 00.

    numbers_in_name = re.findall(r'\d+', name)
    if not numbers_in_name:
        return name + str(max(0, increment))
    
    last = numbers_in_name[-1]
    incremented = str( max(0, int(last) + increment) ).zfill(len(last))
    split = name.rsplit(last, 1)
    return incremented.join(split)

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
        source_bone.name = increment_name(source_bone.name)

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

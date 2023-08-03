"""
This is currently intended to be used with the Pie Menu Editor add-on.
In future, we could create our own pie menu and hotkey UI.
"""

import bpy
from bpy.types import Operator, Object
from bpy.props import BoolProperty, PointerProperty
from typing import List


def get_active_bone(context):
    if context.object.mode == 'POSE':
        return context.active_pose_bone.bone
    elif context.object.mode == 'EDIT':
        return context.active_bone


def get_selected_bones(context, exclude_active=False) -> List[bpy.types.Bone]:
    if not context.object or not context.object.type == 'ARMATURE':
        return []
    bones = []
    if context.object.mode == 'POSE':
        bones = [pb.bone for pb in context.selected_pose_bones]
    elif context.object.mode == 'EDIT':
        bones = context.selected_editable_bones

    if exclude_active:
        bones.remove(get_active_bone(context))

    return bones


class GenericBoneOperator:
    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == 'ARMATURE'
            and context.object.mode in {'POSE', 'EDIT'}
        )

    @staticmethod
    def get_selected_pose_bones(context):
        if context.object.mode == 'POSE':
            return context.selected_pose_bones
        elif context.object.mode == 'EDIT':
            return [
                context.object.data.bones.get(eb.name)
                for eb in context.selected_editable_bones
                if eb.name in context.object.data.bones
            ]

    def affect_bones(self, context) -> List[str]:
        """Returns list of bone names that were actually affected."""
        rig = context.object
        mode = rig.mode
        if mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        affected_bones = []
        for eb in get_selected_bones(context):
            name = eb.name
            was_affected = self.affect_bone(eb)
            if was_affected:
                affected_bones.append(name)

        bpy.ops.object.mode_set(mode=mode)
        return affected_bones

    def affect_bone(self, eb) -> bool:
        """Return the bone's name if it was affected"""
        raise NotImplementedError


class POSE_OT_disconnect_bones(GenericBoneOperator, Operator):
    """Disconnect selected bones"""

    bl_idname = "pose.disconnect_selected"
    bl_label = "Disconnect Selected Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        for b in get_selected_bones(context):
            if b.use_connect:
                return True
        else:
            return False

    def affect_bone(self, eb) -> bool:
        if eb.parent:
            eb.parent = None
            return True
        return False

    def execute(self, context):
        affected = self.affect_bones(context)
        plural = "s" if len(affected) != 1 else ""
        self.report({'INFO'}, f'Disconnected {len(affected)} bone{plural}.')
        return {'FINISHED'}


class POSE_OT_unparent_bones(GenericBoneOperator, Operator):
    """Unparent selected bones"""

    bl_idname = "pose.unparent_selected"
    bl_label = "Unparent Selected Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        for b in get_selected_bones(context):
            if b.parent:
                return True

        return False

    def affect_bone(self, eb) -> bool:
        if eb.parent:
            eb.parent = None
            return True
        return False

    def execute(self, context):
        affected = self.affect_bones(context)
        plural = "s" if len(affected) != 1 else ""
        self.report({'INFO'}, f'Unparented {len(affected)} bone{plural}.')
        return {'FINISHED'}


class POSE_OT_delete_bones(GenericBoneOperator, Operator):
    """Delete selected bones"""

    bl_idname = "pose.delete_selected"
    bl_label = "Delete Selected Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def affect_bone(self, eb) -> bool:
        eb.id_data.edit_bones.remove(eb)
        return True

    def execute(self, context):
        affected = self.affect_bones(context)
        plural = "s" if len(affected) != 1 else ""
        self.report({'INFO'}, f'Deleted {len(affected)} bone{plural}.')
        return {'FINISHED'}


class POSE_OT_parent_active_to_all_selected(GenericBoneOperator, Operator):
    """Parent active bone to all selected bones using Armature constraint"""

    bl_idname = "pose.parent_active_to_all_selected"
    bl_label = "Parent Active to All Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        return len(get_selected_bones(context)) > 1 and get_active_bone(context)

    def execute(self, context):
        mode = context.object.mode
        if mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        context.active_bone.parent = None
        bpy.ops.object.mode_set(mode=mode)

        active_bone = get_active_bone(context)

        rig = context.object
        active_pb = rig.pose.bones[active_bone.name]

        # If there is an existing Armature constraint, preserve it. (For position in stack, name, and settings)
        arm_con = None
        for c in active_pb.constraints:
            if c.type == 'ARMATURE':
                c.targets.clear()
                arm_con = c
                break
        if not arm_con:
            arm_con = active_pb.constraints.new(type='ARMATURE')

        for bone in get_selected_bones(context, exclude_active=True):
            target = arm_con.targets.new()
            target.target = rig
            target.subtarget = bone.name

        plural = "s" if len(arm_con.targets) != 1 else ""
        self.report(
            {'INFO'},
            f'Parented "{active_pb.name}" to {len(arm_con.targets)} bone{plural} using Armature constraint.',
        )
        return {'FINISHED'}


class POSE_OT_parent_selected_to_active(GenericBoneOperator, Operator):
    """Parent selected bones to the active one"""

    bl_idname = "pose.parent_selected_to_active"
    bl_label = "Parent Selected Bones To Active"
    bl_options = {'REGISTER', 'UNDO'}

    use_connect: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        return len(get_selected_bones(context)) > 1 and get_active_bone(context)

    def execute(self, context):
        rig = context.object
        mode = rig.mode
        bpy.ops.object.mode_set(mode='EDIT')
        parent = get_active_bone(context)
        parent_name = parent.name

        bones_to_parent = get_selected_bones(context, exclude_active=True)
        for eb in bones_to_parent:
            if parent.parent == eb:
                parent.use_connect = False
                parent.parent = eb.parent
            if (eb.head - parent.tail).length > 0.0001:
                eb.use_connect = False
            if self.use_connect:
                eb.use_connect = True
            eb.parent = parent

        bpy.ops.object.mode_set(mode=mode)
        plural = "s" if len(bones_to_parent) != 1 else ""
        self.report(
            {'INFO'},
            f'Parented {len(bones_to_parent)} bone{plural} to "{parent_name}".',
        )
        return {'FINISHED'}


class POSE_OT_parent_object_to_selected_bones(Operator):
    """Parent object to selected bones"""

    bl_idname = "pose.parent_object_to_selected_bones"
    bl_label = "Parent Selected Objects to Selected Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            len(get_selected_bones(context)) > 0 and len(context.selected_objects) > 1
        )

    def execute(self, context):
        rig = context.object
        target_objs = [o for o in context.selected_objects if o != rig]
        if not target_objs:
            return {'CANCELLED'}

        bones = get_selected_bones(context, exclude_active=False)
        for obj in target_objs:
            arm_con = None
            for c in obj.constraints:
                if c.type == 'ARMATURE':
                    c.targets.clear()
                    arm_con = c
                    break
            if not arm_con:
                arm_con = obj.constraints.new(type='ARMATURE')

            for bone in bones:
                target = arm_con.targets.new()
                target.target = rig
                target.subtarget = bone.name
            obj.parent = rig
            obj.parent_type = 'OBJECT'

        objs = obj.name if len(target_objs) == 1 else f"{len(target_objs)} objects"
        plural_bone = 's' if len(bones) != 1 else ''
        self.report({'INFO'}, f'Parented "{objs}" to {len(bones)} bone{plural_bone}.')
        return {'FINISHED'}


registry = [
    POSE_OT_disconnect_bones,
    POSE_OT_unparent_bones,
    POSE_OT_delete_bones,
    POSE_OT_parent_active_to_all_selected,
    POSE_OT_parent_selected_to_active,
    POSE_OT_parent_object_to_selected_bones,
]

# Written by ChatGPT.

import bpy


class AddVertexWeightsToActiveOperator(bpy.types.Operator):
    """Add vertex weights of all selected pose bones to the active one"""

    bl_idname = "object.add_vertex_weights_to_active"
    bl_label = "Add Vertex Weights to Active"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            cls.poll_message_set("No active object.")
            return False
        if obj.type != 'MESH':
            cls.poll_message_set("The active object is not a mesh.")
            return False
        if context.mode != 'PAINT_WEIGHT':
            cls.poll_message_set("The mode must be Weight Paint.")
            return False
        armature_modifier = next(
            (mod for mod in obj.modifiers if mod.type == 'ARMATURE'), None
        )
        if not armature_modifier:
            cls.poll_message_set("The mesh must have an armature modifier.")
            return False
        if not context.selected_pose_bones:
            cls.poll_message_set("No pose bones selected.")
            return False
        if not context.active_pose_bone:
            cls.poll_message_set("No active pose bone.")
            return False
        if context.active_pose_bone not in context.selected_pose_bones:
            cls.poll_message_set("The active bone is not in the selected bones.")
            return False
        return True

    def execute(self, context):
        obj = context.active_object
        active_bone = context.active_pose_bone
        active_bone_name = active_bone.name
        pose_bones = context.selected_pose_bones
        pose_bones = [bone for bone in pose_bones if bone.name != active_bone_name]
        vertex_groups = obj.vertex_groups
        active_vertex_group = vertex_groups.get(active_bone_name)

        for bone in pose_bones:
            vertex_group = vertex_groups.get(bone.name)
            if not vertex_group:
                continue

            weights_to_add = {}
            for vertex in obj.data.vertices:
                for group in vertex.groups:
                    if group.group == vertex_group.index:
                        if vertex.index not in weights_to_add:
                            weights_to_add[vertex.index] = 0.0
                        weights_to_add[vertex.index] += group.weight

            for vertex_index, weight in weights_to_add.items():
                active_vertex_group.add([vertex_index], weight, 'ADD')

            vertex_groups.remove(vertex_group)

        self.report(
            {'INFO'},
            "Vertex weights successfully added to the active bone and vertex groups removed.",
        )
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(AddVertexWeightsToActiveOperator.bl_idname)


def register():
    bpy.utils.register_class(AddVertexWeightsToActiveOperator)
    bpy.types.VIEW3D_MT_paint_weight.append(menu_func)


def unregister():
    bpy.utils.unregister_class(AddVertexWeightsToActiveOperator)
    bpy.types.VIEW3D_MT_paint_weight.remove(menu_func)


if __name__ == "__main__":
    register()

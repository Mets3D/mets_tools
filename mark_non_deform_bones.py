import bpy

def has_vertex_group(obj, group_name):
    """Check if the given object has a vertex group with the specified name."""
    return group_name in obj.vertex_groups

class OBJECT_OT_uncheck_deform_bones(bpy.types.Operator):
    """Toggle the 'use_deform' property of bones if they don't deform any meshes"""
    bl_idname = "object.uncheck_deform_bones"
    bl_label = "Uncheck Deform Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        mesh_objects = [obj for obj in armature.children if obj.type == 'MESH']
        
        if not mesh_objects:
            self.report({'WARNING'}, "No child mesh objects found.")
            return {'CANCELLED'}

        for bone in armature.data.bones:
            if bone.use_deform:
                bone_has_group = any(
                    has_vertex_group(mesh_obj, bone.name) for mesh_obj in mesh_objects
                )
                if not bone_has_group:
                    bone.use_deform = False
                    print("Set bone to non-deform: ", bone.name)
        
        self.report({'INFO'}, "Updated bone deform properties.")
        return {'FINISHED'}

registry = [OBJECT_OT_uncheck_deform_bones]

def draw_uncheck_def_bones(self, context):
    layout = self.layout
    layout.operator(OBJECT_OT_uncheck_deform_bones.bl_idname, icon='GROUP_BONE')

registry = [OBJECT_OT_uncheck_deform_bones]

def register():
    bpy.types.VIEW3D_MT_pose.append(draw_uncheck_def_bones)

def unregister():
    bpy.types.VIEW3D_MT_pose.remove(draw_uncheck_def_bones)

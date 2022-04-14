import bpy

class Parent_With_Armature_Constraint(bpy.types.Operator):
    bl_idname = "object.parent_with_armature_constraint"
    bl_description = "Parent those selected objects which have no parent to the active object or bone, using an armature constraint. Existing armature constraints will be removed first."
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Parent With Armature Constraint"

    @classmethod
    def poll(cls, context):
        return context.active_bone

    def execute(self, context):
        selected_obs = context.selected_objects
        active_ob = context.object
        active_bone = context.active_bone

        # If object has armature constraint, remove it and unparent it completely.
        for o in selected_obs:
            if o == active_ob: continue
            for c in o.constraints:
                if c.type == 'ARMATURE':
                    o.constraints.remove(c)
                    o.parent = None
                    break

        # Find objects with no parent.
        parentless_obs = [o for o in selected_obs if not o.parent]

        # Parent these objects to the active object, and,
        # create an Armature constraint targetting the active bone.
        for o in parentless_obs:
            if o == active_ob:
                continue
            o.parent = active_ob

            for c in o.constraints:
                if c.type == 'ARMATURE':
                    o.constraints.remove(c)
                    break

            arm_con = o.constraints.new(type='ARMATURE')
            target = arm_con.targets.new()
            target.target = active_ob
            target.subtarget = active_bone.name

        return {'FINISHED'}

def register():
    bpy.utils.register_class(Parent_With_Armature_Constraint)

def unregister():
    bpy.utils.unregister_class(Parent_With_Armature_Constraint)

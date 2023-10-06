import bpy
from bpy.types import Operator

class POSE_OT_create_transform_constraint(Operator):
    """Create transform constraint on the active bone, targeting the selected one, based on current local transforms of the active bone"""

    bl_idname = "pose.create_transform_constraint"
    bl_label = "Create Transform Constraint"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object and 
            context.active_object.type == 'ARMATURE' and 
            context.mode == 'POSE' and
            context.active_pose_bone and
            context.active_pose_bone in context.selected_pose_bones and
            len(context.selected_pose_bones) == 2
        )
    
    def execute(self, context):
        active = context.active_pose_bone
        target = [pb for pb in context.selected_pose_bones if pb != active][0]

        if any([pb.rotation_mode in {'QUATERNION', 'AXIS_ANGLE'} for pb in {active, target}]):
            self.report({'ERROR'}, "Bones must have Euler rotation mode.")
            return {'CANCELLED'}

        con = active.constraints.new(type='TRANSFORM')
        con.target = target.id_data
        con.subtarget = target.name
        con.target_space = con.owner_space = 'LOCAL'

        def get_index_of_largest(iterable):
            largest = (0, 0)
            for i, value in enumerate(iterable):
                if abs(value) > largest[1]:
                    largest = (i, abs(value))
            return largest[0]

        ### Set Map From values

        # Guess which transform type to map from; The one with significant values.
        if abs(sum(target.rotation_euler)) > 0.0001:
            con.map_from = 'ROTATION'
            source_axis = get_index_of_largest(active.rotation_euler)
        elif abs(sum(target.location)) > 0.00001:
            con.map_from = 'LOCATION'
            source_axis = get_index_of_largest(active.location)
        elif abs(sum(target.scale) -3) > 0.0001:
            con.map_from = 'SCALE'
            source_axis = get_index_of_largest(active.scale)
        else:
            source_axis = 0

        axes = "xyz"
        axis = axes[source_axis]

        if con.map_from == 'LOCATION':
            transf_value = getattr(target.location, axis)
            min_max = "max" if transf_value > 0 else "min"
            setattr(con, f"from_{min_max}_{axis}", transf_value)
        elif con.map_from == 'ROTATION':
            transf_value = getattr(target.rotation_euler, axis)
            min_max = "max" if transf_value > 0 else "min"
            setattr(con, f"from_{min_max}_{axis}_rot", transf_value)
        elif con.map_from == 'SCALE':
            transf_value = getattr(target.scale, axis)
            min_max = "max" if transf_value > 1 else "min"
            setattr(con, f"from_{min_max}_{axis}_scale", transf_value)

        ### Set Map To values

        # Guess which transform type to map to (Although, perhaps all 3?)
        if abs(sum(active.rotation_euler)) > 0.0001:
            con.map_to = 'ROTATION'
        elif abs(sum(active.location)) > 0.00001:
            con.map_to = 'LOCATION'
        elif abs(sum(active.scale) -3) > 0.0001:
            con.map_to = 'SCALE'

        for axis in axes:
            setattr(con, f"map_to_{axis}_from", axes[source_axis].upper())

            transf_value = getattr(active.location, axis)
            setattr(con, f"to_{min_max}_{axis}", transf_value)

            transf_value = getattr(active.rotation_euler, axis)
            setattr(con, f"to_{min_max}_{axis}_rot", transf_value)

            transf_value = getattr(active.scale, axis)
            setattr(con, f"to_{min_max}_{axis}_scale", transf_value)

        # Reset local transforms of constrained bone
        if con.map_to == 'LOCATION':
            con.name += " Location"
            active.location = (0, 0, 0)
        elif con.map_to == 'ROTATION':
            con.name += " Rotation"
            active.rotation_euler = (0, 0, 0)
        elif con.map_to == 'SCALE':
            con.name += " Scale"
            active.scale = (1, 1, 1)

        return {'FINISHED'}

registry = [
    POSE_OT_create_transform_constraint
]
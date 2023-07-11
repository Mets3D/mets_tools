import bpy
from . import utils
from bpy.utils import flip_name
from bpy.types import Operator, Object, PoseBone, Constraint

class POSE_OT_Symmetrize(Operator):
    """Mirror constraints to the opposite of all selected bones"""
    bl_idname = "pose.symmetrize_rigging"
    bl_label = "Symmetrize Selected Bones"
    bl_options = {'REGISTER', 'UNDO'}

    poll_fail_reason = ""

    @classmethod
    def poll(cls, context):
        if not context.object or context.object.type != 'ARMATURE':
            cls.poll_fail_reason = "No active armature"
            return False
        if not context.object.mode == 'POSE':
            cls.poll_fail_reason = "Armature must be in pose mode"
            return False

        for bone in (context.selected_bones or context.selected_pose_bones):
            if bone.name != flip_name(bone.name):
                cls.poll_fail_reason = ""
                return True

        cls.poll_fail_reason = "No selected flippable bones"
        return False

    @classmethod
    def description(cls, context, properties):
        return cls.poll_fail_reason or cls.__doc__

    def execute(self, context):
        rig = context.object
        selected_pose_bones = context.selected_pose_bones[:]

        bone_names = [pb.name for pb in selected_pose_bones]
        bpy.ops.object.mode_set(mode='EDIT')
        for bone_name in bone_names:
            eb = rig.data.edit_bones[bone_name]
            eb.hide = False
            eb.select = True
        bpy.ops.armature.symmetrize()
        bpy.ops.object.mode_set(mode='POSE')

        for pb in selected_pose_bones:
            flipped_name = flip_name(pb.name)
            opp_pb = rig.pose.bones.get(flipped_name)
            if opp_pb in selected_pose_bones:
                self.report({'ERROR'}, f'Bone selected on both sides: "{pb.name}". Select only one side to clarify symmetrizing direction')
                return {'CANCELLED'}
            if opp_pb == pb:
                self.report({'WARNING'}, f'Bone name cannot be flipped: "{pb.name}". Symmetrize will have no effect.')
                pb.bone.select = False
                selected_pose_bones.remove(pb)
                continue
            else:
                # Wipe any existing constraints on the opposite side bone.
                for con in opp_pb.constraints:
                    remove_constraint_with_drivers(opp_pb, con.name)

        for bone_name in bone_names:
            pb = rig.pose.bones[bone_name]
            flipped_name = flip_name(pb.name)
            opp_pb = rig.pose.bones.get(flipped_name)
            if not opp_pb:
                continue
            # Mirror drivers on bone properties.
            mirror_drivers(context.object, pb, opp_pb)

            # Mirror constraints and drivers on constraint properties.
            for con in pb.constraints:
                mirror_constraint(rig, pb, con)

            # Mirror bone layers. NOTE: Symmetrize operator should do this imho, but it doesn't.
            opp_pb.bone.layers = pb.bone.layers


        return {"FINISHED"}

def remove_constraint_with_drivers(
        pbone: PoseBone,
        con_name: str,
    ):
    armature = pbone.id_data
    con = pbone.constraints.get(con_name)
    if not con:
        return

    pbone.constraints.remove(con)

    if armature.animation_data:
        for fc in armature.animation_data.drivers[:]:
            if (
                "pose.bones" in fc.data_path and 
                pbone.name in fc.data_path and
                "constraints" in fc.data_path and
                con_name in fc.data_path
            ):
                armature.animation_data.drivers.remove(fc)

def mirror_constraint(
        armature: Object,
        pbone: PoseBone,
        con: Constraint
    ):
    """Apply some additional mirroring logic that the Symmetrize operator doesn't do for us."""
    flipped_con_name = flip_name(con.name)
    flipped_bone_name = flip_name(pbone.name)
    opp_pb = armature.pose.bones.get(flipped_bone_name)

    if pbone == opp_pb: 
        # Bone name cannot be flipped, so we skip.
        return
    if pbone == opp_pb and con.name == flipped_con_name: 
        # No opposite bone found and the constraint name could not be flipped, so we skip.
        return

    opp_c = utils.find_or_create_constraint(opp_pb, con.type, flipped_con_name)
    utils.copy_attributes(con, opp_c, skip=['name'])
    opp_c.name = flipped_con_name

    if con.type=='ACTION' and pbone != opp_pb:
        # Need to mirror the curves in the action to the opposite bone.
        # TODO: Something's wrong when the control bone's X translation axis is the global up/down axis.
        action = con.action

        curves = []
        for cur in action.fcurves:
            if pbone.name in cur.data_path:
                curves.append(cur)
        for cur in curves:
            opp_data_path = cur.data_path.replace(pbone.name, opp_pb.name)
            
            # Nuke opposite curves, just to be safe.
            while True:
                # While this should never happen, theoretically there can be an unlimited.
                # number of curves corresponding to a single channel of a single bone.
                opp_cur = action.fcurves.find(opp_data_path, index=cur.array_index)
                if not opp_cur: break
                action.fcurves.remove(opp_cur)

            # Create opposite curve.
            opp_cur = action.fcurves.new(opp_data_path, index=cur.array_index, action_group=opp_pb.name)
            utils.copy_attributes(cur, opp_cur, skip=["data_path", "group"])

            # Copy keyframes.
            for kf in cur.keyframe_points:
                opp_kf = opp_cur.keyframe_points.insert(kf.co[0], kf.co[1])
                utils.copy_attributes(kf, opp_kf, skip=["data_path"])
                # Flip X location, Y and Z rotation.
                if (
                    ("location" in cur.data_path and cur.array_index == 0) or
                    ("rotation" in cur.data_path and cur.array_index in [1, 2]) 
                ):
                        opp_kf.co[1] *= -1
                        opp_kf.handle_left[1] *=-1
                        opp_kf.handle_right[1] *=-1

    elif con.type == 'LIMIT_LOCATION':
        # X: Flipped and inverted.
        opp_c.min_x = con.max_x *-1
        opp_c.max_x = con.min_x *-1

    elif con.type == 'DAMPED_TRACK':
        # NOTE: Not sure why this isn't in the Symmetrize operator, I think it always applies?
        axis_mapping = {
            'TRACK_NEGATIVE_X' : 'TRACK_X',
            'TRACK_X' : 'TRACK_NEGATIVE_X',
        }
        if opp_c.track_axis in axis_mapping.keys():
            opp_c.track_axis = axis_mapping[con.track_axis]

    mirror_drivers(armature, pbone, opp_pb, con, opp_c)

def mirror_drivers(
        armature: Object, 
        from_bone: PoseBone, 
        to_bone: PoseBone, 
        from_constraint: Constraint=None, 
        to_constraint: Constraint=None
    ):
    """Mirrors all drivers from one bone to another.
    If from_constraint is specified, to_constraint also must be, and then copy and mirror 
    drivers between constraints instead of bones.
    """

    if not armature.animation_data: 
        # No drivers to mirror.
        return

    for d in armature.animation_data.drivers:
        if not 'pose.bones["' + from_bone.name + '"]' in d.data_path: 
            # Driver doesn't belong to source bone, skip.
            continue
        if "constraints[" in d.data_path and not from_constraint: 
            # Driver is on a constraint, but no source constraint was given, skip.
            continue
        if from_constraint and from_constraint.name not in d.data_path: 
            # Driver is on a constraint other than the given source constraint, skip.
            continue

        ### Copying mirrored driver to target bone.

        # Managing drivers through bpy is weird:
        # Even though bones and constraints have driver_add() and driver_remove() 
        # functions that take a data path relative to themselves, you can't actually 
        # access drivers from sub-IDs, only through real IDs, like Objects or Armature datablocks.

        data_path_from_bone = d.data_path.split("]", 1)[1]
        if data_path_from_bone.startswith("."):
            data_path_from_bone = data_path_from_bone[1:]
        new_d = None
        if "constraints[" in data_path_from_bone:
            data_path_from_constraint = data_path_from_bone.split("]", 1)[1]
            if data_path_from_constraint.startswith("."):
                data_path_from_constraint = data_path_from_constraint[1:]
            # Armature constraints need special special treatment...
            if from_constraint.type == 'ARMATURE' and "targets[" in data_path_from_constraint:
                target_idx = int(data_path_from_constraint.split("targets[")[1][0])
                target = to_constraint.targets[target_idx]
                # Weight is the only property that can have a driver on an Armature constraint's Target.
                target.driver_remove("weight")
                new_d = target.driver_add("weight")
            else:
                to_constraint.driver_remove(data_path_from_constraint)
                new_d = to_constraint.driver_add(data_path_from_constraint)
        else:
            to_bone.driver_remove(data_path_from_bone, d.array_index)
            try:
                new_d = to_bone.driver_add(data_path_from_bone, d.array_index)
            except:
                new_d = to_bone.driver_add(data_path_from_bone)
                # TODO: This can error sometimes, not sure why yet.

        expression = d.driver.expression
        
        # Copy the driver variables.
        for from_var in d.driver.variables:
            to_var = new_d.driver.variables.new()
            to_var.type = from_var.type
            to_var.name = from_var.name
            
            for i in range(len(from_var.targets)):
                target_bone = from_var.targets[i].bone_target
                new_target_bone = flip_name(target_bone)
                if to_var.type == 'SINGLE_PROP':
                    to_var.targets[i].id_type = from_var.targets[i].id_type
                to_var.targets[i].id = from_var.targets[i].id
                to_var.targets[i].rotation_mode = from_var.targets[i].rotation_mode
                to_var.targets[i].bone_target = new_target_bone
                data_path = from_var.targets[i].data_path
                if "pose.bones" in data_path:
                    bone_name = data_path.split('pose.bones["')[1].split('"')[0]
                    flipped_name = flip_name(bone_name)
                    data_path = data_path.replace(bone_name, flipped_name)
                # HACK
                if "left" in data_path:
                    data_path = data_path.replace("left", "right")
                elif "right" in data_path:
                    data_path = data_path.replace("right", "left")
                to_var.targets[i].data_path         = data_path
                to_var.targets[i].transform_type     = from_var.targets[i].transform_type
                to_var.targets[i].transform_space     = from_var.targets[i].transform_space
                # TODO: If transform is X Rotation, have a "mirror" option, to invert it in the expression. Better yet, detect if the new_target_bone is the opposite of the original.

        # Copy the driver expression.
        new_d.driver.expression = expression

def draw_menu_entry(self, context):
    self.layout.separator()
    self.layout.operator(POSE_OT_Symmetrize.bl_idname, icon='MOD_MIRROR')

def register():
    from bpy.utils import register_class
    register_class(POSE_OT_Symmetrize)

    bpy.types.VIEW3D_MT_pose.append(draw_menu_entry)

def unregister():
    from bpy.utils import unregister_class
    unregister_class(POSE_OT_Symmetrize)
    bpy.types.VIEW3D_MT_pose.remove(draw_menu_entry)
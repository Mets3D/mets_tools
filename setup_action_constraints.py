import bpy
from . import utils
from bpy.props import (
    EnumProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
    StringProperty,
)


class SetupActionConstraints(bpy.types.Operator):
    """Automatically manage action constraints of one action on all bones in an armature."""

    bl_idname = "armature.setup_action_constraints"
    bl_label = "Setup Action Constraints"
    bl_options = {'REGISTER', 'UNDO'}

    transform_channel: EnumProperty(
        name="Transform Channel",
        items=[
            ("LOCATION_X", "X Location", "X Location"),
            ("LOCATION_Y", "Y Location", "Y Location"),
            ("LOCATION_Z", "Z Location", "Z Location"),
            ("ROTATION_X", "X Rotation", "X Rotation"),
            ("ROTATION_Y", "Y Rotation", "Y Rotation"),
            ("ROTATION_Z", "Z Rotation", "Z Rotation"),
            ("SCALE_X", "X Scale", "X Scale"),
            ("SCALE_Y", "Y Scale", "Y Scale"),
            ("SCALE_Z", "Z Scale", "Z Scale"),
        ],
        description="Transform channel",
        default="LOCATION_X",
    )

    target_space: EnumProperty(
        name="Transform Space",
        items=[
            ("WORLD", "World Space", "World Space"),
            ("POSE", "Pose Space", "Pose Space"),
            ("LOCAL_WITH_PARENT", "Local With Parent", "Local With Parent"),
            ("LOCAL", "Local Space", "Local Space"),
        ],
        default="LOCAL",
    )

    frame_start: IntProperty(name="Start Frame")
    frame_end: IntProperty(name="End Frame", default=2)
    trans_min: FloatProperty(name="Min", default=-0.05)
    trans_max: FloatProperty(name="Max", default=0.05)
    subtarget: StringProperty(name="String Property")

    enabled: BoolProperty(name="Enabled", default=True)
    delete: BoolProperty(name="Delete", default=False)

    affect: EnumProperty(
        name="Affect Bones",
        items=(
            ("SELECTED", "Selected", "Affect all selected bones"),
            ("ALL", "All", "Affect all bones in the active armature"),
        ),
        default="ALL",
    )

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == 'ARMATURE'
            and context.object.mode in ['POSE', 'OBJECT']
        )

    def invoke(self, context, event):
        # When the operation is invoked, set the operator's target and action based on the context.
        # If they are found, find the first bone with this action constraint,
        # and pre-fill the operator settings based on that constraint.
        # TODO: If no constraint is found, put the active bone as the target.

        wm = context.window_manager

        action = context.object.animation_data.action

        if action and context.object.type == 'ARMATURE':
            done = False
            for b in context.object.pose.bones:
                for c in b.constraints:
                    if (c.type == 'ACTION') and (c.action == action):
                        self.subtarget = c.subtarget
                        self.frame_start = c.frame_start
                        self.frame_end = c.frame_end
                        self.trans_min = c.min
                        self.trans_max = c.max
                        self.enabled = not c.mute

                        self.target_space = c.target_space
                        self.transform_channel = c.transform_channel
                        done = True
                        print("Updated operator values...")
                        break
                if done:
                    break
            if not done:
                self.subtarget = context.active_pose_bone.name

        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        layout.row().prop(self, "affect", expand=True)

        layout.prop(self, "delete", text="Delete")

        if not self.delete:
            layout.prop(self, "enabled", text="Enabled")
            layout.prop_search(
                self, "subtarget", context.object.data, "bones", text="Bone"
            )
        layout.prop(context.object.animation_data, "action", text="Active Action")

        if not self.delete:
            action_row = layout.row()
            action_row.prop(self, "frame_start", text="Start")
            action_row.prop(self, "frame_end", text="End")

            trans_row = layout.row()
            trans_row.use_property_decorate = False
            trans_row.prop(self, "target_space", text="")
            trans_row.prop(self, "transform_channel", text="")

            trans_row2 = layout.row()
            trans_row2.prop(self, "trans_min")
            trans_row2.prop(self, "trans_max")

    def execute(self, context):
        # Options
        armature = context.object
        action = armature.animation_data.action
        assert action, "No action was selected."
        constraint_name = "Action_" + action.name.replace("Rain_", "")
        constraint_name_left = (
            "Action_" + action.name.replace("Rain_", "") + ".L"
        )  # TODO: Hard coded action naming convention.
        constraint_name_right = "Action_" + action.name.replace("Rain_", "") + ".R"
        constraint_names = [
            constraint_name,
            constraint_name_left,
            constraint_name_right,
        ]

        affect_bones = []
        if self.affect == 'ALL':
            affect_bones = [b.name for b in armature.pose.bones]
        else:
            affect_bones = [b.name for b in context.selected_pose_bones]

        # Getting a list of pose bones on the active armature corresponding to the selected action's keyframes
        bones = []
        for fc in action.fcurves:
            # Extracting bone name from fcurve data path
            if "pose.bones" in fc.data_path:
                bone_name = fc.data_path.split('["')[1].split('"]')[0]

                if bone_name not in affect_bones:
                    continue

                bone = armature.pose.bones.get(bone_name)
                if bone and bone not in bones:
                    bones.append(bone)

        # Adding or updating Action constraint on the bones
        for b in bones:
            constraints = [c for c in b.constraints if c.name in constraint_names]

            # Creating Action constraints
            if len(constraints) == 0:
                if (
                    bpy.utils.flip_name(b.name) == b.name
                    and bpy.utils.flip_name(self.subtarget) != self.subtarget
                ):
                    # If bone name is unflippable, but target bone name is flippable, split constraint in two.
                    c_l = utils.find_or_create_constraint(
                        b, 'ACTION', constraint_name_left
                    )
                    constraints.append(c_l)
                    c_r = utils.find_or_create_constraint(
                        b, 'ACTION', constraint_name_right
                    )
                    constraints.append(c_r)
                else:
                    c = utils.find_or_create_constraint(b, 'ACTION', constraint_name)
                    c.influence = 1
                    constraints.append(c)

            # Configuring Action constraints
            for c in constraints:
                # TODO: Utils should have a way to detect and set a string to a specific side, rather than only flip. That way we wouldn't have to hard-code and only support .L/.R suffix.
                # This is done in CloudRig, take the code from there.
                # TODO: We should abstract constraints just like we did drivers in .definitions, and then let those abstract constraints mirror themselves. Then we can use that mirroring functionality from both here and X Mirror Constraints operator.

                # If bone name indicates a side, force subtarget to that side, if subtarget is flippable.
                if b.name.endswith(".L") and self.subtarget.endswith(".R"):
                    if bpy.utils.flip_name(self.subtarget) != self.subtarget:
                        self.subtarget = self.subtarget[:-2] + ".L"
                if b.name.endswith(".R") and self.subtarget.endswith(".L"):
                    if bpy.utils.flip_name(self.subtarget) != self.subtarget:
                        self.subtarget = self.subtarget[:-2] + ".R"

                # If constraint name indicates a side, force subtarget to that side and set influence to 0.5.
                if c.name.endswith(".L") and self.subtarget.endswith(".R"):
                    self.subtarget = self.subtarget[:-2] + ".L"
                    c.influence = 0.5
                if c.name.endswith(".R") and self.subtarget.endswith(".L"):
                    self.subtarget = self.subtarget[:-2] + ".R"
                    c.influence = 0.5

                c.target_space = self.target_space
                c.transform_channel = self.transform_channel
                c.target = armature
                if self.subtarget != "":
                    c.subtarget = self.subtarget
                c.action = action
                c.min = self.trans_min
                c.max = self.trans_max
                c.frame_start = self.frame_start
                c.frame_end = self.frame_end
                c.mute = not self.enabled

        # Deleting superfluous action constraints, if any
        for bn in affect_bones:
            b = armature.pose.bones.get(bn)
            for c in b.constraints:
                if c.type == 'ACTION':
                    # If the constraint targets this action
                    if c.action == action:
                        if (
                            c.name not in constraint_names  # but its name is wrong
                            or self.delete
                        ):  # or the user wants to delete it.
                            print(
                                "removing because "
                                + c.name
                                + " not in "
                                + str(constraint_names)
                            )
                            b.constraints.remove(c)
                            continue
                        # If the name is fine, but there is no associated keyframe
                        elif b not in bones:
                            b.constraints.remove(c)
                            continue
                    # Any action constraint with no action
                    if c.action == None:
                        b.constraints.remove(c)
                        continue
                    # Warn for action constraint with suspicious names
                    if c.name == "Action" or ".00" in c.name:
                        print(
                            "Warning: Suspicious action constraint on bone: "
                            + b.name
                            + " constraint: "
                            + c.name
                        )

        return {'FINISHED'}


def register():
    from bpy.utils import register_class

    register_class(SetupActionConstraints)


def unregister():
    from bpy.utils import unregister_class

    unregister_class(SetupActionConstraints)

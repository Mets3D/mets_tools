from . import utils
from bpy.props import (
    EnumProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
    StringProperty,
)
from bpy.types import VIEW3D_MT_pose_constraints
from bpy.types import PoseBone, Action, ActionSlot, Operator
from bpy_extras import anim_utils
from bpy.utils import flip_name, register_class, unregister_class


class OBJECT_OT_setup_action_constraints(Operator):
    """Automatically manage action constraints of one action on all bones in an armature."""

    bl_idname = "armature.setup_action_constraints"
    bl_label = "Setup Action Constraints"
    bl_options = {"REGISTER", "UNDO"}

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
    mode: EnumProperty(
        name="Mode",
        items=[
            (
                "DELETE",
                "Delete",
                "Delete Action constraints matching this Action and Slot.",
            ),
            (
                "ENSURE",
                "Ensure",
                "Create/Update Action constraints matching this Action and Slot. Remove constraints of bones which are not keyed in this slot.",
            ),
        ],
        default="ENSURE",
    )

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
            context.active_object
            and context.active_object.type == "ARMATURE"
            and context.active_object.mode in ["POSE", "OBJECT"]
        )

    def get_active_action(self, context) -> tuple[Action | None, ActionSlot | None]:
        obj = context.active_object
        if not obj:
            return None, None
        animdata = obj.animation_data
        if not animdata:
            return None, None
        return animdata.action, animdata.action_slot

    def invoke(self, context, event):
        # When the operation is invoked, set the operator's target and action based on the context.
        # If they are found, find the first bone with this action constraint,
        # and pre-fill the operator settings based on that constraint.

        wm = context.window_manager

        rig_ob = context.active_object
        action, slot = self.get_active_action(context)

        # Initialize operator properties.
        if action and rig_ob.type == "ARMATURE":
            done = False
            for b in rig_ob.pose.bones:
                for c in b.constraints:
                    if (
                        (c.type == "ACTION")
                        and (c.action == action)
                        and c.action_slot == slot
                    ):
                        self.subtarget = c.subtarget
                        self.frame_start = c.frame_start
                        self.frame_end = c.frame_end
                        self.trans_min = c.min
                        self.trans_max = c.max
                        self.enabled = not c.mute

                        self.target_space = c.target_space
                        self.transform_channel = c.transform_channel
                        done = True
                        break
                if done:
                    break
            if not done:
                self.subtarget = context.active_pose_bone.name

        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        affected_bones = self.get_keyed_bones(context)
        box = layout.box()
        header, panel = box.panel("Setup Action: Operation Config")
        header.label(text="Operation")
        if panel:
            animdata = context.active_object.animation_data
            act_col = panel.column(align=True)
            act_col.prop(animdata, "action", text="Action")
            split = act_col.split(factor=0.23)
            split.label(text="Slot: ")
            split.template_search(
                animdata,
                "action_slot",
                animdata,
                "action_suitable_slots",
            )

            split = act_col.split(factor=0.23)
            split.label(text="Bones: ")
            split.row().prop(self, "affect", expand=True)

            split = act_col.split(factor=0.23)
            split.label(text="Operation: ")
            split.row().prop(self, "mode", expand=True)

        layout = layout.box()

        word = "Ensure" if self.mode == "ENSURE" else "Delete"
        punc = ":" if self.mode == "ENSURE" else "."
        layout.label(
            text=f"{word} Action constraint on {len(affected_bones)} bones{punc}",
            icon="ACTION",
        )

        if self.mode == "DELETE":
            return

        icon = "HIDE_OFF" if self.enabled else "HIDE_ON"
        layout.prop(self, "enabled", text="Enabled", icon=icon)
        layout.prop_search(
            self, "subtarget", context.active_object.data, "bones", text="Control Bone"
        )

        frame_row = layout.row(align=True)
        frame_row.prop(self, "frame_start", text="Start")
        frame_row.prop(self, "frame_end", text="End")

        trans_row = layout.row(align=True)
        trans_row.use_property_decorate = False
        trans_row.prop(self, "target_space", text="")
        trans_row.prop(self, "transform_channel", text="")

        trans_row2 = layout.row(align=True)
        trans_row2.prop(self, "trans_min")
        trans_row2.prop(self, "trans_max")

    def get_all_bones(self, context) -> list[PoseBone]:
        rig_ob = context.active_object
        if self.affect == "ALL":
            return [b.name for b in rig_ob.pose.bones]
        else:
            return [b.name for b in context.selected_pose_bones]

    def get_keyed_bones(self, context) -> list[PoseBone]:
        rig_ob = context.active_object
        action = rig_ob.animation_data.action
        all_bones = self.get_all_bones(context)
        bones = []
        action, slot = self.get_active_action(context)
        channelbag = anim_utils.action_get_channelbag_for_slot(action, slot)
        if not channelbag:
            return []
        for fc in channelbag.fcurves:
            # Extracting bone name from fcurve data path
            if "pose.bones" in fc.data_path:
                bone_name = fc.data_path.split('["')[1].split('"]')[0]

                if bone_name not in all_bones:
                    continue

                bone = rig_ob.pose.bones.get(bone_name)
                if bone and bone not in bones:
                    bones.append(bone)
        return bones

    def execute(self, context):
        rig_ob = context.active_object
        action = rig_ob.animation_data.action
        if not action:
            self.report({"ERROR"}, "No Action was selected.")
            return {"CANCELLED"}
        CON_PREFIX = "Action_"
        constraint_name = CON_PREFIX + action.name
        constraint_name_left = CON_PREFIX + action.name + ".L"
        constraint_name_right = CON_PREFIX + action.name + ".R"
        constraint_names = [
            constraint_name,
            constraint_name_left,
            constraint_name_right,
        ]

        all_bones = self.get_all_bones(context)

        # Getting a list of pose bones on the active armature corresponding to the selected action's keyframes
        pbones = self.get_keyed_bones(context)

        # Adding or updating Action constraint on the bones
        for pbone in pbones:
            constraints = [
                con for con in pbone.constraints if con.name in constraint_names
            ]

            # Creating Action constraints
            if len(constraints) == 0:
                if (
                    flip_name(pbone.name) == pbone.name
                    and flip_name(self.subtarget) != self.subtarget
                ):
                    # If bone name is unflippable, but target bone name is flippable, split constraint in two.
                    con_left = utils.find_or_create_constraint(
                        pbone, "ACTION", constraint_name_left
                    )
                    constraints.append(con_left)
                    con_right = utils.find_or_create_constraint(
                        pbone, "ACTION", constraint_name_right
                    )
                    constraints.append(con_right)
                else:
                    con = utils.find_or_create_constraint(
                        pbone, "ACTION", constraint_name
                    )
                    con.influence = 1
                    constraints.append(con)

            # Configuring Action constraints
            for con in constraints:
                # TODO: Utils should have a way to detect and set a string to a specific side, rather than only flip. That way we wouldn't have to hard-code and only support .L/.R suffix.
                # This is done in CloudRig, take the code from there.
                # TODO: We should abstract constraints just like we did drivers in .definitions, and then let those abstract constraints mirror themselves. Then we can use that mirroring functionality from both here and X Mirror Constraints operator.

                # If bone name indicates a side, force subtarget to that side, if subtarget is flippable.
                if pbone.name.endswith(".L") and self.subtarget.endswith(".R"):
                    if flip_name(self.subtarget) != self.subtarget:
                        self.subtarget = self.subtarget[:-2] + ".L"
                if pbone.name.endswith(".R") and self.subtarget.endswith(".L"):
                    if flip_name(self.subtarget) != self.subtarget:
                        self.subtarget = self.subtarget[:-2] + ".R"

                # If constraint name indicates a side, force subtarget to that side and set influence to 0.5.
                if con.name.endswith(".L") and self.subtarget.endswith(".R"):
                    self.subtarget = self.subtarget[:-2] + ".L"
                    con.influence = 0.5
                if con.name.endswith(".R") and self.subtarget.endswith(".L"):
                    self.subtarget = self.subtarget[:-2] + ".R"
                    con.influence = 0.5

                con.target_space = self.target_space
                con.transform_channel = self.transform_channel
                con.target = rig_ob
                if self.subtarget != "":
                    con.subtarget = self.subtarget
                con.action = action
                con.min = self.trans_min
                con.max = self.trans_max
                con.frame_start = self.frame_start
                con.frame_end = self.frame_end
                con.mute = not self.enabled

        # Deleting superfluous action constraints, if any
        for bn in all_bones:
            pbone = rig_ob.pose.bones.get(bn)
            for con in pbone.constraints:
                if con.type == "ACTION":
                    # If the constraint targets this action
                    if con.action == action:
                        if (
                            con.name not in constraint_names  # but its name is wrong.
                            or self.mode == "DELETE"  # or the user wants to delete it.
                        ):
                            pbone.constraints.remove(con)
                            continue
                        # If the name is fine, but there is no associated keyframe
                        elif pbone not in pbones:
                            pbone.constraints.remove(con)
                            continue

        word = "Ensured" if self.mode == 'ENSURE' else "Deleted"
        self.report({'INFO'}, f"{word} Action constraints.")
        return {"FINISHED"}


def draw_button(self, context):
    self.layout.operator(OBJECT_OT_setup_action_constraints.bl_idname, icon="ACTION")


def register():
    register_class(OBJECT_OT_setup_action_constraints)
    VIEW3D_MT_pose_constraints.append(draw_button)


def unregister():
    unregister_class(OBJECT_OT_setup_action_constraints)
    VIEW3D_MT_pose_constraints.remove(draw_button)

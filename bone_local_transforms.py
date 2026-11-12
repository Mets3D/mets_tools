import math
from typing import List, Tuple

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator, Panel, PoseBone
from mathutils import Matrix

ROTATION_MODE_ITEMS = [
    ('AUTO', "Bone's Mode", "Use the active bone's own rotation mode"),
    None,
    ('XYZ', "XYZ Euler", "Euler angles, XYZ order"),
    ('XZY', "XZY Euler", "Euler angles, XZY order"),
    ('YXZ', "YXZ Euler", "Euler angles, YXZ order"),
    ('YZX', "YZX Euler", "Euler angles, YZX order"),
    ('ZXY', "ZXY Euler", "Euler angles, ZXY order"),
    ('ZYX', "ZYX Euler", "Euler angles, ZYX order"),
    None,
    ('QUATERNION', "Quaternion", "Raw quaternion values"),
    None,
    (
        'SWING_TWIST_X',
        "Swing and X Twist",
        "Twist angle around the X axis, plus the remaining swing as pseudo-angles "
        "(same as the Transformation constraint and driver variable options)",
    ),
    (
        'SWING_TWIST_Y',
        "Swing and Y Twist",
        "Twist angle around the Y axis, plus the remaining swing as pseudo-angles "
        "(same as the Transformation constraint and driver variable options)",
    ),
    (
        'SWING_TWIST_Z',
        "Swing and Z Twist",
        "Twist angle around the Z axis, plus the remaining swing as pseudo-angles "
        "(same as the Transformation constraint and driver variable options)",
    ),
]


def get_local_matrix(pose_bone: PoseBone) -> Matrix:
    """Return the final (evaluated) transform of the pose bone relative to its
    parent bone, in the parent's pose space.

    Unlike the pose bone's own Location/Rotation/Scale properties, which are
    channel values relative to the bone's rest pose, this includes the rest pose
    offset as well as the effects of constraints and drivers.
    """
    if pose_bone.parent:
        return pose_bone.parent.matrix.inverted_safe() @ pose_bone.matrix
    return pose_bone.matrix.copy()


def format_length(context, value: float) -> str:
    # Round away float noise and normalize -0.0 so we don't display "-0 m".
    value = round(value, 6) + 0.0
    unit_settings = context.scene.unit_settings
    if unit_settings.system == 'NONE':
        return f"{value:.4f}"
    return bpy.utils.units.to_string(
        unit_settings.system,
        'LENGTH',
        value * unit_settings.scale_length,
        precision=4,
    )


def format_angle(radians: float) -> str:
    # `+ 0.0` normalizes -0.0, the replace() handles tiny negatives rounding to -0.00.
    return f"{math.degrees(radians) + 0.0:.2f}°".replace("-0.00°", "0.00°")


def format_float(value: float) -> str:
    return f"{value + 0.0:.4f}".replace("-0.0000", "0.0000")


def safe_asin(value: float) -> float:
    return math.asin(max(-1.0, min(1.0, value)))


def mode_is_angle(pose_bone: PoseBone, mode: str) -> bool:
    """Whether the rotation values shown for this mode are angles (as opposed to
    quaternion components)."""
    if mode == 'AUTO':
        mode = pose_bone.rotation_mode
    return mode != 'QUATERNION'


def get_rotation_rows(
    pose_bone: PoseBone, matrix: Matrix, mode: str
) -> Tuple[str, List[Tuple[str, str, float]]]:
    """Return a title and a list of (label, formatted value, raw value) rows for
    the rotation of the given matrix, expressed in the given rotation mode.
    Raw angles are in radians.
    """
    if mode == 'AUTO':
        mode = pose_bone.rotation_mode
        if mode == 'AXIS_ANGLE':
            mode = 'XYZ'

    if mode == 'QUATERNION':
        quat = matrix.to_quaternion()
        rows = [(label, format_float(v), v) for label, v in zip("WXYZ", quat)]
        return "Rotation (Quaternion)", rows

    if mode.startswith('SWING_TWIST_'):
        # Mirrors BKE_driver_target_matrix_to_rot_channels(): the twist axis holds
        # the twist angle, the other two hold the swing quaternion's components
        # converted to pseudo-angles (2 * asin(component)).
        twist_axis = mode[-1]
        swing, twist = matrix.to_quaternion().to_swing_twist(twist_axis)
        rows = []
        for i, axis in enumerate("XYZ"):
            if axis == twist_axis:
                rows.append((f"{axis} Twist", format_angle(twist), twist))
            else:
                angle = 2 * safe_asin(swing[i + 1])
                rows.append((f"{axis} Swing", format_angle(angle), angle))
        return f"Rotation (Swing and {twist_axis} Twist)", rows

    euler = matrix.to_euler(mode)
    rows = [(axis, format_angle(a), a) for axis, a in zip("XYZ", euler)]
    return f"Rotation ({mode})", rows


class VIEW3D_OT_mets_copy_value(Operator):
    """Copy this value to the clipboard"""

    bl_idname = "view3d.mets_copy_value"
    bl_label = "Copy Value"
    bl_options = {'INTERNAL'}

    value: StringProperty(options={'SKIP_SAVE'})
    is_angle: BoolProperty(
        description="The value is an angle in radians, which can be copied as degrees with Shift",
        options={'SKIP_SAVE'},
    )
    use_degrees: BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        text = f"Copy {properties.value} to the clipboard"
        if properties.is_angle:
            text += " (radians)\nShift: Copy in degrees"
        return text

    def invoke(self, context, event):
        self.use_degrees = self.is_angle and event.shift
        return self.execute(context)

    def execute(self, context):
        value = self.value
        if self.use_degrees:
            value = repr(math.degrees(float(value)) + 0.0)
        context.window_manager.clipboard = value
        unit = " (degrees)" if self.use_degrees else ""
        self.report({'INFO'}, f"Copied: {value}{unit}")
        return {'FINISHED'}


class VIEW3D_PT_mets_bone_local_transforms(Panel):
    """Read-only display of the active bone's transforms relative to its parent"""

    bl_label = "Local Transforms"
    bl_idname = "VIEW3D_PT_mets_bone_local_transforms"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"
    bl_context = "posemode"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.active_pose_bone is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False

        pose_bone = context.active_pose_bone
        matrix = get_local_matrix(pose_bone)
        loc, _rot, scale = matrix.decompose()

        parent_name = pose_bone.parent.name if pose_bone.parent else "Armature"
        layout.label(text=f"Relative to: {parent_name}", icon='BONE_DATA')

        def draw_rows(title, rows, is_angle=False):
            col = layout.column(align=True)
            col.label(text=title)
            for label, display, raw in rows:
                split = col.split(factor=0.3)
                split.alignment = 'LEFT'
                split.label(text=label)
                value_row = split.row()
                value_row.alignment = 'RIGHT'
                value_row.label(text=display)
                # `+ 0.0` normalizes -0.0. repr() keeps full float precision.
                op = value_row.operator(
                    VIEW3D_OT_mets_copy_value.bl_idname,
                    text="",
                    icon='COPYDOWN',
                    emboss=False,
                )
                op.value = repr(float(raw) + 0.0)
                op.is_angle = is_angle

        draw_rows(
            "Location",
            [(a, format_length(context, v), v) for a, v in zip("XYZ", loc)],
        )

        mode = context.window_manager.mets_local_rotation_mode
        title, rows = get_rotation_rows(pose_bone, matrix, mode)
        draw_rows(title, rows, is_angle=mode_is_angle(pose_bone, mode))
        layout.prop(context.window_manager, 'mets_local_rotation_mode', text="")

        draw_rows("Scale", [(a, format_float(v), v) for a, v in zip("XYZ", scale)])


registry = [VIEW3D_OT_mets_copy_value, VIEW3D_PT_mets_bone_local_transforms]


def register():
    bpy.types.WindowManager.mets_local_rotation_mode = EnumProperty(
        name="Local Rotation Mode",
        description="Rotation representation shown in the Local Transforms panel",
        items=ROTATION_MODE_ITEMS,
        default='AUTO',
    )


def unregister():
    del bpy.types.WindowManager.mets_local_rotation_mode

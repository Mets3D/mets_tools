import bpy
from bpy import types
from typing import List, Tuple, Dict, Optional
from bpy.props import StringProperty, BoolProperty, EnumProperty
from mathutils import Matrix

from .util import hotkeys


def selected_objs_with_parents(context):
    return [ob for ob in context.selected_objects if ob.parent]


class OBJECT_OT_clear_parent(bpy.types.Operator):
    """Clear the parent of selected objects"""

    bl_idname = "object.parent_clear_py"
    bl_label = "Clear Parent"
    bl_options = {'REGISTER', 'UNDO'}

    keep_transform: BoolProperty(
        name="Keep Transform",
        description="Whether to preserve the object's world-space transforms by affecting its local space transforms",
    )

    @classmethod
    def description(cls, context, properties):
        if properties.keep_transform:
            return "Clear the parent of selected objects, and affect their local-space transformation such that their world-space transformation remains the same after the relationship is cleared"
        else:
            return "Clear the parent of selected objects, without preserving their world-space transforms"

    @classmethod
    def poll(cls, context):
        if not selected_objs_with_parents(context):
            cls.poll_message_set("No selected objects have parents")
            return False

        return True

    def execute(self, context):
        objs = selected_objs_with_parents(context)

        op_type = 'CLEAR_KEEP_TRANSFORM' if self.keep_transform else 'CLEAR'
        bpy.ops.object.parent_clear(type=op_type)

        # Report what was done.
        objs_str = objs[0].name if len(objs) == 1 else f"{len(objs)} objects"
        self.report({'INFO'}, f"Cleared parent of {objs_str}")
        return {'FINISHED'}


class OBJECT_OT_clear_parent_inverse(bpy.types.Operator):
    """Reset the helper matrix responsible for offsetting the child by the parent's transforms in the moment the parenting relationship was created"""

    bl_idname = "object.parent_clear_inverse_matrix_py"
    bl_label = "Clear Parent Inverse Matrix"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        objs_with_parents = selected_objs_with_parents(context)
        if not objs_with_parents:
            cls.poll_message_set("No selected objects have parents")
            return False

        identity_matrix = Matrix.Identity(4)
        if not any(
            [obj.matrix_parent_inverse != identity_matrix for obj in objs_with_parents]
        ):
            cls.poll_message_set("No selected objects have an inverse matrix set")
            return False

        return True

    def execute(self, context):
        objs = selected_objs_with_parents(context)
        bpy.ops.object.parent_clear(type='CLEAR_INVERSE')

        # Report what was done.
        objs_str = objs[0].name if len(objs) == 1 else f"{len(objs)} objects"
        self.report({'INFO'}, f"Cleared parent inverse matrix of {objs_str}")
        return {'FINISHED'}


class OBJECT_OT_parent_set_advanced(bpy.types.Operator):
    """Parent selected objects to the active one"""

    bl_idname = "object.parent_set_advanced"
    bl_label = "Set Parent (Advanced)"
    bl_options = {'REGISTER', 'UNDO'}

    def get_parent_type_items(self, context):
        parent_ob = context.active_object
        items = [
            (
                'OBJECT',
                "Object",
                "Use simple object parenting, with no additional behaviours",
                'OBJECT_DATAMODE',
            ),
            (
                'CONSTRAINT',
                "Constraint",
                "Create a constraint-based parenting set-up",
                'CONSTRAINT',
            ),
        ]
        if parent_ob.type == 'ARMATURE':
            items.append(
                (
                    'MODIFIER',
                    "Armature Modifier",
                    "Add an Armature Modifier to the children, so they are deformed by this armature",
                    'MODIFIER',
                )
            )
            items.append(
                (
                    'BONE_RELATIVE',
                    "(Legacy) Bone: " + parent_ob.data.bones.active.name,
                    """Parent to the armature's active bone. This option is deprecated, please set the "Parent Type" to "Constraint", and choose the Armature Constraint""",
                    'BONE_DATA',
                )
            )
        elif parent_ob.type == 'CURVE':
            items.append(
                (
                    'MODIFIER',
                    "Curve Modifier",
                    "Add a Curve Modifier to the children, so they are deformed by this curve",
                    'MODIFIER',
                )
            )
            items.append(
                (
                    'FOLLOW',
                    "(Legacy) Follow Path",
                    """Animate the curve's Evaluation Time, causing all children to move along the path over time. This option is deprecated, please et the "Parent Type" to "Constraint", and choose the Follow Path Constraint""",
                    'CURVE_DATA',
                )
            )
        elif parent_ob.type == 'LATTICE':
            items.append(
                (
                    'MODIFIER',
                    "Lattice Modifier",
                    "Add a Lattice Modifier to the children, so they are deformed by this lattice",
                    'MODIFIER',
                )
            )

        if parent_ob.type in ('MESH', 'CURVE', 'LATTICE'):
            items.append(
                (
                    'VERTEX',
                    "Nearest Point",
                    "Parent to the nearest point (mesh vertex, lattice point, curve point) of the target object",
                    'VERTEXSEL',
                )
            )
            items.append(
                (
                    'VERTEX_TRI',
                    "Nearest Triangle",
                    "Parent to the nearest 3 points of the target object",
                    'MESH_DATA',
                )
            )

        return [(item[0], item[1], item[2], item[3], idx) for idx, item in enumerate(items)]

    parent_type: EnumProperty(
        name="Parent Type",
        description="Type of parenting behaviour",
        items=get_parent_type_items,
        default=0,
    )

    def get_constraint_type_items(self, context):
        items = [
            (
                'COPY_TRANSFORMS',
                "Copy Transforms",
                "In addition to Object parenting, add a Copy Transforms constraint to the children, which snaps and locks them to the parent in world space",
                'CON_TRANSLIKE',
                0,
            ),
            (
                'CHILD_OF',
                "Child Of",
                "Instead of Object parenting, add a Child Of constraint to the children, which stores a hidden Parent Inverse Matrix to create a parenting relationship while preserving the children's world-space transforms without affecting their Loc/Rot/Scale values",
                'CON_CHILDOF',
                1,
            ),
        ]
        if context.active_pose_bone:
            items.append(
                (
                    'ARMATURE',
                    "Armature",
                    "In addition to Object parenting, add an Armature constraint to the children. The child objects will only follow the parent bone when it is moved in Pose Mode, but not when it is moved in Edit Mode",
                    'CON_ARMATURE',
                    2,
                )
            )
        elif context.active_object.type == 'CURVE':
            items.append(
                (
                    'FOLLOW_PATH',
                    "Follow Path",
                    "Instead of parenting, add a Follow Path constraint to the children, and animate the curve's Evaluation Time, causing the constrained objects to follow the curve's path over time",
                    'CON_FOLLOWPATH',
                    2,
                )
            )
        return items

    constraint_type: EnumProperty(
        name="Constraint Type",
        description="What type of Constraint to use for parenting",
        items=get_constraint_type_items,
    )

    vgroup_init_method: EnumProperty(
        name="Initialize Vertex Groups",
        items=[
            ('NONE', "None", "Do not initialize vertex groups on the child meshes"),
            (
                'EMPTY_GROUPS',
                "Empty Groups",
                "On all child meshes, generate empty vertex groups for each deforming bone of the parent Armature",
            ),
            (
                'ENVELOPE_WEIGHTS',
                "Weights From Envelopes",
                "On all child meshes, generate vertex groups using the parent Armature's bone envelopes",
            ),
            (
                'PROXIMITY_WEIGHTS',
                "Weights By Proximity",
                "On all child meshes, generate Vertex Groups for the parent Armature's deforming bones, based on the mesh surface's proximity to each bone",
            ),
        ],
    )

    transform_correction: EnumProperty(
        name="Transform Correction",
        description="How to preserve the child's world-space transform, if at all",
        items=[
            (
                'NONE',
                "None",
                "Simply create the parenting relationship, even if it may cause the children to move in world space",
                'BLANK1',
                0,
            ),
            (
                'MATRIX_LOCAL',
                "Local Matrix",
                "After creating the relationship, snap the children back to their original positions. This will affect their Loc/Rot/Scale values",
                'OPTIONS',
                1,
            ),
            (
                'MATRIX_INTERNAL',
                "Internal Matrix",
                "After creating the relationship, store the correction in a hidden matrix, so the children can stay where they are in world space, and their Loc/Rot/Scale values remain unaffected",
                'SNAP_OFF',
                2,
            ),
        ],
        default='MATRIX_INTERNAL',
    )

    def invoke(self, context, _event):
        parent_ob = context.active_object
        if parent_ob.type == 'ARMATURE':
            self.parent_type = 'MODIFIER'
        
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        parent_ob = context.active_object

        layout.prop(self, 'parent_type')

        if self.parent_type == 'CONSTRAINT':
            layout.prop(self, 'constraint_type', icon='CONSTRAINT')
        elif self.parent_type == 'MODIFIER':
            if parent_ob.type == 'ARMATURE':
                layout.prop(self, 'vgroup_init_method', icon='GROUP_VERTEX')

        if self.parent_type == 'CONSTRAINT' and self.constraint_type != 'ARMATURE':
            # Skip drawing transform_correction for constraint types where
            # it's irrelevant.
            return

        layout.prop(self, 'transform_correction')

    def execute(self, context):
        parent_ob = context.active_object
        keep_transform = self.transform_correction == 'MATRIX_INTERNAL'

        objs_to_parent = [obj for obj in context.selected_objects if obj != parent_ob]
        matrix_backups = [obj.matrix_world.copy() for obj in objs_to_parent]

        op_parent_type = self.parent_type

        if self.parent_type == 'MODIFIER':
            if parent_ob.type == 'ARMATURE':
                if self.vgroup_init_method == 'EMPTY_GROUPS':
                    op_parent_type = 'ARMATURE_NAME'
                elif self.vgroup_init_method == 'ENVELOPE_WEIGHTS':
                    op_parent_type = 'ARMATURE_ENVELOPE'
                elif self.vgroup_init_method == 'PROXIMITY_WEIGHTS':
                    op_parent_type = 'ARMATURE_AUTO'
            elif parent_ob.type == 'LATTICE':
                op_parent_type = 'LATTICE'
            elif parent_ob.type == 'CURVE':
                op_parent_type = 'CURVE'
        elif self.parent_type == 'CONSTRAINT':
            if self.constraint_type == 'FOLLOW_PATH':
                op_parent_type = 'PATH_CONST'
            elif self.constraint_type == 'ARMATURE':
                return self.parent_with_arm_con(context, keep_transform)
            elif self.constraint_type == 'CHILD_OF':
                return self.parent_with_child_of_con(context)
            elif self.constraint_type == 'COPY_TRANSFORMS':
                return self.parent_with_copy_transforms_con(context)

        bpy.ops.object.parent_set(type=op_parent_type, keep_transform=keep_transform)

        if self.transform_correction != 'MATRIX_INTERNAL':
            for obj in objs_to_parent:
                obj.matrix_parent_inverse = Matrix.Identity(4)
        if self.transform_correction == 'MATRIX_LOCAL':
            for obj, mat_bkp in zip(objs_to_parent, matrix_backups):
                obj.matrix_world = mat_bkp

        # Report what was done.
        objs_str = objs_to_parent[0].name if len(objs_to_parent) == 1 else f"{len(objs_to_parent)} objects"
        self.report({'INFO'}, f"Parented {objs_str} to {parent_ob.name}")
        return {'FINISHED'}

    def parent_with_arm_con(self, context, keep_transform):
        """Parent selected objects to the active bone."""
        rig = context.active_object
        active_bone = rig.data.bones.active
        if not active_bone:
            self.report({'ERROR'}, "No active bone.")
            return {'CANCELLED'}

        bpy.ops.object.parent_set(type='OBJECT', keep_transform=keep_transform)

        objs_to_parent = [obj for obj in context.selected_objects if obj != rig]
        for obj in objs_to_parent:
            arm_con = None
            for con in obj.constraints:
                if con.type == 'ARMATURE':
                    con.targets.clear()
                    arm_con = con
                    break
            if not arm_con:
                arm_con = obj.new(type='ARMATURE')

                target = arm_con.targets.new()
                target.target = rig
                target.subtarget = active_bone.name

        # Draw a nice info message.
        objs_str = (
            obj.name if len(objs_to_parent) == 1 else f"{len(objs_to_parent)} objects"
        )
        self.report({'INFO'}, f"Constrained {objs_str} to {active_bone.name}")
        return {'FINISHED'}

    def parent_with_child_of_con(self, context):
        """Parent selected bones to the active object/bone using Child Of constraints."""
        parent_ob = context.active_object
        objs_to_parent = [obj for obj in context.selected_objects if obj != parent_ob]

        for obj in objs_to_parent:
            if obj.parent:
                self.report(
                    {'WARNING'},
                    f"Warning: A Child Of Constraint was added to {obj.name}, which already has a parent. This results in double-parenting. Existing parent should be removed!",
                )
            for con in obj.constraints:
                if con.type == 'CHILD_OF':
                    self.report(
                        {'WARNING'},
                        f"Warning: A Child Of Constraint was added to {obj.name}, which already had a Child Of constraint. This results in double-parenting. Existing constraint should be removed!",
                    )

            childof = obj.constraints.new(type='CHILD_OF')
            childof.target = parent_ob
            if context.active_pose_bone:
                childof.subtarget = context.active_pose_bone.name
                childof.inverse_matrix = (
                    parent_ob.matrix_world @ context.active_pose_bone.matrix
                ).inverted()
            else:
                childof.inverse_matrix = parent_ob.matrix_world.inverted()

        # Draw a nice info message.
        objs_str = (
            obj.name if len(objs_to_parent) == 1 else f"{len(objs_to_parent)} objects"
        )
        parent_str = (
            context.active_pose_bone.name
            if context.active_pose_bone
            else parent_ob.name
        )
        self.report({'INFO'}, f"Constrained {objs_str} to {parent_str}")
        return {'FINISHED'}

    def parent_with_copy_transforms_con(self, context):
        """Parent selected bones to the active object/bone using Copy Transforms constraints."""
        parent_ob = context.active_object
        objs_to_parent = [obj for obj in context.selected_objects if obj != parent_ob]

        for obj in objs_to_parent:
            copytrans = obj.constraints.new(type='COPY_TRANSFORMS')
            copytrans.target = parent_ob
            if context.active_pose_bone:
                copytrans.subtarget = context.active_pose_bone.name

        # Draw a nice info message.
        objs_str = (
            obj.name if len(objs_to_parent) == 1 else f"{len(objs_to_parent)} objects"
        )
        parent_str = (
            context.active_pose_bone.name
            if context.active_pose_bone
            else parent_ob.name
        )
        self.report({'INFO'}, f"Constrained {objs_str} to {parent_str}")
        return {'FINISHED'}

### Pie Menu UI
class OBJECT_MT_parenting_pie(bpy.types.Menu):
    # bl_label is displayed at the center of the pie menu
    bl_label = 'Object Parenting'
    bl_idname = 'OBJECT_MT_parenting_pie'

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        # <
        # Clear Parent
        pie.operator(OBJECT_OT_clear_parent.bl_idname, icon='X').keep_transform = False

        # >
        # Set Parent
        op = pie.operator('object.parent_set', text="Set Parent", icon='CON_CHILDOF')
        op.type = 'OBJECT'
        op.keep_transform = True

        # v
        pie.separator()

        # ^
        pie.separator()

        # ^>
        # Clear Parent (Keep Transform)
        pie.operator(
            OBJECT_OT_clear_parent.bl_idname,
            text="Clear Parent (Preserve World Space)",
            icon='WORLD',
        ).keep_transform = True

        # ^>
        # Set Parent (Advanced)
        pie.operator(OBJECT_OT_parent_set_advanced.bl_idname, icon='CON_CHILDOF')

        # v>
        # Clear Inverse
        pie.operator(OBJECT_OT_clear_parent_inverse.bl_idname, icon='DRIVER_TRANSFORM')

        # v>
        pie.separator()


registry = [
    OBJECT_OT_clear_parent,
    OBJECT_OT_clear_parent_inverse,
    OBJECT_OT_parent_set_advanced,
    OBJECT_MT_parenting_pie,
]


def register():
    for keymap_name in ('Object Mode', 'Mesh', 'Pose'):
        hotkeys.addon_hotkey_register(
            op_idname='wm.call_menu_pie',
            keymap_name=keymap_name,
            key_id='P',
            op_kwargs={'name': OBJECT_MT_parenting_pie.bl_idname},
            add_on_conflict=False,
            warn_on_conflict=False,
        )

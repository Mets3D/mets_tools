import bpy
import os
from bpy.types import PropertyGroup
from bpy.props import PointerProperty
from .operators import TransferShapeKeyDrivers, TransferMeshData, MapTopology

bl_info = {
    "name": "MeshDataTransfer",
    "author": "Maurizio Memoli",
    "description": "Transfer geometry data between meshes with all possible methods",
    "blender": (2, 93, 0),
    "version": (2, 0, 5),
    "location": "Properties Editor > Data > Mesh Data Transfer ",
    "warning": "",
    "wiki_url": "",
    "category": "Mesh",
}

script_dir = os.path.dirname(os.path.realpath(__file__))


def scene_chosenobject_poll(context, object):
    if bpy.context.active_object == object:
        return False
    return object.type in ['MESH']


def pick_armature(context, object):
    if bpy.context.active_object == object:
        return False
    return object.type in ['ARMATURE']


def update_search_method(self, context):
    active = context.active_object
    if not active:
        return
    attributes_to_transfer = (
        context.object.mesh_data_transfer_object.attributes_to_transfer
    )
    search_method = context.object.mesh_data_transfer_object.search_method
    if search_method == "UVS" and attributes_to_transfer == "UVS":
        context.object.mesh_data_transfer_object.search_method = 'CLOSEST'


class MeshDataSettings(PropertyGroup):
    mesh_object_space: bpy.props.EnumProperty(
        items=[('WORLD', 'World', '', 1), ('LOCAL', 'Local', '', 2)],
        name="Object Space",
        default='LOCAL',
    )

    gp_object_space: bpy.props.EnumProperty(
        items=[('WORLD', 'World', '', 1), ('LOCAL', 'Local', '', 2)],
        name="Object Space",
        default='LOCAL',
    )

    search_method: bpy.props.EnumProperty(
        items=[
            ('CLOSEST', 'Closest', "Closest Point on Surface Search Method", 1),
            ('RAYCAST', 'Raycast', "Bidirectional Projection Search Method", 2),
            ('TOPOLOGY', 'Topology', "Vertex ID or Topology Search Methood", 3),
            ('UVS', 'Active UV', "Active UV Search Method", 4),
        ],
        name="Search method",
        default='CLOSEST',
    )

    attributes_to_transfer: bpy.props.EnumProperty(
        items=[
            ('SHAPE', 'Shape', '', 1),
            ('UVS', 'UV set', '', 2),
            ('SHAPE_KEYS', 'Shape Keys', '', 3),
            ('VERTEX_GROUPS', 'Vertex Groups', '', 4),
        ],
        name="Attributes to to transfer",
        default="SHAPE",
        update=update_search_method,
    )

    mesh_source: bpy.props.PointerProperty(
        name="Source mesh",
        description="Pick a source armature for transfer",
        type=bpy.types.Object,
        poll=scene_chosenobject_poll,
    )

    arm_source: bpy.props.PointerProperty(
        name="Source armature",
        description="Pick a target armature for transfer",
        type=bpy.types.Object,
        poll=pick_armature,
    )

    arm_target: bpy.props.PointerProperty(
        name="Target armature",
        description="Pick a source mesh for transfer",
        type=bpy.types.Object,
        poll=pick_armature,
    )

    vertex_group_filter: bpy.props.StringProperty(
        name="Vertex Group", description="Filter transfer using a vertex group."
    )
    invert_vertex_group_filter: bpy.props.BoolProperty(
        name="Invert vertex group values"
    )
    transfer_edit_selection: bpy.props.BoolProperty(
        name="Only edit mode selection",
        description="Restrict transfer to selection in edit mode",
    )
    transfer_shape_as_key: bpy.props.BoolProperty(
        name="Transfer as shape key",
        description="Transfer vertices position as a shape key",
    )
    transfer_to_new_uv: bpy.props.BoolProperty()

    transfer_modified_source: bpy.props.BoolProperty(
        name="Transfer deformed source",
        description="Transfer the source mesh deformed by modifiers and shapeKeys",
    )

    exclude_muted_shapekeys: bpy.props.BoolProperty(
        name="Exclude muted", description="Muted shape keys will not be transferred"
    )

    exclude_locked_groups: bpy.props.BoolProperty(
        name="Exclude locked",
        description="Locked vertex groups will not be transferred",
    )
    snap_to_closest_shape: bpy.props.BoolProperty(
        name="Snap shape to closest vertex",
        description="Snap transferred vertices to closest vertex on source mesh",
    )
    snap_to_closest_shapekey: bpy.props.BoolProperty(
        name="Snap shape key to closest vertex",
        description="Snap transferred shape keys vertices to closest vertex on source shape key",
    )

    more_settings: bpy.props.BoolProperty(default=False)


# =========================================UI===============================================================


class DATA_PT_mesh_data_transfer(bpy.types.Panel):
    bl_label = "Mesh Data Transfer"
    bl_idname = "MESH_PT_mesh_data_transfer"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        # To reactivate GPencil change the variable to: ['MESH','GPENCIL']
        return context.active_object.type in ['MESH']

    @classmethod
    def is_vert_count_matching(cls, context, identifier):
        active = bpy.context.active_object
        source = active.mesh_data_transfer_object.mesh_source
        if identifier == "TOPOLOGY":
            if not source:
                return False
            if len(source.data.vertices) == len(active.data.vertices):
                return True
            else:
                return False
        elif identifier == "UVS":
            if not source:
                return False
            if active.mesh_data_transfer_object.attributes_to_transfer == "UVS":
                return False
            if source.data.uv_layers.active:
                return True
            else:
                return False
        return True

    def draw(self, context):
        active = bpy.context.active_object
        ob_prop = context.object.mesh_data_transfer_object
        # sc_prop = context.scene.mesh_data_transfer_global
        obj = context.object
        # mesh_object_space layout
        main_box_layout = self.layout.box()
        sample_main_box = main_box_layout.box()

        search_space_label = sample_main_box.row()
        search_space_label.alignment = 'CENTER'
        search_space_label.label(text="SEARCH METHOD")

        option_row = sample_main_box.row()

        items = ob_prop.bl_rna.properties["search_method"].enum_items_static

        search_icons = ["ARROW_LEFTRIGHT", "PROP_PROJECTED", "MESH_DATA", "UV_DATA"]
        for i, item in enumerate(items):
            search_icon = search_icons[i]
            # This is the first item of the enum item tuple, eg. "NONE", or "BONE_GROUPS" :
            identifier = item.identifier
            # This seems overkill but we need individual access to the field layout to disable it :
            item_layout = option_row.row(align=True)
            if i == 2:
                if not active.mesh_data_transfer_object.attributes_to_transfer == "UVS":
                    item_layout.prop_enum(
                        ob_prop,
                        "search_method",
                        identifier,
                        text="Vertex ID",
                        icon=search_icon,
                    )
                else:
                    item_layout.prop_enum(
                        ob_prop, "search_method", identifier, icon=search_icon
                    )
            else:
                item_layout.prop_enum(
                    ob_prop, "search_method", identifier, icon=search_icon
                )
            item_layout.enabled = self.is_vert_count_matching(context, identifier)

        top_row_box_layout = main_box_layout.box()

        attribute_label = top_row_box_layout.row()
        attribute_label.alignment = 'CENTER'
        attribute_label.label(text="ATTRIBUTE TO TRANSFER")

        # attribute to transfer
        top_row_layout = top_row_box_layout.row()
        attributes_to_transfer = ob_prop.bl_rna.properties[
            "attributes_to_transfer"
        ].enum_items_static
        left_top_row_box_layout = top_row_layout.box()
        shape_cols_layout = left_top_row_box_layout.row(align=True)
        shape_identifier = attributes_to_transfer[0].identifier
        uv_identifier = attributes_to_transfer[1].identifier
        shape_keys_identifier = attributes_to_transfer[2].identifier
        vertex_groups_identifier = attributes_to_transfer[3].identifier
        shape_cols_layout.prop_enum(
            ob_prop,
            "attributes_to_transfer",
            shape_identifier,
            icon="MOD_DATA_TRANSFER",
        )
        # split = shape_cols_layout.split()

        snap_shape_icon = "SNAP_OFF"
        if ob_prop.snap_to_closest_shape:
            snap_shape_icon = "SNAP_ON"
        shape_cols_layout.prop(
            ob_prop, "snap_to_closest_shape", text="", toggle=True, icon=snap_shape_icon
        )

        shape_cols_layout.prop(
            ob_prop, "transfer_shape_as_key", text="", toggle=True, icon='SHAPEKEY_DATA'
        )

        left_bottom_row_box_layout = left_top_row_box_layout.row(align=True)
        left_bottom_row_box_layout.prop_enum(
            ob_prop,
            "attributes_to_transfer",
            shape_keys_identifier,
            icon="SHAPEKEY_DATA",
        )
        snap_key_icon = "SNAP_OFF"
        if ob_prop.snap_to_closest_shapekey:
            snap_key_icon = "SNAP_ON"
        left_bottom_row_box_layout.prop(
            ob_prop,
            "snap_to_closest_shapekey",
            text="",
            toggle=True,
            icon=snap_key_icon,
        )
        left_bottom_row_box_layout.prop(
            ob_prop, "exclude_muted_shapekeys", text="", toggle=True, icon='CHECKMARK'
        )

        top_row_layout.split()
        right_top_row_box_layout = top_row_layout.box()

        right_top_row_box_layout.prop_enum(
            ob_prop, "attributes_to_transfer", uv_identifier, icon="UV_DATA"
        )
        right_bottom_row_box_layout = right_top_row_box_layout.row(align=True)
        right_bottom_row_box_layout.prop_enum(
            ob_prop,
            "attributes_to_transfer",
            vertex_groups_identifier,
            icon="GROUP_VERTEX",
        )
        right_bottom_row_box_layout.prop(
            ob_prop, "exclude_locked_groups", text="", toggle=True, icon='LOCKED'
        )

        # mesh picker layout
        mesh_picker_box_layout = main_box_layout.box()
        mesh_picker_row = mesh_picker_box_layout.row(align=True)

        mesh_picker_row.prop_search(
            ob_prop, "mesh_source", context.scene, "objects", text="Source"
        )
        mesh_picker_row.prop(
            ob_prop, "mesh_object_space", toggle=True, text="", icon="WORLD"
        )
        mesh_picker_row.prop(
            ob_prop, 'transfer_modified_source', text="", icon='MOD_MESHDEFORM'
        )

        # vertex group filter
        vgroup_picker_box_layout = main_box_layout.box()
        vgroup_row = vgroup_picker_box_layout.row(align=True)

        vgroup_row.prop_search(ob_prop, "vertex_group_filter", active, "vertex_groups")
        vgroup_row.prop(
            ob_prop,
            "invert_vertex_group_filter",
            text="",
            toggle=True,
            icon='ARROW_LEFTRIGHT',
        )

        # Mesh transfer button

        transfer_box_layout = main_box_layout.box()
        transfer_layout = transfer_box_layout.row()
        restrict_icon = "RESTRICT_SELECT_ON"
        if ob_prop.transfer_edit_selection:
            restrict_icon = "RESTRICT_SELECT_OFF"

        transfer_layout.prop(
            ob_prop, "transfer_edit_selection", text="", toggle=True, icon=restrict_icon
        )
        transfer_layout.operator(
            "object.transfer_mesh_data",
            text="Transfer Mesh Data",
            icon="MOD_DATA_TRANSFER",
        )

        # # transfer_layout.prop(ob_prop, "transfer_edit_selection", text="", toggle =True, icon = restrict_icon)
        # transfer_layout.operator("object.map_topology", text="Map Topology",
        #                                         icon="MOD_DATA_TRANSFER")
        #

        # Rigging utilities
        utility_box_layout = main_box_layout.box()
        utility_label = utility_box_layout.row(align=True)
        utility_label.prop(
            obj.mesh_data_transfer_object,
            "more_settings",
            icon="TRIA_DOWN" if obj.mesh_data_transfer_object.more_settings else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
            expand=False,
        )
        utility_label.label(text="RIGGING HELPERS")
        utility_label.alignment = "LEFT"
        if obj.mesh_data_transfer_object.more_settings:
            # armature picker layout
            source_arm_picker_box_layout = utility_box_layout.box()
            source_arm_picker_box_layout.prop_search(
                ob_prop, "arm_source", context.scene, "objects", text="Source Armature"
            )
            target_arm_picker_box_layout = utility_box_layout.box()
            target_arm_picker_box_layout.prop_search(
                ob_prop, "arm_target", context.scene, "objects", text="Target Armature"
            )
            transfer_drivers_layout = utility_box_layout.row()
            transfer_drivers_layout.operator(
                "object.transfer_shape_key_drivers",
                text="Transfer Shape Keys drivers",
                icon="DRIVER",
            )


# =================================================================================================================

registry = (
    DATA_PT_mesh_data_transfer,
    MeshDataSettings,
    TransferShapeKeyDrivers,
    TransferMeshData,
    MapTopology,
)


def register():
    for cl in registry:
        bpy.utils.register_class(cl)

    bpy.types.Object.mesh_data_transfer_object = PointerProperty(type=MeshDataSettings)


def unregister():
    for cl in registry:
        bpy.utils.unregister_class(cl)

    del bpy.types.Object.mesh_data_transfer_object

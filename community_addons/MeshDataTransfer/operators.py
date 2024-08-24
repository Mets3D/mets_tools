import bpy

from .mesh_data_transfer import MeshDataTransfer, TopologyData


class TransferShapeKeyDrivers(bpy.types.Operator):
    """Transfer Shape Key Drivers"""

    bl_idname = "object.transfer_shape_key_drivers"
    bl_label = "Transfer Shape Key Drivers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.active_object.mesh_data_transfer_object.mesh_source is not None
            and bpy.context.object.mode == "OBJECT"
            and context.active_object.mesh_data_transfer_object.arm_source is not None
        )

    def execute(self, context):
        active = context.active_object
        active_prop = context.object.mesh_data_transfer_object

        deformed_source = active_prop.transfer_modified_source
        source = active.mesh_data_transfer_object.mesh_source
        source_arm = active.mesh_data_transfer_object.arm_source
        target_arm = active.mesh_data_transfer_object.arm_target
        mask_vertex_group = active_prop.vertex_group_filter
        invert_mask = active_prop.invert_vertex_group_filter
        snap_to_closest = active_prop.snap_to_closest_shapekey
        exclude_muted_shapekeys = active_prop.exclude_muted_shapekeys
        world_space = False
        uv_space = False

        search_method = active_prop.search_method
        sample_space = active_prop.mesh_object_space
        if sample_space == 'UVS':
            uv_space = True

        if sample_space == 'LOCAL':
            world_space = False

        if sample_space == 'WORLD':
            world_space = True
        transfer_data = MeshDataTransfer(
            target=active,
            source=source,
            world_space=world_space,
            uv_space=uv_space,
            deformed_source=deformed_source,
            invert_vertex_group=invert_mask,
            search_method=search_method,
            vertex_group=mask_vertex_group,
            exclude_muted_shapekeys=exclude_muted_shapekeys,
            snap_to_closest=snap_to_closest,
            transfer_drivers=False,
            source_arm=source_arm,
            target_arm=target_arm,
        )

        transferred = transfer_data.transfer_shape_keys_drivers()
        transfer_data.free()
        if not transferred:
            self.report({'INFO'}, 'Unable to perform the operation.')
            return {'CANCELLED'}

        return {'FINISHED'}


class TransferMeshData(bpy.types.Operator):
    """Transfer Mesh Data"""

    bl_idname = "object.transfer_mesh_data"
    bl_label = "Transfer Mesh Data"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        attributes_to_transfer = (
            context.object.mesh_data_transfer_object.attributes_to_transfer
        )
        search_method = context.object.mesh_data_transfer_object.search_method
        enabled = True
        if search_method == "UVS" and attributes_to_transfer == "UVS":
            enabled = False
        return (
            context.active_object is not None
            and context.active_object.mesh_data_transfer_object.mesh_source is not None
            and enabled
        )

    def execute(self, context):

        active = context.active_object
        current_mode = bpy.context.object.mode
        if not current_mode == "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        active_prop = context.object.mesh_data_transfer_object
        deformed_source = active_prop.transfer_modified_source
        # sc_prop = context.scene.mesh_data_transfer_global
        as_shape_key = active_prop.transfer_shape_as_key
        snap_to_closest = active_prop.snap_to_closest_shape
        snap_to_closest_shapekey = active_prop.snap_to_closest_shapekey
        source = active.mesh_data_transfer_object.mesh_source
        mask_vertex_group = active_prop.vertex_group_filter
        invert_mask = active_prop.invert_vertex_group_filter
        restrict_selection = active_prop.transfer_edit_selection
        exclude_muted_shapekeys = active_prop.exclude_muted_shapekeys
        exclude_locked_groups = active_prop.exclude_locked_groups
        # target_prop = target.mesh_data_transfer_global

        world_space = False
        uv_space = False

        search_method = active_prop.search_method
        sample_space = active_prop.mesh_object_space
        if search_method == 'UVS':
            uv_space = True

        if sample_space == 'LOCAL':
            world_space = False

        if sample_space == 'WORLD':
            world_space = True
        transfer_data = MeshDataTransfer(
            target=active,
            source=source,
            world_space=world_space,
            deformed_source=deformed_source,
            invert_vertex_group=invert_mask,
            uv_space=uv_space,
            search_method=search_method,
            vertex_group=mask_vertex_group,
            snap_to_closest=snap_to_closest,
            restrict_to_selection=restrict_selection,
            exclude_muted_shapekeys=exclude_muted_shapekeys,
            snap_to_closest_shape_key=snap_to_closest_shapekey,
            exclude_locked_groups=exclude_locked_groups,
        )

        attribute_to_transfer = active_prop.attributes_to_transfer
        if attribute_to_transfer == "SHAPE":
            transferred = transfer_data.transfer_vertex_position(
                as_shape_key=as_shape_key
            )
        elif attribute_to_transfer == "UVS":
            transferred = transfer_data.transfer_uvs()
        elif attribute_to_transfer == "SHAPE_KEYS":
            transferred = transfer_data.transfer_shape_keys()
        elif attribute_to_transfer == "VERTEX_GROUPS":
            transferred = transfer_data.transfer_vertex_groups()
        transfer_data.free()
        bpy.ops.object.mode_set(mode=current_mode)
        bpy.context.view_layer.objects.active = active
        if not transferred:
            self.report({'INFO'}, 'Unable to perform the operation.')
            return {'CANCELLED'}

        return {'FINISHED'}


class MapTopology(bpy.types.Operator):
    """Map Topology"""

    bl_idname = "object.map_topology"
    bl_label = "Map Topology"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    # @classmethod
    # def poll(cls, context):
    #     attributes_to_transfer = context.object.mesh_data_transfer_object.attributes_to_transfer
    #     search_method = context.object.mesh_data_transfer_object.search_method
    #     enabled = True
    #     if search_method == "UVS" and attributes_to_transfer == "UVS":
    #         enabled = False
    #     return context.active_object is not None \
    #            and context.active_object.mesh_data_transfer_object.mesh_source is not None and enabled
    #

    def execute(self, context):
        active = context.active_object
        topo = TopologyData(active)

        print(topo.active_edge)
        print("Selected Face", topo.selected_face[0])
        print(__file__)
        face_id = topo.selected_face[0]
        active_edge = topo.edges[topo.active_edge]
        print("Active Edge", active_edge)
        print("====EDGES====")
        print(topo.edges)
        print("====FACE VERTICES====")
        print(topo.get_face_vertices(face_id))
        print("====FACE EDGES====")
        print(topo.get_face_edges(face_id))
        print("====FACE FACES====")
        print(topo.face_edge_loops)
        print("====ROLLED FACE===")
        print(topo.roll_to_edge(face_id, active_edge))
        return {'FINISHED'}


# class TransferShapeData(bpy.types.Operator):
#     """Tooltip"""
#     bl_idname = "object.transfer_shape_data"
#     bl_label = "Simple Object Operator"
#     bl_options = {'REGISTER','UNDO'}
#
#     @classmethod
#     def poll(cls, context):
#         sample_space = context.object.mesh_data_transfer_object.mesh_object_space
#         return context.active_object is not None \
#                and context.active_object.mesh_data_transfer_object.mesh_source is not None\
#                and sample_space != "TOPOLOGY" and bpy.context.object.mode == "OBJECT"
#
#     def execute(self, context):
#
#         active = context.active_object
#         active_prop = context.object.mesh_data_transfer_object
#         deformed_source = active_prop.transfer_modified_source
#         # sc_prop = context.scene.mesh_data_transfer_global
#         as_shape_key = active_prop.transfer_shape_as_key
#         snap_to_closest = active_prop.snap_to_closest_shape
#         source = active.mesh_data_transfer_object.mesh_source
#         mask_vertex_group = active_prop.vertex_group_filter
#         invert_mask = active_prop.invert_vertex_group_filter
#         restrict_selection = active_prop.transfer_edit_selection
#         # target_prop = target.mesh_data_transfer_global
#
#         world_space = False
#         uv_space = False
#
#         search_method = active_prop.search_method
#         sample_space = active_prop.mesh_object_space
#         if sample_space == 'UVS':
#             uv_space = True
#
#         if sample_space == 'LOCAL':
#             world_space = False
#
#         if sample_space == 'WORLD':
#             world_space = True
#         transfer_data = MeshDataTransfer(target=active, source =source, world_space=world_space,
#                                          deformed_source=deformed_source,invert_vertex_group = invert_mask,
#                                          uv_space=uv_space, search_method=search_method, vertex_group=mask_vertex_group,
#                                          snap_to_closest=snap_to_closest, restrict_to_selection=restrict_selection)
#         transferred = transfer_data.transfer_vertex_position(as_shape_key=as_shape_key)
#         transfer_data.free()
#         if not transferred:
#             self.report({'INFO'}, 'Unable to perform the operation.')
#             return{'CANCELLED'}
#
#         return {'FINISHED'}
#
#
# class TransferShapeKeyData(bpy.types.Operator):
#     """Tooltip"""
#     bl_idname = "object.transfer_shape_key_data"
#     bl_label = "Simple Object Operator"
#     bl_options = {'REGISTER','UNDO'}
#
#     @classmethod
#     def poll(cls, context):
#         sample_space = context.object.mesh_data_transfer_object.mesh_object_space
#         return context.active_object is not None \
#                and context.active_object.mesh_data_transfer_object.mesh_source is not None\
#                and sample_space != "TOPOLOGY" and bpy.context.object.mode == "OBJECT"
#
#     def execute(self, context):
#
#         active = context.active_object
#         active_prop = context.object.mesh_data_transfer_object
#
#         deformed_source = active_prop.transfer_modified_source
#         # sc_prop = context.scene.mesh_data_transfer_global
#         as_shape_key = active_prop.transfer_shape_as_key
#         source = active.mesh_data_transfer_object.mesh_source
#         mask_vertex_group = active_prop.vertex_group_filter
#         invert_mask = active_prop.invert_vertex_group_filter
#         snap_to_closest = active_prop.snap_to_closest_shapekey
#         # target_prop = target.mesh_data_transfer_global
#         exclude_muted_shapekeys = active_prop.exclude_muted_shapekeys
#         restrict_selection = active_prop.transfer_edit_selection
#
#         world_space = False
#         uv_space = False
#
#         search_method = active_prop.search_method
#         sample_space = active_prop.mesh_object_space
#         if sample_space == 'UVS':
#             uv_space = True
#
#         if sample_space == 'LOCAL':
#             world_space = False
#
#         if sample_space == 'WORLD':
#             world_space = True
#         transfer_data = MeshDataTransfer(target=active, source =source, world_space=world_space,
#                                          uv_space=uv_space,deformed_source= deformed_source ,
#                                          invert_vertex_group= invert_mask,
#                                          search_method=search_method, vertex_group=mask_vertex_group,
#                                          exclude_muted_shapekeys = exclude_muted_shapekeys,
#                                          snap_to_closest=snap_to_closest, transfer_drivers= False,
#                                          restrict_to_selection= restrict_selection)
#         transferred = transfer_data.transfer_shape_keys()
#         transfer_data.free()
#         if not transferred:
#             self.report({'INFO'}, 'Unable to perform the operation.')
#             return{'CANCELLED'}
#
#         return {'FINISHED'}
#
#
# class TransferShapeKeyDrivers(bpy.types.Operator):
#     """Tooltip"""
#     bl_idname = "object.transfer_shape_key_drivers"
#     bl_label = "Simple Object Operator"
#     bl_options = {'REGISTER','UNDO'}
#
#     @classmethod
#     def poll(cls, context):
#         sample_space = context.object.mesh_data_transfer_object.mesh_object_space
#         return context.active_object is not None \
#                and context.active_object.mesh_data_transfer_object.mesh_source is not None\
#                and sample_space != "TOPOLOGY" and bpy.context.object.mode == "OBJECT"
#
#     def execute(self, context):
#
#         active = context.active_object
#         active_prop = context.object.mesh_data_transfer_object
#
#         deformed_source = active_prop.transfer_modified_source
#         # sc_prop = context.scene.mesh_data_transfer_global
#         as_shape_key = active_prop.transfer_shape_as_key
#         source = active.mesh_data_transfer_object.mesh_source
#         source_arm = active.mesh_data_transfer_object.arm_source
#         target_arm = active.mesh_data_transfer_object.arm_target
#         mask_vertex_group = active_prop.vertex_group_filter
#         invert_mask = active_prop.invert_vertex_group_filter
#         snap_to_closest = active_prop.snap_to_closest_shapekey
#         # target_prop = target.mesh_data_transfer_global
#         exclude_muted_shapekeys = active_prop.exclude_muted_shapekeys
#         #transfer_drivers = active_prop.transfer_shapekeys_drivers
#         world_space = False
#         uv_space = False
#
#         search_method = active_prop.search_method
#         sample_space = active_prop.mesh_object_space
#         if sample_space == 'UVS':
#             uv_space = True
#
#         if sample_space == 'LOCAL':
#             world_space = False
#
#         if sample_space == 'WORLD':
#             world_space = True
#         transfer_data = MeshDataTransfer(target=active, source =source, world_space=world_space,
#                                          uv_space=uv_space,deformed_source= deformed_source ,
#                                          invert_vertex_group= invert_mask,
#                                          search_method=search_method, vertex_group=mask_vertex_group,
#                                          exclude_muted_shapekeys = exclude_muted_shapekeys,
#                                          snap_to_closest=snap_to_closest, transfer_drivers= False,
#                                          source_arm= source_arm, target_arm= target_arm)
#         transferred = transfer_data.transfer_shape_keys_drivers()
#         transfer_data.free()
#         if not transferred:
#             self.report({'INFO'}, 'Unable to perform the operation.')
#             return{'CANCELLED'}
#
#         return {'FINISHED'}
#
#
# class TransferVertexGroupsData(bpy.types.Operator):
#     """Tooltip"""
#     bl_idname = "object.transfer_vertex_groups_data"
#     bl_label = "Simple Object Operator"
#     bl_options = {'REGISTER','UNDO'}
#
#     @classmethod
#     def poll(cls, context):
#         sample_space = context.object.mesh_data_transfer_object.mesh_object_space
#
#         return context.active_object is not None \
#                and context.active_object.mesh_data_transfer_object.mesh_source is not None \
#                and sample_space != "TOPOLOGY" and bpy.context.object.mode == "OBJECT"
#
#
#     def execute(self, context):
#
#         active = context.active_object
#         active_prop = context.object.mesh_data_transfer_object
#
#         # sc_prop = context.scene.mesh_data_transfer_global
#         as_shape_key = active_prop.transfer_shape_as_key
#         source = active.mesh_data_transfer_object.mesh_source
#         mask_vertex_group = active_prop.vertex_group_filter
#         invert_mask = active_prop.invert_vertex_group_filter
#         exclude_locked_groups = active_prop.exclude_locked_groups
#         # target_prop = target.mesh_data_transfer_global
#         restrict_selection = active_prop.transfer_edit_selection
#         world_space = False
#         uv_space = False
#
#         search_method = active_prop.search_method
#         sample_space = active_prop.mesh_object_space
#         if sample_space == 'UVS':
#             uv_space = True
#
#         if sample_space == 'LOCAL':
#             world_space = False
#
#         if sample_space == 'WORLD':
#             world_space = True
#         transfer_data = MeshDataTransfer(target=active, source =source, world_space=world_space,
#                                          invert_vertex_group = invert_mask, uv_space=uv_space, search_method=search_method,
#                                          vertex_group=mask_vertex_group, exclude_locked_groups= exclude_locked_groups,
#                                          restrict_to_selection=restrict_selection)
#         transferred = transfer_data.transfer_vertex_groups()
#         transfer_data.free()
#         if not transferred:
#             self.report({'INFO'}, 'Unable to perform the operation.')
#             return{'CANCELLED'}
#
#         return {'FINISHED'}
#
# class TransferUVData(bpy.types.Operator):
#     """Tooltip"""
#     bl_idname = "object.transfer_uv_data"
#     bl_label = "Simple Object Operator"
#     bl_options = {'REGISTER','UNDO'}
#
#     @classmethod
#     def poll(cls, context):
#         return context.active_object is not None \
#                and context.active_object.mesh_data_transfer_object.mesh_source is not None \
#                and bpy.context.object.mode == "OBJECT"
#
#     def execute(self, context):
#
#         active = context.active_object
#         active_prop = context.object.mesh_data_transfer_object
#
#         # sc_prop = context.scene.mesh_data_transfer_global
#         as_shape_key = active_prop.transfer_shape_as_key
#         source = active.mesh_data_transfer_object.mesh_source
#         # target_prop = target.mesh_data_transfer_global
#         mask_vertex_group = active_prop.vertex_group_filter
#         invert_mask = active_prop.invert_vertex_group_filter
#         restrict_selection = active_prop.transfer_edit_selection
#         world_space = False
#         topology = False
#         search_method = active_prop.search_method
#         sample_space = active_prop.mesh_object_space
#         if sample_space == 'UVS':
#             uv_space = True
#
#         if sample_space == 'LOCAL':
#             world_space = False
#
#         if sample_space == 'WORLD':
#             world_space = True
#
#         if sample_space == 'TOPOLOGY':
#             topology = True
#
#         #transfer_uvs(active, target, world_space)
#         transfer_data = MeshDataTransfer(target=active, source =source, world_space=world_space,
#                                          invert_vertex_group = invert_mask, search_method=search_method,
#                                          topology=topology, vertex_group=mask_vertex_group,
#                                          restrict_to_selection=restrict_selection)
#         transfer_data.transfer_uvs()
#         transfer_data.free()
#
#
#         return {'FINISHED'}

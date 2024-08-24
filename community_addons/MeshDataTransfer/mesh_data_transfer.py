import bmesh
import bpy
from mathutils import Vector
import numpy as np
import codecs
from mathutils.bvhtree import BVHTree
from mathutils import Vector, kdtree


class GreasePencilData:
    def __init__(
        self, obj, deformed=False, world_space=False, uv_space=False, triangulate=True
    ):
        self.obj = obj
        self.grease_pencil = obj.data
        self.deformed = deformed
        self.world_space = world_space
        self.uv_space = uv_space

        self.triangulate = triangulate
        # BVHtree for point casting.
        self.bvhtree = None
        self.transfer_bmesh = None

        # The correspondance map of the uv_vertices to the mesh vert id
        self.vertex_map = {}

    def free(self):
        if self.transfer_bmesh:
            self.transfer_bmesh.free()
        if self.bvhtree:
            self.bvhtree = None

    @property
    def active_strokes(self):
        strokes = list()
        for layer in self.grease_pencil.layers:
            active_frame = layer.active_frame
            for stroke in active_frame.strokes:
                strokes.append(stroke)
        return strokes

    @property
    def active_points(self):
        points = list()
        for stroke in self.active_strokes:
            for point in stroke.points:
                points.append(point)
        return points

    @property
    def v_count(self):
        return len(self.active_points)

    @property
    def vertex_groups(self):
        return self.obj.vertex_groups

    def get_locked_vertex_groups_array(self):
        v_groups = self.vertex_groups
        if not v_groups:
            return
        array = []
        for g in v_groups:
            array.append(not g.lock_weight)
        return array

    def get_vertex_groups_names(self, ignore_locked=False):
        if not self.vertex_groups:
            return
        group_names = list()
        for group in self.vertex_groups:
            group_names.append(group.name)
        if ignore_locked:
            filter_array = self.get_locked_vertex_groups_array()
            for i in range(len(filter_array)):
                if not filter_array[i]:
                    group_names.pop(i)
        return group_names

    def generate_bmesh(self, deformed=True, world_space=True):
        """
        Create a bmesh from the mesh.
        This will capture the deformers too.
        :param deformed:
        :param transformed:
        :param object:
        :return:
        """
        bm = bmesh.new()
        if deformed:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            ob_eval = self.obj.evaluated_get(depsgraph)
            mesh = ob_eval.to_mesh()
            bm.from_mesh(mesh)
            ob_eval.to_mesh_clear()
        else:
            mesh = self.obj.to_mesh()
            bm.from_mesh(mesh)
        if world_space:
            bm.transform(self.obj.matrix_world)
            self.evalued_in_world_coords = True
        else:
            self.evalued_in_world_coords = False
        bm.verts.ensure_lookup_table()

        return bm


class TopologyData:
    """
    This class will order the topology based on the selected face and the active mesh
    """

    def __init__(self, obj):
        self.obj = obj
        self.mesh = obj.data

        # The correspondance map of the uv_vertices to the mesh vert id.
        self.vertex_map = {}

        self.loop_totals = None
        self.loop_starts = None
        self.face_loops = None

        self.face_edge_loops = None

        self.edges = None
        self.selected_face = None

        self.get_data()

        self.bmesh = bmesh.new()
        self.bmesh.from_mesh(self.mesh)
        self.active_edge = None
        active = self.bmesh.select_history.active
        if isinstance(active, bmesh.types.BMEdge):
            self.active_edge = active.index

        self.parsed = None

    @property
    def selected_faces(self):
        mesh = self.mesh
        f_count = len(mesh.polygons)
        selected_faces = np.zeros(f_count, dtype=np.int64)
        mesh.polygons.foreach_get("select", selected_faces)
        selected_faces = np.where(selected_faces == 1)
        return selected_faces

    def get_face_vertices(self, face_id):
        start = self.loop_starts[face_id]
        end = start + self.loop_totals[face_id]
        return self.face_loops[start:end]

    def get_face_edges(self, face_id):
        """
        return the edges sorted accordingly to the face draw order
        """
        face_vertices = self.get_face_vertices(face_id)
        offset_face_vertices = np.roll(face_vertices.ravel(), -1)
        face_edges = np.ravel([face_vertices, offset_face_vertices], 'F')
        face_edges = face_edges.reshape(int(face_edges.size / 2), 2)
        return face_edges

    def roll_to_edge(self, face_id, edge):
        face_edges = self.get_face_edges(face_id)
        face_vertices = self.get_face_vertices(face_id)
        edge_index = np.where((face_edges == edge).all(axis=1))[0]
        if edge_index.size == 0:
            edge_index = np.where((face_edges == edge[::-1]).all(axis=1))[0]
        edge = face_edges[edge_index].flatten()[0]
        face_index = np.where((face_vertices == edge))[0]
        rolled_face = np.roll(face_vertices, -face_index, axis=0)

        return rolled_face

    def get_data(self):
        mesh = self.mesh
        f_count = len(mesh.polygons)
        loop_starts = np.zeros(f_count, dtype=np.int64)
        mesh.polygons.foreach_get("loop_start", loop_starts)

        loop_totals = np.zeros(f_count, dtype=np.int64)
        mesh.polygons.foreach_get("loop_total", loop_totals)

        loops_count = len(mesh.loops)
        face_loops = np.zeros(loops_count, dtype=np.int64)
        mesh.loops.foreach_get("vertex_index", face_loops)

        edge_count = len(mesh.edges)
        edges = np.zeros((edge_count * 2), dtype=np.int64)
        mesh.edges.foreach_get("vertices", edges)
        edges = edges.reshape(int(edges.size / 2), 2)

        self.loop_totals = loop_totals
        self.face_loops = face_loops
        self.loop_starts = loop_starts
        self.edges = edges

        edge_face_total = np.sum(loop_totals)

        faces_edges_count = int(edge_face_total * 2)
        faces_edges_loops = np.zeros(faces_edges_count, dtype=np.int64)
        start = 0

        for i in range(len(mesh.polygons)):
            face_edges = self.get_face_edges(i).flatten()
            end = start + face_edges.size
            faces_edges_loops[start:end] = face_edges
            start += face_edges.size
        faces_edges_loops.shape = (int(len(faces_edges_loops) / 2), 2)
        self.face_edge_loops = faces_edges_loops

        if self.selected_faces:
            self.selected_face = self.selected_faces[0]

    def free(self):
        if self.bmesh:
            self.bmesh.free()


class MeshData:
    def __init__(
        self, obj, deformed=False, world_space=False, uv_space=False, triangulate=True
    ):
        self.obj = obj
        self.mesh = obj.data
        self.deformed = deformed
        self.world_space = world_space
        self.uv_space = uv_space

        self.triangulate = triangulate
        # BVHtree for point casting.
        self.bvhtree = None
        self.transfer_bmesh = None

        # The correspondance map of the uv_vertices to the mesh vert id.
        self.vertex_map = {}

    def free(self):
        if self.transfer_bmesh:
            self.transfer_bmesh.free()
        if self.bvhtree:
            self.bvhtree = None

    @property
    def seam_edges(self):
        return self.get_seam_edges()

    @seam_edges.setter
    def seam_edges(self, edges):
        self.set_seam_edges(edges)

    @property
    def shape_keys(self):
        if self.mesh.shape_keys:
            return self.mesh.shape_keys.key_blocks

    @property
    def vertex_groups(self):
        return self.obj.vertex_groups

    @property
    def v_count(self):
        return len(self.mesh.vertices)

    def get_locked_vertex_groups_array(self):
        v_groups = self.vertex_groups
        if not v_groups:
            return
        array = []
        for g in v_groups:
            array.append(not g.lock_weight)
        return array

    def get_vertex_groups_names(self, ignore_locked=False):
        if not self.vertex_groups:
            return
        group_names = list()
        for group in self.vertex_groups:
            group_names.append(group.name)
        if ignore_locked:
            filter_array = self.get_locked_vertex_groups_array()
            filtered_group_names = list()
            for i in range(len(filter_array)):
                if filter_array[i]:
                    filtered_group_names.append(group_names[i])
            return filtered_group_names
        return group_names

    @property
    def shape_keys_drivers(self):
        return self.mesh.shape_keys.animation_data.drivers

    @property
    def shape_keys_names(self):
        if self.shape_keys:
            return [x.name for x in self.shape_keys]

    def get_seam_edges(self):
        edges = self.mesh.edges
        edges_array = [True] * len(edges)
        edges.foreach_get("use_seam", edges_array)
        return edges_array

    def set_seam_edges(self, edges_array):
        edges = self.mesh.edges
        edges.foreach_set("use_seam", edges_array)

    def get_vertex_group_weights(self, vertex_group_name):
        v_groups = self.vertex_groups
        v_group = None
        for group in v_groups:
            if group.name == vertex_group_name:
                v_group = group.index
                # print("{} id is {}".format(group.name, group.index))
        if v_group is None:
            return
        v_count = len(self.mesh.vertices)
        weights = np.zeros(v_count, dtype=np.float32)
        for v in self.mesh.vertices:
            groups = v.groups
            for group in groups:
                i = group.group
                if i == v_group:
                    v_index = v.index
                    weight = group.weight
                    weights[v_index] = weight
        weights.shape = (v_count, 1)
        return weights

    def get_vertex_groups_weights(self, ignore_locked=False):
        v_groups = self.vertex_groups
        if not v_groups:
            return
        # setting up the np.arrays
        v_count = len(self.mesh.vertices)
        v_groups_count = len(v_groups)

        weights = np.zeros((v_count * v_groups_count), dtype=np.float32)
        weights.shape = (v_groups_count, v_count)

        for v in self.mesh.vertices:
            groups = v.groups
            for group in groups:
                i = group.group
                v_index = v.index
                weight = group.weight
                weights[i, v_index] = weight
        if ignore_locked:
            array = self.get_locked_vertex_groups_array()
            return weights[array]
        return weights

    def set_single_vgroup_weights(self, group_name, weights):
        # Remove existing vertex group.
        v_group = self.vertex_groups.get(group_name)
        group_weights = weights.flatten()
        v_ids = np.nonzero(group_weights)[0]
        for v_id in v_ids:
            value = group_weights[v_id]
            v_group.add((int(v_id),), value, "REPLACE")
        return v_group

    def set_multiple_vgroups_weights(self, weights, group_names):
        for i in range(weights.shape[0]):
            # Remove existing vertex group.
            group_name = group_names[i]
            v_group = self.vertex_groups.get(group_name)
            if v_group:
                self.vertex_groups.remove(v_group)
            group_weights = weights[i]
            v_ids = np.nonzero(group_weights)[0]
            v_group = self.obj.vertex_groups.new(name=group_name)
            for v_id in v_ids:
                value = group_weights[v_id]
                v_group.add((int(v_id),), value, "REPLACE")

    def store_shape_keys_values(self):
        values = list()
        for sk in self.shape_keys:
            values.append(sk.value)
        return values

    def set_shape_keys_values(self, values):
        for i in range(len(self.shape_keys)):
            self.shape_keys[i].value = values[i]

    def reset_shape_keys_values(self):
        for sk in self.shape_keys:
            if not sk.name == "Basis":
                sk.value = 0

    def set_position_as_shape_key(
        self, shape_key_name="Data_transfer", co=None, activate=False
    ):
        if not self.shape_keys:
            basis = self.obj.shape_key_add()
            basis.name = "Basis"
        if shape_key_name in self.shape_keys_names:
            shape_key = self.shape_keys[shape_key_name]
        else:
            shape_key = self.obj.shape_key_add()
        shape_key.name = shape_key_name
        shape_key.data.foreach_set("co", co.ravel())
        if activate:
            shape_key.value = 1.0

    def get_mesh_data(self):
        """
        Builds a BVHTree with a triangulated version of the mesh
        :param deformed: will sample the deformed mesh
        :param transformed:  will sample the mesh in world space
        :param uv_space: will sample the mesh in UVspace
        """
        deformed = self.deformed
        world_space = self.world_space
        uv_space = self.uv_space
        # create an empity bmesh
        bm = self.generate_bmesh(deformed=deformed, world_space=world_space)
        bm.verts.ensure_lookup_table()
        if uv_space:  # this is for the uv space
            # resetting the vertex map
            self.vertex_map = {}
            # get the uv_layer
            uv_layer_name = self.mesh.uv_layers.active.name
            uv_id = 0
            for i, uv in enumerate(self.mesh.uv_layers):
                if uv.name == uv_layer_name:
                    uv_id = i
            uv_layer = bm.loops.layers.uv[uv_id]
            bm.faces.ensure_lookup_table()

            nFaces = len(bm.faces)
            verts = []
            faces = []

            for fi in range(nFaces):
                face_verts = bm.faces[fi].verts
                face = []
                for i, v in enumerate(face_verts):
                    vert_id = len(verts)
                    uv = bm.faces[fi].loops[i][uv_layer].uv
                    verts_coord = Vector((uv.x, uv.y, 0.0))

                    verts.append(verts_coord)

                    if vert_id not in self.vertex_map.keys():

                        self.vertex_map[vert_id] = [v.index]
                    else:
                        if v.index not in self.vertex_map[vert_id]:
                            self.vertex_map[vert_id].append(v.index)
                    face.append(vert_id)
                faces.append(face)

            mesh = bpy.data.meshes.new('{}_PolyMesh'.format(self.obj.name))
            # print(faces)
            mesh.from_pydata(verts, [], faces)

            self.transfer_bmesh = bmesh.new()
            self.transfer_bmesh.from_mesh(mesh)
            bpy.data.meshes.remove(mesh)
        else:
            for v in bm.verts:
                self.vertex_map[v.index] = [v.index]
            self.transfer_bmesh = bm

        # triangulating the mesh
        if self.triangulate:
            bmesh.ops.triangulate(
                self.transfer_bmesh, faces=self.transfer_bmesh.faces[:]
            )
        # self.transfer_bmesh.to_mesh(mesh)

        self.bvhtree = BVHTree.FromBMesh(self.transfer_bmesh)

    def generate_bmesh(self, deformed=True, world_space=True):
        """
        Create a bmesh from the mesh.
        This will capture the deformers too.
        :param deformed:
        :param transformed:
        :param object:
        :return:
        """
        bm = bmesh.new()
        if deformed:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            ob_eval = self.obj.evaluated_get(depsgraph)
            mesh = ob_eval.to_mesh()
            bm.from_mesh(mesh)
            ob_eval.to_mesh_clear()
        else:
            mesh = self.obj.to_mesh()
            bm.from_mesh(mesh)
        if world_space:
            bm.transform(self.obj.matrix_world)
            self.evalued_in_world_coords = True
        else:
            self.evalued_in_world_coords = False
        bm.verts.ensure_lookup_table()

        return bm

    def get_shape_keys_vert_pos(self, exclude_muted=False):
        if not self.shape_keys:
            return
        if self.deformed:
            stored_values = self.store_shape_keys_values()
            self.reset_shape_keys_values()
        shape_arrays = {}
        for sk in self.shape_keys:
            if sk.name == "Basis":
                continue
            if exclude_muted:
                if sk.mute:
                    continue
            array = self.convert_shape_key_to_array(sk)
            shape_arrays[sk.name] = array
        if self.deformed:
            self.set_shape_keys_values(stored_values)
        return shape_arrays

    def convert_shape_key_to_array(self, shape_key):
        if self.deformed:
            # Create a snapshot of the shape key.
            shape_key.value = 1.0
            temp_mesh = bpy.data.meshes.new("mesh")
            temp_bm = self.generate_bmesh(deformed=True, world_space=False)
            temp_bm.to_mesh(temp_mesh)
            verts = temp_mesh.vertices
            v_count = len(verts)
            co = np.zeros(v_count * 3, dtype=np.float32)
            verts.foreach_get("co", co)
            co.shape = (v_count, 3)
            temp_bm.free()
            bpy.data.meshes.remove(temp_mesh)
            shape_key.value = 0.0
            return co

        v_count = len(self.mesh.vertices)
        co = np.zeros(v_count * 3, dtype=np.float32)
        shape_key.data.foreach_get("co", co)
        co.shape = (v_count, 3)
        return co

    def get_verts_position(self):
        """
        Get the mesh vertex coordinated
        :return: np.array
        """
        if self.deformed:
            # print("Getting deformed vertices position for {}".format(self.obj.name))
            temp_bm = self.generate_bmesh(deformed=self.deformed, world_space=False)
            temp_mesh = bpy.data.meshes.new("mesh")  # add the new mesh
            temp_bm.to_mesh(temp_mesh)
            verts = temp_mesh.vertices
            v_count = len(verts)
            co = np.zeros(v_count * 3, dtype=np.float32)
            verts.foreach_get("co", co)
            co.shape = (v_count, 3)
            bpy.data.meshes.remove(temp_mesh)
            temp_bm.free()
            return co
        # print ("Getting non deformed vertices position for {}".format (self.obj.name))
        v_count = len(self.mesh.vertices)
        co = np.zeros(v_count * 3, dtype=np.float32)
        self.mesh.vertices.foreach_get("co", co)
        co.shape = (v_count, 3)
        return co

    def get_selected_verts(self):
        v_count = len(self.mesh.vertices)
        co = np.zeros(v_count, dtype=np.float32)
        self.mesh.vertices.foreach_get("select", co)
        co.shape = (v_count, 1)
        return co

    def set_verts_position(self, co):
        self.mesh.vertices.foreach_set("co", co.ravel())
        self.mesh.update()


class MeshDataTransfer:
    def __init__(
        self,
        source,
        target,
        uv_space=False,
        deformed_source=False,
        deformed_target=False,
        world_space=False,
        search_method="RAYCAST",
        topology=False,
        vertex_group=None,
        invert_vertex_group=False,
        exclude_locked_groups=False,
        exclude_muted_shapekeys=False,
        snap_to_closest=False,
        snap_to_closest_shape_key=False,
        transfer_drivers=False,
        source_arm=None,
        target_arm=None,
        restrict_to_selection=False,
    ):
        self.vertex_group = vertex_group
        self.restrict_to_selection = restrict_to_selection
        self.uv_space = uv_space
        self.topology = topology
        self.world_space = world_space
        self.deformed_target = deformed_target
        self.deformed_source = deformed_source
        self.search_method = search_method
        if self.uv_space:
            # automatically switching to closest if UV samlpes
            self.search_method = "CLOSEST"
        self.source = MeshData(
            source, uv_space=uv_space, deformed=deformed_source, world_space=world_space
        )
        self.source.get_mesh_data()
        self.target = MeshData(
            target, uv_space=uv_space, deformed=deformed_target, world_space=world_space
        )
        self.target.get_mesh_data()
        self.invert_vertex_group = invert_vertex_group
        self.exclude_muted_shapekeys = exclude_muted_shapekeys
        self.exclude_locked_groups = exclude_locked_groups
        self.snap_to_closest = snap_to_closest
        self.snap_to_closest_shapekey = snap_to_closest_shape_key

        self.missed_projections = None
        self.ray_casted = None
        self.hit_faces = None
        self.related_ids = None  # this will store the indexing between

        self.transfer_drivers = transfer_drivers
        self.cast_verts()
        self.barycentric_coords = self.get_barycentric_coords(
            self.ray_casted, self.hit_faces
        )

        self.source_arm = source_arm
        self.target_arm = target_arm

    def get_vertices_mask(self):
        """
        get the vertex group weights for the filter
        :return:
        """

        selection = None
        if self.restrict_to_selection:
            selection = self.target.get_selected_verts()
        if self.vertex_group:
            v_group = self.target.get_vertex_group_weights(self.vertex_group)
            if self.invert_vertex_group:
                v_group = 1.0 - v_group
            if self.restrict_to_selection:
                v_group = v_group * selection
            return v_group
        else:
            return selection

    def free(self):
        """
        Free memory
        :return:
        """
        if self.target:
            self.target.free()
        if self.source:
            self.source.free()

    def snap_coords_to_source_verts(self, coords, source_coords):
        """
        Find the closest vertex on source coordinates to the target coordinates
        :param coords: target transformed coordinates
        :param source_coords: source coordinates
        :return: snapped coordinates
        """
        source_size = len(self.source.mesh.vertices)
        kd = kdtree.KDTree(source_size)
        snapped_coords = coords
        for i, co in enumerate(source_coords):
            kd.insert(co, i)
        kd.balance()
        for i in range(len(coords)):
            co = coords[i]
            snapped = kd.find(co)

            snapped_coords[i] = snapped[0]
        return snapped_coords

    def transfer_shape_keys(self):
        shape_keys = self.source.get_shape_keys_vert_pos(
            exclude_muted=self.exclude_muted_shapekeys
        )
        if not shape_keys:
            return
        undeformed_verts = self.target.get_verts_position()
        base_coords = self.source.get_verts_position()
        if self.search_method == "TOPOLOGY":
            base_transferred_position = base_coords
        else:
            base_transferred_position = self.get_transferred_vert_coords(base_coords)
        if self.world_space:
            mat = np.array(self.target.obj.matrix_world.inverted()) @ np.array(
                self.source.obj.matrix_world
            )
            base_transferred_position = self.transform_vertices_array(
                base_transferred_position, mat
            )
        base_transferred_position = np.where(
            self.missed_projections, undeformed_verts, base_transferred_position
        )
        masked_vertices = self.get_vertices_mask()
        target_shape_keys = self.target.get_shape_keys_vert_pos()
        for sk in shape_keys:
            sk_points = shape_keys[sk]
            if self.world_space:
                mat = np.array(self.source.obj.matrix_world)
                sk_points = self.transform_vertices_array(sk_points, mat)
            if self.search_method == "TOPOLOGY":
                transferred_sk = sk_points
            else:
                transferred_sk = self.get_transferred_vert_coords(sk_points)
            # snap to vertices
            if self.snap_to_closest_shapekey:
                transferred_sk = self.snap_coords_to_source_verts(
                    transferred_sk, sk_points
                )
            if self.world_space:
                mat = np.array(self.target.obj.matrix_world.inverted())
                transferred_sk = self.transform_vertices_array(transferred_sk, mat)

            transferred_sk = np.where(
                self.missed_projections, undeformed_verts, transferred_sk
            )
            # extracting deltas
            transferred_sk = transferred_sk - base_transferred_position

            # filter on vertex group
            if isinstance(masked_vertices, (np.ndarray, np.generic)):
                delta = transferred_sk * masked_vertices
                if target_shape_keys:
                    if sk in target_shape_keys:
                        inverted_masked_vertices = 1.0 - masked_vertices
                        old_delta = (
                            target_shape_keys[sk] - undeformed_verts
                        ) * inverted_masked_vertices
                        delta = old_delta + delta
                transferred_sk = undeformed_verts + delta
            else:
                transferred_sk = transferred_sk + undeformed_verts
            self.target.set_position_as_shape_key(shape_key_name=sk, co=transferred_sk)
            # transfer drivers
        if self.transfer_drivers:
            self.transfer_shape_keys_drivers()

        return True

    @staticmethod
    def copy_f_curve(source, target):
        """
        Copy the f curve parameters from source to target
        :param source: source curve
        :param target: target curve
        """
        # remove modifiers
        for mod in target.modifiers:
            target.modifiers.remove(mod)

        for mod in source.modifiers:
            copy = target.modifiers.new(mod.type)
            for prop in mod.bl_rna.properties:
                if not prop.is_readonly:
                    setattr(copy, prop.identifier, getattr(mod, prop.identifier))
        target.extrapolation = source.extrapolation
        target_keyframe_points = target.keyframe_points
        source_keyframe_points = source.keyframe_points
        target_keyframe_points.add(len(source_keyframe_points))

        for sk, tk in zip(source_keyframe_points, target_keyframe_points):
            tk.co = sk.co
            tk.interpolation = sk.interpolation
            tk.handle_left = sk.handle_left
            tk.handle_left_type = sk.handle_left_type
            tk.handle_right = sk.handle_right
            tk.handle_right_type = sk.handle_right_type

    def transfer_shape_keys_drivers(self):
        """
        Transfer shape keys drivers.
        :return:
        """
        source_f_curves = self.source.shape_keys_drivers
        target_shape_keys_names = self.target.shape_keys_names
        for source_f_curve in source_f_curves:
            source_driver = source_f_curve.driver
            # finding the input

            source_shape_key = '['.join(source_f_curve.data_path.split('[')[1:])
            source_shape_key = "]".join(source_shape_key.split("]")[:-1])[1:-1]
            source_shape_key = codecs.decode(source_shape_key, 'unicode_escape')
            if source_shape_key not in target_shape_keys_names:
                continue
            source_channel = source_f_curve.data_path.split(".")[-1]
            # create the target driver

            target_f_curve = self.target.shape_keys[source_shape_key].driver_add(
                source_channel
            )
            # copying the f_curve
            self.copy_f_curve(source_f_curve, target_f_curve)
            target_driver = target_f_curve.driver
            # copying the data over to the target driver
            target_driver.type = source_driver.type
            # copying variables over
            for source_var in source_driver.variables:
                target_var = target_driver.variables.new()
                source_var_type = source_var.type
                target_var.name = source_var.name
                target_var.type = source_var_type

                # coping the variable targets over depending on the var source_var_type
                if source_var_type == "SINGLE_PROP":

                    for i, source_var_target in source_var.targets.items():
                        target_var_target = target_var.targets[i]
                        source_var_target_id = source_var_target.id
                        # id type
                        target_var_target.id_type = source_var_target.id_type
                        # checking if the ID object is the shape key we are copying the shapes from and replacing it
                        # with the target key shape
                        if source_var_target_id == self.source.mesh.shape_keys:
                            source_var_target_id = self.target.mesh.shape_keys

                        # replacing the armature source armature with the target armature
                        if source_var_target_id == self.source_arm:
                            if self.target_arm:
                                source_var_target_id = self.target_arm
                        # id
                        target_var_target.id = source_var_target_id

                        # data path
                        target_var_target.data_path = source_var_target.data_path

                        # transform_type
                        target_var_target.transform_type = (
                            source_var_target.transform_type
                        )
                        # bone_target
                        target_var_target.bone_target = source_var_target.bone_target
                        # rotation_mode
                        target_var_target.rotation_mode = (
                            source_var_target.rotation_mode
                        )
                        # transform_space
                        target_var_target.transform_space = (
                            source_var_target.transform_space
                        )

                if source_var_type == "TRANSFORMS":

                    for i, source_var_target in source_var.targets.items():
                        target_var_target = target_var.targets[i]
                        target_id = source_var_target.id
                        # replacing the armature source armature with the target armature
                        if target_id == self.source_arm:
                            if self.target_arm:
                                target_id = self.target_arm
                        # id
                        target_var_target.id = target_id
                        # transform_type
                        target_var_target.transform_type = (
                            source_var_target.transform_type
                        )
                        # bone_target
                        target_var_target.bone_target = source_var_target.bone_target
                        # rotation_mode
                        target_var_target.rotation_mode = (
                            source_var_target.rotation_mode
                        )
                        # transform_space
                        target_var_target.transform_space = (
                            source_var_target.transform_space
                        )
                        # data path
                        target_var_target.data_path = source_var_target.data_path

                if source_var_type in ["ROTATION_DIFF", "LOC_DIFF"]:

                    for i, source_var_target in source_var.targets.items():
                        target_var_target = target_var.targets[i]
                        target_id = source_var_target.id
                        # replacing the armature source armature with the target armature
                        if target_id == self.source_arm:
                            if self.target_arm:
                                target_id = self.target_arm
                        # id
                        target_var_target.id = target_id
                        # transform_type
                        target_var_target.transform_type = (
                            source_var_target.transform_type
                        )
                        # bone_target
                        target_var_target.bone_target = source_var_target.bone_target
                        # data path
                        target_var_target.data_path = source_var_target.data_path

            target_driver.expression = source_driver.expression
        return True

    def transfer_vertex_groups(self):
        source_weights = self.source.get_vertex_groups_weights(
            ignore_locked=self.exclude_locked_groups
        )
        weights_names = self.source.get_vertex_groups_names(
            ignore_locked=self.exclude_locked_groups
        )
        if not weights_names:
            return
        # getting existing target group weights
        existing_target_weights = self.target.get_vertex_groups_weights(
            ignore_locked=self.exclude_locked_groups
        )
        existing_target_weights_names = self.target.get_vertex_groups_names(
            ignore_locked=self.exclude_locked_groups
        )
        # setting up destination array
        target_weights_shape = (len(weights_names), self.target.v_count)
        target_weights = np.zeros(
            (target_weights_shape[0] * target_weights_shape[1]), dtype=np.float32
        )
        target_weights.shape = target_weights_shape
        masked_vertices = self.get_vertices_mask()
        # unpacking array
        for i in range(len(weights_names)):
            weight_name = weights_names[i]
            # checking if the current vertex group is the masked one.
            if self.search_method == "TOPOLOGY":
                transferred_weights = self.source.get_vertex_group_weights(
                    weight_name
                ).flatten()
            else:
                source_weight = np.zeros(
                    (source_weights[i].shape[0] * 3), dtype=np.float32
                )
                source_weight.shape = (source_weights[i].shape[0], 3)
                source_weight[:, 0] = source_weights[i]
                source_weight[:, 1] = source_weights[i]
                source_weight[:, 2] = source_weights[i]

                transferred_weights = self.get_transferred_vert_coords(source_weight)[
                    :, 0
                ]

            # filter on vertex group
            # blending to existing weight map
            existing_weight_map = None
            if isinstance(masked_vertices, (np.ndarray, np.generic)):

                if weight_name in existing_target_weights_names:
                    target_weight_index = existing_target_weights_names.index(
                        weight_name
                    )
                    existing_weight_map = existing_target_weights[target_weight_index]
                    existing_weight_map.reshape(transferred_weights.shape)
                    inverted_masked_vertices = 1.0 - masked_vertices
                    inverted_masked_vertices = inverted_masked_vertices.flatten()
                    existing_weight_map = existing_weight_map * inverted_masked_vertices
                transferred_weights = transferred_weights * masked_vertices.flatten()

            if isinstance(existing_weight_map, (np.ndarray, np.generic)):
                transferred_weights = np.sum(
                    [transferred_weights, existing_weight_map], axis=0
                )

            target_weights[i] = transferred_weights
        self.target.set_multiple_vgroups_weights(target_weights, weights_names)
        return True

    def get_projected_vertices_on_source(self):
        """
        Return the coordinates of the vertices projected on the source mesh
        """

        transfer_coord = self.source.get_verts_position()

        # transferred_position = self.calculate_barycentric_location(sorted_coords, self.barycentric_coords)
        if self.search_method == "TOPOLOGY":
            transferred_position = transfer_coord
        else:
            transferred_position = self.get_transferred_vert_coords(transfer_coord)
        if self.snap_to_closest:
            transferred_position = self.snap_coords_to_source_verts(
                transferred_position, transfer_coord
            )

        if self.world_space:  # inverting the matrix
            mat = np.array(self.target.obj.matrix_world.inverted()) @ np.array(
                self.source.obj.matrix_world
            )
            transferred_position = self.transform_vertices_array(
                transferred_position, mat
            )

        undeformed_verts = self.target.get_verts_position()
        if not self.search_method == "TOPOLOGY":
            # filetring missing positions. We Don't need that if we are doing a topology transfer
            transferred_position = np.where(
                self.missed_projections, undeformed_verts, transferred_position
            )

        return transferred_position

    def transfer_vertex_position(self, as_shape_key=False):
        transferred_position = self.get_projected_vertices_on_source()
        # filtering through vertex
        masked_vertices = self.get_vertices_mask()

        if isinstance(masked_vertices, (np.ndarray, np.generic)):
            undeformed_verts = self.target.get_verts_position()
            delta = transferred_position - undeformed_verts
            delta = delta * masked_vertices
            transferred_position = undeformed_verts + delta

        if as_shape_key:
            shape_key_name = "{}.Transferred".format(self.source.obj.name)
            target_shape_keys = self.target.get_shape_keys_vert_pos()
            if target_shape_keys:
                if shape_key_name in target_shape_keys and isinstance(
                    masked_vertices, (np.ndarray, np.generic)
                ):
                    non_deformed = self.target.get_verts_position()
                    existing_shape_key_vertex_pos = (
                        target_shape_keys[shape_key_name] - non_deformed
                    )
                    inverted_mask = 1.0 - masked_vertices
                    existing_shape_key_vertex_pos = (
                        existing_shape_key_vertex_pos * inverted_mask
                    )
                    transferred_position = (
                        existing_shape_key_vertex_pos + transferred_position
                    )

            self.target.set_position_as_shape_key(
                shape_key_name=shape_key_name, co=transferred_position, activate=True
            )
        else:
            self.target.set_verts_position(transferred_position)
            self.target.mesh.update()
        return True

    def get_transferred_vert_coords(self, transfer_coord):
        '''
        sort the transfer coords and return the transferred positions
        :param transfer_coord:
        :return:
        '''
        indexes = self.related_ids.ravel()
        # sorting verts coordinates
        sorted_coords = transfer_coord[indexes]
        # reshaping the array
        sorted_coords.shape = self.hit_faces.shape
        transferred_position = self.calculate_barycentric_location(
            sorted_coords, self.barycentric_coords
        )

        return transferred_position

    def transfer_uvs(self):
        """
        will transfer UVs using the data transfer
        :return:
        """
        current_object = bpy.context.object
        current_mode = bpy.context.object.mode
        if not current_mode == "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if not current_object == self.target.obj:
            # print("Current objects was {}".format(current_object.name))
            bpy.context.view_layer.objects.active = self.target.obj
        # get the source seam edges
        source_seams = self.source.seam_edges
        self.mark_seam_islands(self.source.obj)

        transfer_source = self.source.obj
        transfer_target = self.target.obj
        if self.search_method == "CLOSEST":
            loop_mapping = 'POLYINTERP_NEAREST'
            poly_mapping = 'NEAREST'
            edge_mapping = "EDGEINTERP_VNORPROJ"
        if self.search_method == "RAYCAST":
            loop_mapping = 'POLYINTERP_LNORPROJ'
            poly_mapping = 'POLYINTERP_PNORPROJ'
            edge_mapping = "EDGEINTERP_VNORPROJ"
        if self.search_method == "TOPOLOGY":
            loop_mapping = "TOPOLOGY"
            poly_mapping = "TOPOLOGY"
            edge_mapping = "TOPOLOGY"
        data_transfer = self.target.obj.modifiers.new(
            name="Data Transfer", type="DATA_TRANSFER"
        )
        data_transfer.use_object_transform = self.world_space
        data_transfer.data_types_edges = {"SEAM"}
        data_transfer.object = transfer_source
        data_transfer.use_loop_data = True
        # options: 'TOPOLOGY', 'NEAREST_NORMAL', 'NEAREST_POLYNOR',
        # 'NEAREST_POLY', 'POLYINTERP_NEAREST', 'POLYINTERP_LNORPROJ'
        data_transfer.use_edge_data = True
        # EDGEINTERP_VNORPROJ
        data_transfer.edge_mapping = edge_mapping
        data_transfer.loop_mapping = loop_mapping
        # options ('CUSTOM_NORMAL', 'VCOL', 'UV')
        data_transfer.data_types_loops = {
            "UV",
        }
        data_transfer.use_poly_data = True

        source_active_uv = transfer_source.data.uv_layers.active
        data_transfer.layers_uv_select_src = source_active_uv.name

        dest_active_uv = transfer_target.data.uv_layers.active
        data_transfer.layers_uv_select_dst = dest_active_uv.name

        # options: ('TOPOLOGY', 'NEAREST', 'NORMAL', 'POLYINTERP_PNORPROJ')
        if self.vertex_group or self.restrict_to_selection:
            masked_vertex = self.get_vertices_mask()
            mask_v_group = self.target.obj.vertex_groups.new()
            group_name = mask_v_group.name
            # vgroup class get lost so getting the v group instance from mesh data
            self.target.set_single_vgroup_weights(group_name, masked_vertex)
            data_transfer.vertex_group = mask_v_group.name
            # data_transfer.invert_vertex_group = self.invert_vertex_group

        data_transfer.poly_mapping = poly_mapping
        bpy.ops.object.datalayout_transfer(modifier=data_transfer.name)
        bpy.ops.object.modifier_apply(modifier=data_transfer.name)
        self.source.seam_edges = source_seams
        if self.vertex_group or self.restrict_to_selection:
            v_group = self.target.obj.vertex_groups.get(group_name)
            self.target.obj.vertex_groups.remove(v_group)
        # re applying the old seams

        return True

    @staticmethod
    def mark_seam_islands(obj):
        """
        Mark seam islands
        :param obj:
        :return:
        """
        current_object = bpy.context.object
        current_mode = bpy.context.object.mode
        scene = bpy.context.scene
        if not current_object == obj:
            if current_mode is not "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
                bpy.context.view_layer.objects.active = obj
        if not bpy.context.object.mode == "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")
        uv_sync_state = scene.tool_settings.use_uv_select_sync
        scene.tool_settings.use_uv_select_sync = True
        mesh = obj.data
        verts = mesh.vertices
        edges = mesh.edges
        current_selection = [0] * len(verts)
        verts.foreach_get("select", current_selection)
        # select all edges
        edges.foreach_set("select", [True] * len(edges))
        # set seams from isalnds
        bpy.ops.uv.mark_seam(clear=True)
        bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
        verts.foreach_set("select", current_selection)
        scene.tool_settings.use_uv_select_sync = uv_sync_state
        bpy.ops.object.mode_set(mode=current_mode)
        bpy.context.view_layer.objects.active = current_object

    @staticmethod
    def transform_vertices_array(array, mat):
        verts_co_4d = np.ones(shape=(array.shape[0], 4), dtype=np.float32)
        verts_co_4d[:, :-1] = array  # cos v (x,y,z,1) - point,   v(x,y,z,0)- vector
        local_transferred_position = np.einsum('ij,aj->ai', mat, verts_co_4d)
        return local_transferred_position[:, :3]

    def cast_verts(self):
        '''
        Ray cast the vertices of the
        :param search_method:
        :return:
        '''

        self.target.transfer_bmesh.verts.ensure_lookup_table()
        v_count = len(self.target.mesh.vertices)
        # np array with coordinates
        self.ray_casted = np.zeros(v_count * 3, dtype=np.float32)
        self.ray_casted.shape = (v_count, 3)
        # np array with the triangles
        self.hit_faces = np.zeros(v_count * 9, dtype=np.float32)
        self.hit_faces.shape = (v_count, 3, 3)

        # get the ids of the hit vertices
        self.related_ids = np.zeros(v_count * 3, dtype=np.int64)
        self.related_ids.shape = (v_count, 3)

        self.source.transfer_bmesh.faces.ensure_lookup_table()

        # np bool array with hit verts
        self.missed_projections = np.ones(v_count * 3, dtype=bool)
        self.missed_projections.shape = (v_count, 3)
        v_normal = Vector((0.0, 0.0, 1.0))
        for v in self.target.transfer_bmesh.verts:
            v_ids = self.target.vertex_map[
                v.index
            ]  # gets the correspondent vert to the UV_mesh

            if self.search_method == "CLOSEST":
                projection = self.source.bvhtree.find_nearest(v.co)
            else:
                if not self.uv_space:
                    v_normal = v.normal
                projection = self.source.bvhtree.ray_cast(v.co, v_normal)
                # project in the opposite direction if the ray misses
                if not projection[0]:
                    projection = self.source.bvhtree.ray_cast(v.co, (v_normal * -1.0))
            if projection[0]:
                for v_id in v_ids:
                    self.ray_casted[v_id] = projection[0]
                    self.missed_projections[v_id] = False
                    face = self.source.transfer_bmesh.faces[projection[2]]
                    self.hit_faces[v_id] = (
                        face.verts[0].co,
                        face.verts[1].co,
                        face.verts[2].co,
                    )
                    # getting the related vertex ids
                    v1_id, v2_id, v3_id = (
                        face.verts[0].index,
                        face.verts[1].index,
                        face.verts[2].index,
                    )
                    v1_id = self.source.vertex_map[v1_id][0]
                    v2_id = self.source.vertex_map[v2_id][0]
                    v3_id = self.source.vertex_map[v3_id][0]
                    v_array = np.array([v1_id, v2_id, v3_id])

                    self.related_ids[v_id] = v_array
            else:
                for v_id in v_ids:
                    self.ray_casted[v_id] = v.co
        return self.ray_casted, self.hit_faces, self.related_ids

    @staticmethod
    def get_barycentric_coords(verts_co, triangles):
        """
        Calculate the barycentric coordinates
        :param verts_co:
        :param triangles:
        :return:
        """

        barycentric_coords = verts_co.copy()
        # calculate vectors from point f to vertices p1, p2 and p3:

        vert_to_corners = np.copy(triangles)
        vert_to_corners[:, 0] -= verts_co  # f1 point 1 of the triangle coord
        vert_to_corners[:, 1] -= verts_co  # f2 point 2 of the triangle coord
        vert_to_corners[:, 2] -= verts_co  # f3 point 3 of the triangle coord

        # main triangle area
        main_triangle_areas = np.cross(
            (triangles[:, 0] - triangles[:, 1]), (triangles[:, 0] - triangles[:, 2])
        )  # va
        # calculate vert corners areas
        va1 = np.cross(vert_to_corners[:, 1], vert_to_corners[:, 2])  # va1
        va2 = np.cross(vert_to_corners[:, 2], vert_to_corners[:, 0])  # va2
        va3 = np.cross(vert_to_corners[:, 0], vert_to_corners[:, 1])  # va2
        # getting the magnitude of main triangle areas
        a = np.sqrt((main_triangle_areas * main_triangle_areas).sum(axis=1))
        # magnitude of the vert corners areas
        barycentric_coords[:, 0] = (
            np.sqrt((va1 * va1).sum(axis=1))
            / a
            * np.sign((va1 * main_triangle_areas).sum(1))
        )
        barycentric_coords[:, 1] = (
            np.sqrt((va2 * va2).sum(axis=1))
            / a
            * np.sign((va2 * main_triangle_areas).sum(1))
        )
        barycentric_coords[:, 2] = (
            np.sqrt((va3 * va3).sum(axis=1))
            / a
            * np.sign((va3 * main_triangle_areas).sum(1))
        )
        return barycentric_coords

    @staticmethod
    def calculate_barycentric_location(uv_coords, coords):
        """
        Calculate the vertex position based on the coords
        :param uv_coords:
        :param coords:
        :return:
        """
        # print("UV_coords[0,0] is: ", uv_coords[0, 0])
        # print ("Coords[0,0] is: " , coords[0, 0])
        location = (
            uv_coords[:, 0] * coords[:, 0, None]
            + uv_coords[:, 1] * coords[:, 1, None]
            + uv_coords[:, 2] * coords[:, 2, None]
        )
        return location

    # ================================================DEBUG=============================================================
    @staticmethod
    def create_debug_mesh(obj, co, name):
        print(co.shape[0])
        copy = obj.data.copy()
        print(len(copy.vertices))
        new_obj = bpy.data.objects.new(name, copy)
        bpy.context.scene.collection.objects.link(new_obj)
        copy.vertices.foreach_set("co", co.ravel())
        obj.data.update()
        return new_obj

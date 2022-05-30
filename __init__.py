# MetsTools addon for Blender
# Copyright (C) 2019 Demeter Dzadik
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TODO
#	Mirror selected bones (names, transforms, constraints, drivers, settings)
# 	Copy Cloth Settings (for some reason Copy Attributes doesn't do this)
#	Maybe use Jacques's auto-register.

bl_info = {
	"name": "MetsTools",
	"author": "Demeter Dzadik",
	"version": (2,4),
	"blender": (3, 0, 0),
	"location": "View3D > Search",
	"description": "Random collection of tools I built for myself",
	"category": "Rigging",
	"doc_url": "https://github.com/Mets3D/mets_tools/blob/master/docs/README.md",
	"tracker_url": "https://github.com/Mets3D/mets_tools/issues/new",
}
	
import importlib

from . import create_lightmap_uvs
from . import make_physics_bones
from . import cleanup_blend
from . import join_as_shape_key_by_uvs
# from . import join_as_shape_key_by_weights
from . import make_modifiers_consistent
from . import weighted_normals
from . import convert_images
from . import rename_skeleton_to_metsrig
from . import mirror_constraints
from . import setup_action_constraints
from . import armature_apply_scale
from . import assign_bone_group
from . import refresh_drivers
from . import weld_normals
from . import relink_character_rig
from . import resync_all_collections
from . import armature_merge
from . import armature_constraint_vertex_parent
from . import parent_with_armature_constraint
from . import better_bone_extrude

# Each module is expected to have a register() and unregister() function.
modules = [
	create_lightmap_uvs,
	make_physics_bones,
	cleanup_blend,
	join_as_shape_key_by_uvs,
	# join_as_shape_key_by_weights,
	make_modifiers_consistent,
	weighted_normals,
	convert_images,
	rename_skeleton_to_metsrig,
	mirror_constraints,
	setup_action_constraints,
	armature_apply_scale,
	assign_bone_group,
	refresh_drivers,
	weld_normals,
	relink_character_rig,
	resync_all_collections,
	armature_merge,
	armature_constraint_vertex_parent,
	parent_with_armature_constraint,
	better_bone_extrude
]

def register():
	for m in modules:
		importlib.reload(m)
		try:
			m.register()
		except:
			pass

def unregister():
	for m in modules:
		m.unregister()
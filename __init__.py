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
	
from typing import List
import importlib
from bpy.utils import register_class, unregister_class

from . import (
    armature_apply_scale,
    armature_constraint_parent,
    armature_constraint_vertex_parent,
	armature_merge,
	assign_bone_group,
	better_bone_extrude,
    bone_parenting_ops,
	refresh_drivers,
    symmetrize,
)

# Each module is expected to have a register() and unregister() function.
modules = [
    armature_apply_scale,
    armature_constraint_parent,
    armature_constraint_vertex_parent,
	armature_merge,
	assign_bone_group,
	better_bone_extrude,
    bone_parenting_ops,
	refresh_drivers,
    symmetrize,
]

def register_unregister_modules(modules: List, register: bool):
	"""Recursively register or unregister modules by looking for either
	un/register() functions or lists named `registry` which should be a list of 
	registerable classes.
	"""
	register_func = register_class if register else unregister_class

	for m in modules:
		if register:
			importlib.reload(m)
		if hasattr(m, 'registry'):
			for c in m.registry:
				try:
					register_func(c)
				except Exception as e:
					un = 'un' if not register else ''
					print(f"Warning: MetsTools failed to {un}register class: {c.__name__}")
					print(e)

		if hasattr(m, 'modules'):
			register_unregister_modules(m.modules, register)

		if register and hasattr(m, 'register'):
			m.register()
		elif hasattr(m, 'unregister'):
			m.unregister()

def register():
	register_unregister_modules(modules, True)

def unregister():
	register_unregister_modules(modules, False)

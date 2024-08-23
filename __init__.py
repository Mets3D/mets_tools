# MetsTools addon for Blender
# Copyright (C) 2019 Demeter Dzadik

bl_info = {
    "name": "MetsTools",
    "author": "Demeter Dzadik",
    "version": (2, 4),
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
    armature_constraint_vertex_parent,
    object_select_pie,
    refresh_drivers,
    object_parenting_pie,
    create_transform_constraint,
    setup_action_constraints,
    vgroup_merge,
)

# Each module is expected to have a register() and unregister() function.
modules = [
    armature_apply_scale,
    armature_constraint_vertex_parent,
    refresh_drivers,
    object_parenting_pie,
    create_transform_constraint,
    object_select_pie,
    setup_action_constraints,
    vgroup_merge,
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
                    print(
                        f"ERROR: MetsTools failed to {un}register class: {c.__name__}"
                    )
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

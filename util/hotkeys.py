from typing import List, Dict, Tuple, Optional
import bpy
from bpy.types import KeyConfig, KeyMap, KeyMapItem, Operator


def addon_hotkey_register(
    keymap_name='Window',
    op_idname='',
    key_id='A',
    event_type='PRESS',
    any=False,
    ctrl=False,
    alt=False,
    shift=False,
    oskey=False,
    key_modifier='NONE',
    direction='ANY',
    repeat=False,
    op_kwargs={},

    add_on_conflict=True,
    warn_on_conflict=True,
    error_on_conflict=False,
):
    """Top-level function for registering a hotkey as conveniently as possible.
    If you want to better manage the registered hotkey (for example, to be able
    to un-register it), it's advised to instantiate PyKeyMapItems yourself instead.

    :param str keymap_name: Name of the KeyMap that this hotkey will be created in. Used to define what contexts the hotkey is available in
    :param str op_idname: bl_idname of the operator this hotkey should execute
    :param str key_id: Name of the key that must be interacted with to trigger this hotkey
    :param str event_type: Type of interaction to trigger this hotkey

    :param bool any: If True, all modifier keys will be valid to trigger this hotkey
    :param bool ctrl: Whether the Ctrl key needs to be pressed in addition to the primary key
    :param bool alt: Whether the Alt key needs to be pressed in addition to the primary key
    :param bool shift: Whether the Shift key needs to be pressed in addition to the primary key
    :param bool oskey: Whether the OS key needs to be pressed in addition to the primary key
    :param str key_modifier: Another non-modifier key that should be used as a modifier key
    :param str direction: For interaction methods with a direction, this defines the direction
    :param bool repeat: Whether the hotkey should repeat its action as long as the keys remain held

    :param op_kwargs: A dictionary of parameters that should be passed as operator parameters

    :return: The PyKeyMapItem that manages this hotkey
    """
    py_kmi = PyKeyMapItem(
        op_idname=op_idname,
        key_id=key_id,
        event_type=event_type,
        any=any,
        ctrl=ctrl,
        alt=alt,
        shift=shift,
        oskey=oskey,
        key_modifier=key_modifier,
        direction=direction,
        repeat=repeat,
        op_kwargs=op_kwargs,
    )

    keymap, kmi = py_kmi.register(
        keymap_name=keymap_name,
        add_on_conflict=add_on_conflict,
        warn_on_conflict=warn_on_conflict,
        error_on_conflict=error_on_conflict,
    )
    return keymap, kmi


class PyKeyMapItem:
    """Class to help conveniently manage a single KeyMapItem, independently of
    any particular KeyMap or any other container or built-in bpy_type."""

    def __init__(
        self,
        op_idname='',
        key_id='A',
        event_type='PRESS',
        any=False,
        ctrl=False,
        alt=False,
        shift=False,
        oskey=False,
        key_modifier='NONE',
        direction='ANY',
        repeat=False,
        op_kwargs={},
    ):
        self.op_idname = op_idname
        self.key_id = self.type = key_id
        self.check_key_id()
        self.event_type = self.value = event_type
        self.check_event_type()

        self.any = any
        self.ctrl = ctrl
        self.alt = alt
        self.shift = shift
        self.oskey = oskey
        self.key_modifier = key_modifier
        self.direction = direction
        self.repeat = repeat

        self.op_kwargs = op_kwargs

    @staticmethod
    def new_from_keymap_item(kmi: KeyMapItem, context=None) -> "PyKeyMapItem":
        return PyKeyMapItem(
            op_idname=kmi.idname,
            key_id=kmi.type,
            event_type=kmi.value,
            any=kmi.any,
            ctrl=kmi.ctrl,
            alt=kmi.alt,
            shift=kmi.shift,
            oskey=kmi.oskey,
            key_modifier=kmi.key_modifier,
            direction=kmi.direction,
            repeat=kmi.repeat,
            op_kwargs={
                key: getattr(kmi.properties, key) for key in kmi.properties.keys()
            },
        )

    def check_key_id(self):
        """Raise a KeyMapException if the keymap_name isn't a valid KeyMap name that
        actually exists in Blender's keymap system.
        """
        return check_key_id(self.key_id)

    def check_event_type(self):
        """Raise a KeyMapException if the event_type isn't one that actually exists
        in Blender's keymap system."""
        return check_event_type(self.event_type)

    @property
    def key_string(self) -> str:
        """A user-friendly description string of the keys needed to activate this hotkey.
        Should be identical to what's displayed in Blender's Keymap preferences.
        """
        key_data = get_enum_values(bpy.types.KeyMapItem, 'type')
        keys = []
        if self.shift:
            keys.append("Shift")
        if self.ctrl:
            keys.append("Ctrl")
        if self.alt:
            keys.append("Alt")
        if self.oskey:
            keys.append("OS")
        if self.key_modifier != 'NONE':
            keys.append(key_data[self.key_modifier][0])
        keys.append(key_data[self.key_id][0])
        final_string = " ".join(keys)
        if not final_string:
            return "Unassigned"
        return final_string

    def register(
        self,
        context=None,
        keymap_name='Window',
        *,
        add_on_conflict=True,
        warn_on_conflict=True,
        error_on_conflict=False,
    ) -> Optional[Tuple[KeyMap, KeyMapItem]]:
        """Higher-level function for addon dev convenience.
        The caller doesn't have to worry about the KeyConfig or the KeyMap.
        The `addon` KeyConfig will be used.
        """

        if not context:
            context = bpy.context

        wm = context.window_manager
        kconf = wm.keyconfigs.addon
        if not kconf:
            # This happens when running Blender in background mode.
            return

        check_keymap_name(keymap_name)
        conflicts = self.get_conflict_info(keymap_name, context)
        kmi = None
        keymap = None
        if not conflicts or add_on_conflict:
            # Add the keymap if there is no conflict, or if we are allowed
            # to add it in spite of a conflict.

            # If this KeyMap already exists, new() will return the existing one,
            # which is confusing, but ideal.
            space_type, region_type = get_ui_types_of_keymap(keymap_name)
            keymap = kconf.keymaps.new(
                name=keymap_name, space_type=space_type, region_type=region_type
            )

            kmi = self.register_in_keymap(keymap)

        # Warn or raise error about conflicts.
        if conflicts and (warn_on_conflict or error_on_conflict):
            message = f"See conflicting hotkeys below.\n"
            conflict_info = "\n".join(
                [str(PyKeyMapItem.new_from_keymap_item(kmi)) for kmi in conflicts]
            )
            message += conflict_info

            if error_on_conflict:
                raise KeyMapException("Failed to register KeyMapItem." + message)
            if warn_on_conflict:
                print("Warning: Conflicting KeyMapItems. " + message)

        return keymap, kmi

    def get_conflict_info(
        self,
        keymap_name: str,
        context=None,
    ) -> List[bpy.types.KeyMapItem]:
        """Return whether there are existing conflicting keymaps, or raise an error."""
        if not context:
            context = bpy.context

        wm = context.window_manager
        space_type, region_type = get_ui_types_of_keymap(keymap_name)

        conflicts = []

        kconfs = {('ADDON', wm.keyconfigs.addon), ('USER', wm.keyconfigs.user)}
        for identifier, kconf in kconfs:
            keymap = kconf.keymaps.find(
                keymap_name, space_type=space_type, region_type=region_type
            )
            if not keymap:
                continue

            conflicts.extend(self.find_in_keymap_conflicts(keymap))

        return conflicts

    def register_in_keymap(self, keymap: KeyMap) -> Optional[KeyMapItem]:
        """Lower-level function, for registering in a specific KeyMap."""

        kmi = keymap.keymap_items.new(
            self.op_idname,
            type=self.key_id,
            value=self.event_type,
            any=self.any,
            ctrl=self.ctrl,
            alt=self.alt,
            shift=self.shift,
            oskey=self.oskey,
            key_modifier=self.key_modifier,
            direction=self.direction,
            repeat=self.repeat,
        )

        for key in self.op_kwargs:
            value = self.op_kwargs[key]
            setattr(kmi.properties, key, value)

        return kmi

    def unregister(self, context=None) -> bool:
        """Higher-level function for addon dev convenience.
        The caller doesn't have to worry about the KeyConfig or the KeyMap.
        The hotkey will be removed from all KeyMaps of both `addon` and 'user' KeyConfigs.
        """

        if not context:
            context = bpy.context

        wm = context.window_manager
        kconfs = wm.keyconfigs

        success = False
        for kconf in (kconfs.user, kconfs.addon):
            if not kconf:
                # This happens when running Blender in background mode.
                continue
            for km in self.find_containing_keymaps(kconf):
                self.unregister_from_keymap(km)
                success = True

        return success

    def unregister_from_keymap(self, keymap: KeyMap):
        """Lower-level function, for unregistering from a specific KeyMap."""
        kmi = self.find_in_keymap_exact(keymap)
        if not kmi:
            return False
        keymap.keymap_items.remove(kmi)
        return True

    def find_containing_keymaps(self, key_config: KeyConfig) -> List[KeyMap]:
        """Return list of KeyMaps in a KeyConfig that contain a matching KeyMapItem."""
        matches: List[KeyMap] = []
        for km in key_config.keymaps:
            match = self.find_in_keymap_exact(km)
            if match:
                matches.append(km)
        return matches

    def find_in_keymap_exact(self, keymap: KeyMap) -> Optional[KeyMapItem]:
        """Find zero or one KeyMapItem in the given KeyMap that is an exact match
        with this in its operator, parameters, and key binding.
        More than one will result in an error.
        """
        matches = self.find_in_keymap_exact_multi(keymap)
        if len(matches) > 1:
            # This should happen only if an addon dev or a user creates two keymaps
            # that are identical in everything except their ``repeat`` flag.
            raise KeyMapException(
                "More than one KeyMapItems match this PyKeyMapItem: \n"
                + str(self)
                + "\n".join([str(match) for match in matches])
            )
        if matches:
            return matches[0]

    def find_in_keymap_exact_multi(self, keymap: KeyMap) -> List[KeyMapItem]:
        """Return KeyMapItems in the given KeyMap that are an exact match with
        this PyKeyMapItem in its operator, parameters, and key binding.
        """
        return [kmi for kmi in keymap.keymap_items if self.compare_to_kmi_exact(kmi)]

    def compare_to_kmi_exact(self, kmi: KeyMapItem) -> bool:
        """Return whether we have the same operator, params, and trigger
        as the passed KeyMapItem.
        """
        return self.compare_to_kmi_by_operator(
            kmi, match_kwargs=True
        ) and self.compare_to_kmi_by_trigger(kmi)

    def find_in_keymap_by_operator(
        self, keymap: KeyMap, *, match_kwargs=True
    ) -> List[KeyMapItem]:
        """Return all KeyMapItems in the given KeyMap, which triggers the given
        operator with the given parameters.
        """
        return [
            kmi
            for kmi in keymap.keymap_items
            if self.compare_to_kmi_by_operator(kmi, match_kwargs=match_kwargs)
        ]

    def compare_to_kmi_by_operator(self, kmi: KeyMapItem, *, match_kwargs=True) -> bool:
        """Return whether we have the same operator
        (and optionally operator params) as the passed KMI.
        """
        if kmi.idname != self.op_idname:
            return False

        if not match_kwargs:
            return True

        # Check for mismatching default-ness of operator parameters.
        if set(kmi.properties.keys()) != set(self.op_kwargs.keys()):
            # This happens when the parameter overrides specified in the KMI
            # aren't the same as what we're searching for.
            return False

        # Check for mismatching values of operator parameters.
        for prop_name in kmi.properties.keys():
            # It's important to use getattr() instead of dictionary syntax here,
            # otherwise enum values will be integers instead of identifier strings.
            value = getattr(kmi.properties, prop_name)

            if value != self.op_kwargs[prop_name]:
                return False

        return True

    def find_in_keymap_conflicts(self, keymap: KeyMap) -> List[KeyMapItem]:
        """Return any KeyMapItems in the given KeyMap which are bound to the
        same key combination.
        """
        return [
            kmi for kmi in keymap.keymap_items if self.compare_to_kmi_by_trigger(kmi)
        ]

    def compare_to_kmi_by_trigger(self, kmi: KeyMapItem) -> bool:
        """Return whether we have the same trigger settings as the passed KMI."""
        return (
            kmi.type == self.key_id
            and kmi.value == self.event_type
            and kmi.any == self.any
            and kmi.ctrl == self.ctrl
            and kmi.alt == self.alt
            and kmi.shift == self.shift
            and kmi.oskey == self.oskey
            and kmi.key_modifier == self.key_modifier
            and kmi.direction == self.direction
        )

    def get_user_kmis(self, context=None) -> List[KeyMapItem]:
        """Return all matching KeyMapItems in the user keyconfig."""
        if not context:
            context = bpy.context
        user_kconf = context.window_manager.keyconfigs.user
        matches = []
        for km in user_kconf.keymaps:
            for kmi in km.keymap_items:
                if self.compare_to_kmi_exact(kmi):
                    matches.append(kmi)
        return matches

    def update(self, **kwargs):
        """Update all KeyMapItems with the passed keyword arguments."""
        for key, value in kwargs.items():
            for kmi in self.get_user_kmis():
                setattr(kmi, key, value)

            setattr(self, key, value)

    def __str__(self) -> str:
        """Return an informative but compact string representation."""
        ret = f"PyKeyMapItem: < {self.key_string}"
        if self.op_idname:
            op = find_operator_class_by_bl_idname(self.op_idname)
            if not op:
                ret += " | " + self.op_idname + " (Unregistered)"
            else:
                op_ui_name = op.name if hasattr(op, 'name') else op.bl_idname
                op_class_name = op.bl_rna.identifier
                ret += " | " + op_ui_name + f" | {self.op_idname} | {op_class_name}"
                if self.op_kwargs:
                    ret += " | " + str(self.op_kwargs)
        else:
            ret += " | (No operator assigned.)"

        return ret + " >"

    def __repr__(self):
        """Return a string representation that evaluates back to this object."""
        pretty_kwargs = str(self.op_kwargs).replace(", ", ",\n")
        return (
            "PyKeyMapItem(\n"
            f"    op_idname='{self.op_idname}',\n"
            f"    key_id='{self.key_id}',\n"
            f"    event_type='{self.event_type}',\n"
            "\n"
            f"    any={self.any},\n"
            f"    ctrl={self.ctrl},\n"
            f"    alt={self.alt},\n"
            f"    shift={self.shift},\n"
            f"    oskey={self.oskey},\n"
            f"    key_modifier='{self.key_modifier}',\n"
            f"    direction='{self.direction}',\n"
            f"    repeat='{self.repeat}',\n"
            "\n"
            f"    op_kwargs={pretty_kwargs}\n"
            ")"
        )


def get_enum_values(bpy_type, enum_prop_name: str) -> Dict[str, Tuple[str, str]]:
    """Given a registered EnumProperty's owner and name, return the enum's
    possible states as a dictionary, mapping the enum identifiers to a tuple
    of its name and description.

    :param bpy_type: The RNA type that owns the Enum property
    :param str enum_prop_name: The name of the Enum property
    :return: A dictionary mapping the enum's identifiers to its name and description
    :rtype: dict{str: (str, str)}
    """

    # If it's a Python Operator.
    if isinstance(bpy_type, Operator):
        try:
            enum_items = bpy_type.__annotations__[enum_prop_name].keywords['items']
            return {e[0]: (e[1], e[2]) for e in enum_items}
        except:
            return

    # If it's a built-in operator.
    enum_items = bpy_type.bl_rna.properties[enum_prop_name].enum_items
    return {e.identifier: (e.name, e.description) for e in enum_items}


def get_all_keymap_names() -> List[str]:
    """Returns a list of all keymap names in Blender.

    :return: A list of all valid keymap names
    :rtype: list[str]
    """
    return bpy.context.window_manager.keyconfigs.default.keymaps.keys()


def get_ui_types_of_keymap(keymap_name: str) -> Tuple[str, str]:
    # The default KeyConfig contains all the possible valid KeyMap names,
    # with the correct space_type and region_type already assigned.
    kc_default = bpy.context.window_manager.keyconfigs.default
    # This is useful to acquire the correct parameters for new KeyMapItems,
    # since having the wrong params causes the KeyMapItem to fail silently.
    check_keymap_name(keymap_name)

    km = kc_default.keymaps.get(keymap_name)
    assert km, f"Error: KeyMap not found: '{keymap_name}'"

    return km.space_type, km.region_type


def find_operator_class_by_bl_idname(bl_idname: str):
    """
    Returns the class of the operator registered with the given bl_idname.

    :param str bl_idname: Identifier of the operator to find
    :return: Class of the operator registered with the given bl_idname
    :rtype: bpy.types.Operator (for Python ops) or bpy_struct (for built-ins)
    """

    # Try Python operators first.
    for cl in Operator.__subclasses__():
        if not hasattr(cl, 'bl_idname'):
            # This can happen with mix-in classes.
            continue
        if cl.bl_idname == bl_idname:
            return cl

    # Then built-ins.
    module_name, op_name = bl_idname.split(".")
    module = getattr(bpy.ops, module_name)
    if not module:
        return
    op = getattr(module, op_name)
    if not op:
        return
    return op.get_rna_type()


class KeyMapException(Exception):
    """Raised when a KeyMapItem cannot (un)register."""

    pass


def check_keymap_name(keymap_name: str):
    """Raise a KeyMapException if the keymap_name isn't a valid KeyMap name that
    actually exists in Blender's keymap system.
    """
    all_km_names = get_all_keymap_names()
    is_valid = keymap_name in all_km_names
    if not is_valid:
        print("All valid keymap names:")
        print("\n".join(all_km_names))
        raise KeyMapException(
            f'"{keymap_name}" is not a valid keymap name. Must be one of the above.'
        )


def check_key_id(key_id: str):
    """Raise a KeyMapException if the key_id isn't one that actually exists
    in Blender's keymap system.
    """
    all_valid_key_identifiers = get_enum_values(KeyMapItem, 'type')
    is_valid = key_id in all_valid_key_identifiers
    if not is_valid:
        print("All valid key identifiers and names:")
        print("\n".join(list(all_valid_key_identifiers.items())))
        raise KeyMapException(
            f'"{key_id}" is not a valid key identifier. Must be one of the above.'
        )


def check_event_type(event_type: str):
    """Raise a KeyMapException if the event_type isn't one that actually exists
    in Blender's keymap system.
    """
    all_valid_event_types = get_enum_values(KeyMapItem, 'value')
    is_valid = event_type in all_valid_event_types
    if not is_valid:
        print("All valid event names:")
        print("\n".join(list(all_valid_event_types.keys())))
        raise KeyMapException(
            f'"{event_type}" is not a valid event type. Must be one of the above.'
        )
    return is_valid

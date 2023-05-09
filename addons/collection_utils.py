import bpy
from . import pme
from .layout_helper import lh
from .bl_utils import ConfirmBoxHandler


def sort_collection(collection, key, data=None, idx_prop=None):
    cur_name = None
    if data and idx_prop is not None:
        cur_name = collection[getattr(data, idx_prop)].name

    items = [item for item in collection]
    items.sort(key=key)
    items = [item.name for item in items]

    idx = len(items) - 1
    while idx > 0:
        name = items[idx]
        if collection[idx] != collection[name]:
            idx1 = collection.find(name)
            collection.move(idx1, idx)
        idx -= 1

    if cur_name:
        setattr(data, idx_prop, collection.find(cur_name))


def move_item(collection, old_idx, new_idx, indices=None):
    collection.move(old_idx, new_idx)

    if indices:
        n = len(indices)
        for i in range(n):
            if indices[i] == old_idx:
                indices[i] = new_idx
            elif old_idx < indices[i] <= new_idx:
                indices[i] -= 1
            elif new_idx <= indices[i] < old_idx:
                indices[i] += 1
        return indices[0] if n == 1 else indices

    return None


def remove_item(collection, idx, indices=None):
    collection.remove(idx)

    if indices:
        n = len(indices)
        for i in range(n):
            if indices[i] > idx:
                indices[i] -= 1
        return indices[0] if n == 1 else indices

    return None


def find_by(collection, key, value):
    for item in collection:
        item_value = getattr(item, key, None)
        if item_value and item_value == value:
            return item

    return None


class AddItemOperator:
    bl_label = "Add Item"
    bl_description = "Add an item"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})

    def get_collection(self):
        return None

    def finish(self, item):
        pass

    def execute(self, context):
        collection = self.get_collection()
        item = collection.add()

        idx = len(collection) - 1
        if 0 <= self.idx < idx:
            collection.move(idx, self.idx)
            item = collection[self.idx]

        self.finish(item)
        return {'FINISHED'}


class MoveItemOperator:
    label_prop = "name"
    bl_idname = None
    bl_label = "Move Item"
    bl_description = "Move the item"
    bl_options = {'INTERNAL'}

    old_idx: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})
    old_idx_last: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})
    new_idx: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})
    swap: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def get_collection(self):
        return None

    def get_icon(self, item, idx):
        return 'SPACE2' if idx == self.old_idx else 'SPACE3'

    def get_title(self):
        return "Move Item"

    def get_title_icon(self):
        return 'ARROW_LEFTRIGHT' if self.swap else 'FORWARD'

    def filter_item(self, item, idx):
        return True

    def draw_menu(self, menu, context):
        lh.lt(menu.layout)
        collection = self.get_collection()

        lh.label(self.get_title(), self.get_title_icon())
        lh.sep()

        for i, item in enumerate(collection):
            if not self.filter_item(item, i):
                continue

            name = getattr(item, self.label_prop, None) or "..."
            icon = self.get_icon(item, i)

            lh.operator(
                self.bl_idname, name, icon,
                old_idx=self.old_idx,
                old_idx_last=self.old_idx_last,
                new_idx=i,
                swap=self.swap
            )

    def finish(self):
        pass

    def execute(self, context):
        collection = self.get_collection()
        if self.old_idx < 0 or self.old_idx >= len(collection):
            return {'CANCELLED'}

        if self.old_idx_last >= 0 and (
                self.old_idx_last >= len(collection) or
                self.old_idx_last < self.old_idx):
            return {'CANCELLED'}

        if self.new_idx == -1:
            bpy.context.window_manager.popup_menu(self.draw_menu)
            return {'FINISHED'}

        if self.new_idx < 0 or self.new_idx >= len(collection):
            return {'CANCELLED'}

        if self.new_idx != self.old_idx:
            if self.old_idx_last < 0:
                collection.move(self.old_idx, self.new_idx)

                if self.swap:
                    swap_idx = self.new_idx - 1 \
                        if self.old_idx < self.new_idx \
                        else self.new_idx + 1
                    if swap_idx != self.old_idx:
                        collection.move(swap_idx, self.old_idx)

            else:
                if self.new_idx < self.old_idx:
                    for i in range(self.old_idx, self.old_idx_last + 1):
                        collection.move(self.old_idx_last, self.new_idx)
                else:
                    for i in range(0, self.old_idx_last - self.old_idx + 1):
                        collection.move(
                            self.old_idx_last - i, self.new_idx - i)

            self.finish()

        return {'FINISHED'}


class RemoveItemOperator(ConfirmBoxHandler):
    bl_label = "Remove Item"
    bl_description = "Remove the item"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def get_collection(self):
        return None

    def finish(self):
        pass

    def on_confirm(self, value):
        if not value:
            return

        collection = self.get_collection()
        if self.idx < 0 or self.idx >= len(collection):
            return

        collection.remove(self.idx)

        self.finish()


class BaseCollectionItem(bpy.types.PropertyGroup):
    pass


def register():
    pme.context.add_global("find_by", find_by)

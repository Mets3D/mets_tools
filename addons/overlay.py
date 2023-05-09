import bpy
import blf
import bgl
from time import time
from .addon import ADDON_ID, prefs, uprefs, ic, is_28
from .utils import multiton
from .layout_helper import split
from . import pme
from . import constants as CC

OVERLAY_ALIGNMENT_ITEMS = (
    ('TOP', "Top", ""),
    ('TOP_LEFT', "Top Left", ""),
    ('TOP_RIGHT', "Top Right", ""),
    ('BOTTOM', "Bottom", ""),
    ('BOTTOM_LEFT', "Bottom Left", ""),
    ('BOTTOM_RIGHT', "Bottom Right", ""),
)


def blf_color(r, g, b, a):
    if is_28():
        blf.color(0, r, g, b, a)
    else:
        bgl.glColor4f(r, g, b, a)


class Timer:
    def __init__(self, t):
        self.reset(t)

    def update(self):
        t1 = time()
        self.t -= t1 - self.t0
        self.t0 = t1

        return self.t <= 0

    def reset(self, t):
        self.t = t
        self.t0 = time()

    def finished(self):
        return self.t <= 0


class SpaceGroup:
    def __init__(self, bl_type):
        self.type = bl_type
        self.handler = None
        self.bl_timer = None
        self.timer = Timer(1)
        self.text = None
        self.data = None
        self.alignment = 'TOP'
        self.offset_x = 10
        self.offset_y = 10
        self.shadow = True


space_groups = dict()


def add_space_group(id, tp_name):
    tp = getattr(bpy.types, tp_name, None)
    if not tp:
        return

    space_groups[id] = SpaceGroup(tp)


add_space_group("CLIP_EDITOR", "SpaceClipEditor")
add_space_group("CONSOLE", "SpaceConsole")
add_space_group("DOPESHEET_EDITOR", "SpaceDopeSheetEditor")
add_space_group("FILE_BROWSER", "SpaceFileBrowser")
add_space_group("GRAPH_EDITOR", "SpaceGraphEditor")
add_space_group("IMAGE_EDITOR", "SpaceImageEditor")
add_space_group("INFO", "SpaceInfo")
add_space_group("LOGIC_EDITOR", "SpaceLogicEditor")
add_space_group("NLA_EDITOR", "SpaceNLA")
add_space_group("NODE_EDITOR", "SpaceNodeEditor")
add_space_group("OUTLINER", "SpaceOutliner")
add_space_group("PROPERTIES", "SpaceProperties")
add_space_group("SEQUENCE_EDITOR", "SpaceSequenceEditor")
add_space_group("TEXT_EDITOR", "SpaceTextEditor")
add_space_group("TIMELINE", "SpaceTimeline")
add_space_group(CC.UPREFS, "Space" + CC.UPREFS_CLS)
add_space_group("VIEW_3D", "SpaceView3D")

del add_space_group


_line_y = 0


def _draw_line(space, r, g, b, a):
    ctx = bpy.context
    blf.size(0, space.size, 72)
    w, h = blf.dimensions(0, space.text)

    global _line_y

    if "LEFT" in space.alignment:
        x = space.offset_x
    elif "RIGHT" in space.alignment:
        x = ctx.region.width - w - space.offset_x
    else:
        x = 0.5 * ctx.region.width - 0.5 * w

    if "TOP" in space.alignment:
        _line_y += space.size + 3
        y = ctx.region.height - _line_y - space.offset_y
    else:
        y = _line_y + space.offset_y
        _line_y += space.size + 3

    blf.position(0, x, y, 0)
    blf_color(r, g, b, a)
    blf.draw(0, space.text)


def _draw_handler(space):
    r, g, b, a = space.color
    p = 1 if space.timer.t >= 0.3 else space.timer.t / 0.3

    if space.shadow:
        blf.enable(0, blf.SHADOW)
        blf.shadow_offset(0, 1, -1)
        blf.shadow(0, 5, 0.0, 0.0, 0.0, a * 0.4 * p)

    global _line_y
    _line_y = 0
    if space.text:
        _draw_line(space, r, g, b, a * p)

    blf.disable(0, blf.SHADOW)


class Painter:
    def __init__(self):
        self.overlay = None


class Style:
    def __init__(self, color=None, size=None):
        self.color = color or (1, 1, 1, 1)
        self.size = size or 30

    def update(self, color=None, size=None):
        if color:
            self.color = color
        if size:
            self.size = size


class Text:
    default_style = Style()
    secondary_style = Style()

    def __init__(self, text, style=None, size=0):
        self.style = style if style else self.default_style
        self._size = size
        self.update(text)

    @property
    def size(self):
        return self._size or self.style.size

    def center(self, width):
        return int(0.5 * (width - self.width))

    def right(self, width):
        return width - self.width

    def update(self, text):
        self.text = text
        blf.size(0, self.size, 72)
        self.width, self.height = blf.dimensions(0, text)

    def draw(self, x, y):
        blf_color(*self.style.color)
        blf.position(0, x, y, 0)
        blf.size(0, self.size, 72)
        blf.draw(0, self.text)


class Col:
    def __init__(self):
        self.width = 0
        self.cells = []

    def add_cell(self, text, style, size):
        self.cells.append(Text(text, style, size))

    def init(self):
        self.width = 0
        for cell in self.cells:
            self.width = max(self.width, cell.width)


class TablePainter(Painter):
    spacing_x = 8
    spacing_y = 1
    spacing_h = 5
    line_width = 2
    col_style_scale = 0.7
    col_styles = (Text.secondary_style, Text.default_style)

    def __init__(self, num_cols, data, header=None, align_right=1):
        Painter.__init__(self)

        self.cols = []
        self.num_cols = num_cols
        self.header = Text(header) if header else None
        self.align_right = align_right

        self.update(data)

    def update(self, data=None):
        pr = prefs().overlay
        self.col_size = pr.size * 1

        if data is not None:
            self.cols.clear()

            for i in range(0, self.num_cols):
                self.cols.append(Col())

            if isinstance(data, str):
                cells = data.split("|") if self.num_cols > 1 else (data,)
            else:
                cells = data
            col_idx = 0
            for cell in cells:
                col = self.cols[col_idx]
                col_style = self.col_styles[col_idx % 2]
                col.add_cell(
                    cell, col_style,
                    round(col_style.size * self.col_style_scale))
                col_idx = (col_idx + 1) % self.num_cols

        self.width = 0
        self.height = 0
        if self.header:
            self.width = self.header.width
            self.height += self.header.height

        width = self.spacing_x * (self.num_cols - 1)
        height = 0
        for col in self.cols:
            col.init()
            num_cells = len(col.cells)
            width += col.width
            height = max(
                height,
                self.col_size * num_cells + self.spacing_y * (num_cells - 1))
        self.width = max(self.width, width)
        if height:
            if self.header:
                self.height += self.spacing_y
            self.height += height

        r = bpy.context.region

        if 'LEFT' in pr.alignment:
            self.x = pr.offset_x
        elif 'RIGHT' in pr.alignment:
            self.x = r.width - self.width - pr.offset_x
        else:
            self.x = 0.5 * r.width - 0.5 * self.width

        if 'TOP' in pr.alignment:
            self.y = r.height - pr.offset_y
        else:
            self.y = pr.offset_y + self.height

    def draw(self):
        if self.header:
            x = round(self.x + self.header.center(self.width))
            y = round(self.y - self.header.size)
            self.header.draw(x, y)

            if not is_28():
                bgl.glLineWidth(self.line_width)
                blf_color(*self.header.style.color)
                bgl.glBegin(bgl.GL_LINES)
                bgl.glVertex2f(self.x, y - self.spacing_h - self.line_width)
                bgl.glVertex2f(
                    self.x + self.width, y - self.spacing_h - self.line_width)
                bgl.glEnd()

        x = 0
        for i in range(0, self.num_cols - self.align_right):
            col = self.cols[i]
            y = -self.header.size - self.spacing_y - 2 * self.spacing_h - \
                self.line_width if self.header else 0
            for cell in col.cells:
                cell.draw(self.x + x, self.y + y - self.col_size)
                y -= self.col_size + self.spacing_y
            x += col.width + self.spacing_x

        x = self.width
        for i in range(0, self.align_right):
            col = self.cols[self.num_cols - i - 1]
            y = -self.header.size - self.spacing_y - 2 * self.spacing_h - \
                self.line_width if self.header else 0
            for cell in col.cells:
                cell.draw(self.x + x - cell.width, self.y + y - self.col_size)
                y -= self.col_size + self.spacing_y
            x -= col.width + self.spacing_x


@multiton
class Overlay:
    def __init__(self, id=None):
        self.id = id or bpy.context.area.type
        self.space = type(bpy.context.space_data)
        self.handler = None

        self.painters = []
        self.win_area = None

        self.alpha = 1

    def add_painter(self, painter):
        if painter.overlay:
            return
        painter.overlay = self
        self.painters.append(painter)

    @staticmethod
    def draw(self):
        pr = prefs().overlay

        if pr.shadow:
            a = 1
            blf.enable(0, blf.SHADOW)
            blf.shadow_offset(0, 1, -1)
            blf.shadow(0, 5, 0.0, 0.0, 0.0, a * 0.4 * self.alpha)

        for p in self.painters:
            p.draw()

        if pr.shadow:
            blf.disable(0, blf.SHADOW)

    def show(self):
        if self.handler:
            return
        self.handler = self.space.draw_handler_add(
            self.__class__.draw, (self,), 'WINDOW', 'POST_PIXEL')

        self.win_area = bpy.context.area
        # for r in bpy.context.area.regions:
        #     if r.type == 'WINDOW':
        #         self.win_area = r
        #         break

        self.tag_redraw()

    def hide(self):
        if self.handler:
            self.space.draw_handler_remove(self.handler, 'WINDOW')
            self.handler = None

        self.painters.clear()
        self.tag_redraw()
        self.win_area = None

    def tag_redraw(self):
        if self.win_area:
            self.win_area.tag_redraw()


class OverlayPrefs(bpy.types.PropertyGroup):
    def size_update(self, context):
        Text.default_style.size = self.size
        Text.secondary_style.size = self.size
        # TablePainter.col_styles[0].size = \
        #     round(self.size * TablePainter.col_style_scale)
        # TablePainter.col_styles[1].size = \
        #     round(self.size * TablePainter.col_style_scale)

        TablePainter.line_width = 1 if self.size < 18 else 2

    def color_update(self, context):
        Text.default_style.update(list(self.color))

    def color2_update(self, context):
        Text.secondary_style.update(list(self.color2))

    overlay: bpy.props.BoolProperty(
        name="Use Overlay",
        description="Use overlay for stack keys and modal operators",
        default=True)
    size: bpy.props.IntProperty(
        name="Font Size", description="Font size",
        default=24, min=10, max=50, options={'SKIP_SAVE'},
        update=size_update)
    color: bpy.props.FloatVectorProperty(
        name="Color", description="Color",
        default=(1, 1, 1, 1), subtype='COLOR', size=4, min=0, max=1,
        update=color_update)
    color2: bpy.props.FloatVectorProperty(
        name="Color", description="Color",
        default=(1, 1, 0, 1), subtype='COLOR', size=4, min=0, max=1,
        update=color2_update)
    alignment: bpy.props.EnumProperty(
        name="Alignment",
        description="Alignment",
        items=OVERLAY_ALIGNMENT_ITEMS,
        default='TOP')
    duration: bpy.props.FloatProperty(
        name="Duration", subtype='TIME', min=1, max=10, default=2, step=10)
    offset_x: bpy.props.IntProperty(
        name="Offset X", description="Offset from area edges",
        subtype='PIXEL', default=10, min=0)
    offset_y: bpy.props.IntProperty(
        name="Offset Y", description="Offset from area edges",
        subtype='PIXEL', default=10, min=0)
    shadow: bpy.props.BoolProperty(
        name="Use Shadow", description="Use shadow", default=True)

    def draw(self, layout):
        # if not self.overlay:
        #     layout.prop(self, "overlay", toggle=True)
        # else:
        # layout.prop(self, "overlay")

        col = layout.column(align=True)
        col.active = self.overlay

        row = split(col, 0.5, True)
        row1 = row.row(align=True)
        row1.prop(self, "color", text="")
        row1.prop(self, "color2", text="")
        row1.prop(self, "shadow", text="", icon=ic('META_BALL'))

        row.prop(self, "size")
        row.prop(self, "duration")

        row = split(col, 0.5, True)
        row.prop(self, "alignment", text="")
        row.prop(self, "offset_x")
        row.prop(self, "offset_y")


class PME_OT_overlay(bpy.types.Operator):
    bl_idname = "pme.overlay"
    bl_label = ""
    bl_options = {'INTERNAL'}

    is_running = False

    text: bpy.props.StringProperty(options={'SKIP_SAVE'})
    alignment: bpy.props.EnumProperty(
        name="Alignment",
        description="Alignment",
        items=OVERLAY_ALIGNMENT_ITEMS,
        default='TOP', options={'SKIP_SAVE'})
    duration: bpy.props.FloatProperty(
        name="Duration", subtype='TIME', min=1, default=2, step=10,
        options={'SKIP_SAVE'})
    offset_x: bpy.props.IntProperty(
        name="Offset X", description="Offset from area edges",
        subtype='PIXEL', default=10, min=0, options={'SKIP_SAVE'})
    offset_y: bpy.props.IntProperty(
        name="Offset Y", description="Offset from area edges",
        subtype='PIXEL', default=10, min=0, options={'SKIP_SAVE'})

    def modal(self, context, event):
        if event.type == 'TIMER':
            num_handlers = 0
            active_areas = set()
            for name, space in space_groups.items():
                if not space.handler:
                    continue

                active_areas.add(name)

                if space.timer.update():
                    space.type.draw_handler_remove(
                        space.handler, 'WINDOW')
                    space.handler = None
                else:
                    num_handlers += 1

            for area in context.screen.areas:
                if area.type in active_areas:
                    area.tag_redraw()

            if not num_handlers:
                context.window_manager.event_timer_remove(self.timer)
                self.timer = None
                PME_OT_overlay.is_running = False
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.area.type not in space_groups:
            return {'CANCELLED'}

        pr = uprefs().addons[ADDON_ID].preferences

        # if not pr.overlay.overlay:
        # if not hasattr(bgl, "glColor4f"):
        #     return {'CANCELLED'}

        space = space_groups[context.area.type]
        space.timer.reset(
            self.duration if "duration" in self.properties
            else pr.overlay.duration)
        space.text = self.text
        space.size = pr.overlay.size
        space.alignment = self.alignment if "alignment" in self.properties \
            else pr.overlay.alignment
        space.offset_x = self.offset_x if "offset_x" in self.properties \
            else pr.overlay.offset_x
        space.offset_y = self.offset_y if "offset_y" in self.properties \
            else pr.overlay.offset_y
        space.shadow = pr.overlay.shadow
        space.color = list(pr.overlay.color)

        if space.handler:
            return {'CANCELLED'}

        space.handler = space.type.draw_handler_add(
            _draw_handler, (space,), 'WINDOW', 'POST_PIXEL')

        if not PME_OT_overlay.is_running:
            PME_OT_overlay.is_running = True
            context.window_manager.modal_handler_add(self)
            self.timer = context.window_manager.event_timer_add(
                0.1, window=bpy.context.window)

        return {'RUNNING_MODAL'}


def overlay(text, **kwargs):
    bpy.ops.pme.overlay(text=text, **kwargs)
    return True


def register():
    opr = prefs().overlay
    Text.default_style.update(list(opr.color), opr.size)
    Text.secondary_style.update(list(opr.color2), opr.size)
    # TablePainter.col_styles[0].update(
    #     list(opr.color2), round(opr.size * TablePainter.col_style_scale))
    # TablePainter.col_styles[1].update(
    #     list(opr.color), round(opr.size * TablePainter.col_style_scale))

    pme.context.add_global("overlay", overlay)

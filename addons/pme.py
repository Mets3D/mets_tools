import bpy
from .addon import prefs, temp_prefs, print_exc


class UserData:
    def get(self, name, default=None):
        return self.__dict__.get(name, default)

    def update(self, **kwargs):
        self.__dict__.update(**kwargs)

    def __getattr__(self, name):
        return self.__dict__.get(name, None)


class PMEContext:

    def __init__(self):
        self._globals = dict(
            bpy=bpy,
            pme_context=self,
            drag_x=0,
            drag_y=0,
        )
        self.pm = None
        self.pmi = None
        self.index = None
        self.icon = None
        self.icon_value = None
        self.text = None
        self.region = None
        self.last_operator = None
        self.is_first_draw = True
        self.exec_globals = None
        self.exec_locals = None
        self.exec_user_locals = dict()
        self._layout = None
        self._event = None
        self.edit_item_idx = None

    def __getattr__(self, name):
        return self._globals.get(name, None)

    def item_id(self):
        pmi = self.pmi
        id = self.pm.name
        id += pmi.name if pmi.name else pmi.text
        id += str(self.index)
        return id

    def reset(self):
        self.is_first_draw = True
        self.exec_globals = None
        self.exec_locals = None

    def add_global(self, key, value):
        self._globals[key] = value

    @property
    def layout(self):
        return self._layout

    @layout.setter
    def layout(self, value):
        self._layout = value
        self._globals["L"] = value

    @property
    def event(self):
        return self._event

    @event.setter
    def event(self, value):
        self._event = value
        self._globals["E"] = value

        if self._event:
            if self._event.type == 'WHEELUPMOUSE':
                self._globals["delta"] = 1
            elif self._event.type == 'WHEELDOWNMOUSE':
                self._globals["delta"] = -1

    @property
    def globals(self):
        if self._globals["D"].__class__.__name__ == "_RestrictData":
            # self._globals["C"] = bpy.context
            self._globals["D"] = bpy.data
        return self._globals

    def gen_globals(self, **kwargs):
        ret = dict(
            text=self.text,
            icon=self.icon,
            icon_value=self.icon_value,
            PME=temp_prefs(),
            PREFS=prefs(),
            **kwargs
        )

        ret.update(self.exec_user_locals)
        ret.update(self.globals)

        return ret

    def eval(self, expression, globals=None, menu=None, slot=None):
        if globals is None:
            globals = self.gen_globals()

        # globals["menu"] = menu
        # globals["slot"] = slot

        value = None
        try:
            value = eval(expression, globals)
        except:
            print_exc(expression)

        return value

    def exe(self, data, globals=None, menu=None, slot=None, use_try=True):
        if globals is None:
            globals = self.gen_globals()

        # globals["menu"] = menu
        # globals["slot"] = slot

        if not use_try:
            exec(data, globals)
            return True

        try:
            exec(data, globals)
        except:
            print_exc(data)
            return False

        return True


context = PMEContext()


class PMEProp:
    def __init__(self, type, name, default, ptype='STR', items=None):
        self.name = name
        self.default = default
        self.items = items
        self.type = type
        self.ptype = ptype

    def decode_value(self, value):
        if self.ptype == 'STR':
            return value
        elif self.ptype == 'BOOL':
            return value == "True" or value == "1"
        elif self.ptype == 'INT':
            return int(value) if value else 0


class PMEProps:
    prop_map = {}

    def IntProperty(self, type, name, default=0):
        # default = "" if default == 0 else str(default)
        self.prop_map[name] = PMEProp(type, name, default, 'INT')

    def BoolProperty(self, type, name, default=False):
        # default = "1" if default else ""
        self.prop_map[name] = PMEProp(type, name, default, 'BOOL')

    def StringProperty(self, type, name, default=""):
        self.prop_map[name] = PMEProp(type, name, default, 'STR')

    def EnumProperty(self, type, name, default, items):
        self.prop_map[name] = PMEProp(type, name, default, 'STR', items)

    def __init__(self):
        self.parsed_data = {}

    def get(self, name):
        return self.prop_map.get(name, None)

    def parse(self, text):
        if text not in self.parsed_data:
            self.parsed_data[text] = ParsedData(text)

        return self.parsed_data[text]

    def encode(self, text, prop, value):
        tp, _, data = text.partition("?")

        data = data.split("&")
        lst = []
        has_prop = False
        for pr in data:
            if not pr:
                continue

            k, v = pr.split("=")
            if k not in props.prop_map:
                continue

            if k == prop:
                # v = props.prop_map[k].decode_value(value)
                v = value
                has_prop = True

            if v != props.get(k).default:
                lst.append("%s=%s" % (k, v))

        if not has_prop and value != props.prop_map[prop].default:
            lst.append("%s=%s" % (prop, value))

        lst.sort()

        text = "%s?%s" % (tp, "&".join(lst))
        return text

    def clear(self, text, *args):
        tp, _, data = text.partition("?")

        data = data.split("&")
        lst = []
        for pr in data:
            if not pr:
                continue

            k, v = pr.split("=")
            if k not in props.prop_map or k in args:
                continue

            if v != props.get(k).default:
                lst.append(pr)

        lst.sort()

        text = "%s?%s" % (tp, "&".join(lst))
        return text


props = PMEProps()


class ParsedData:

    def __init__(self, text):
        self.type, _, data = text.partition("?")

        for k, prop in props.prop_map.items():
            if prop.type == self.type:
                setattr(self, k, prop.default)

        data = data.split("&")
        for prop in data:
            if not prop:
                continue
            k, v = prop.split("=")
            if k in props.prop_map:
                setattr(self, k, props.prop_map[k].decode_value(v))

        self.is_empty = True
        for k, prop in props.prop_map.items():
            if not hasattr(self, k):
                continue
            if getattr(self, k) != prop.default:
                self.is_empty = False
                break

    def value(self, name):
        for item in props.get(name).items:
            if getattr(self, name) == item[0]:
                return item[2]

        return 0


def register():
    context.add_global("U", UserData())

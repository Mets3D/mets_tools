from rna_prop_ui import rna_idprop_ui_create

class CustomProp:
    def __init__(self, name, *, default, min=0.0, max=1.0, soft_min=None, soft_max=None, description=None, overridable=True, subtype=True):
        self.name=name
        self.default = default
        self.min = min
        self.max = max
        self.soft_min = soft_min
        self.soft_max = soft_max
        self.description = description
        self.overridable = overridable
        self.subtype = subtype

    def make_real(self, owner):
        return rna_idprop_ui_create(
            owner, 
            self.name, 
            default = self.default,
            min = self.min, 
            max = self.max, 
            soft_min = self.soft_min, 
            soft_max = self.soft_max,
            description = self.description,
            overridable = self.overridable,
            subtype = self.subtype
        )
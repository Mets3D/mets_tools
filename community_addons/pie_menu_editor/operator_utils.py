import bpy
from io import BytesIO
from itertools import chain
from tokenize import (
    tokenize, Untokenizer,
    OP, ENCODING, NAME, STRING, NUMBER, ENDMARKER, INDENT, DEDENT, NEWLINE, NL
)
from .addon import print_exc
from . import pme


class _XUntokenizer(Untokenizer):

    def compat(self, token, iterable):
        indents = []
        toks_append = self.tokens.append
        startline = token[0] in (NEWLINE, NL)
        prevstring = False

        sp_tup = (NAME, NUMBER)
        prevnum = None
        for tok in chain([token], iterable):
            toknum, tokval = tok[:2]
            if toknum == ENCODING:
                self.encoding = tokval
                prevnum = toknum
                continue

            if toknum in sp_tup:
                tokval += ' '
            elif toknum == OP and prevnum in sp_tup:
                self.tokens[-1] = self.tokens[-1][:-1]

            prevnum = toknum

            if toknum == STRING:
                if prevstring:
                    tokval = ' ' + tokval
                prevstring = True
            else:
                prevstring = False

            if toknum == INDENT:
                indents.append(tokval)
                continue
            elif toknum == DEDENT:
                indents.pop()
                continue
            elif toknum == OP and tokval in ",;":
                tokval += " "
            elif toknum in (NEWLINE, NL):
                startline = True
            elif startline and indents:
                toks_append(indents[-1])
                startline = False
            toks_append(tokval)


def _untokenize(stm):
    return _XUntokenizer().untokenize(stm)


def _join_statements(stms, encoding):
    ret = [(ENCODING, encoding)]

    for i, stm in enumerate(stms):
        if i > 0:
            ret.append((OP, ";"))

        for tok in stm:
            ret.append(tok)

    ret.append((ENDMARKER, ""))
    return ret


def _split_statement(text):
    text = text.strip(" ;")

    stms = []
    stm = []
    stms.append(stm)
    encoding = None
    try:
        g = tokenize(BytesIO(text.encode('utf-8')).readline)
        encoding = None
        for tp, value, _, _, _ in g:
            if tp == ENDMARKER:
                continue
            if tp == ENCODING:
                encoding = value
                continue
            if tp == OP and value == ";":
                stm = []
                stms.append(stm)
            else:
                stm.append((tp, value))
    except:
        print_exc()
        return [], None

    return stms, encoding


def _is_operator(stm):
    idx = -1
    n = len(stm)

    if n > 0 and stm[0][1] == "O":
        idx = 2
    elif n > 2 and stm[0][1] == "bpy" and stm[2][1] == "ops":
        idx = 4

    if idx + 3 >= n or stm[idx + 3][0] != OP or stm[idx + 3][1] != "(":
        return -1

    d = 1
    for i in range(idx + 4, n):
        if stm[i][0] == NEWLINE:
            continue

        if d == 0:
            return -1

        if stm[i][1] == "(":
            d += 1
        elif stm[i][1] == ")":
            d -= 1

    return idx


def _extract_args(stm, idx, encoding):
    args = []
    arg = None
    depth = 0
    equal = False
    has_pos_args = False
    pos_args = []
    for i in range(idx, len(stm)):
        tp, value = stm[i]

        if tp == OP:
            if value in "([{":
                depth += 1
                if depth == 1:
                    equal = False
                    arg = [(ENCODING, encoding)]
                    args.append(arg)
                    if value == "(":
                        continue

            elif value in ")]}":
                depth -= 1
                if depth == 0:
                    if len(arg) == 1:
                        args.pop()

                    has_pos_args = has_pos_args or \
                        len(args) > 0 and not equal
                    if args and not equal:
                        pos_args.append(args.pop())

                    arg = None

            if depth == 1:
                if value == "=":
                    equal = True

                if value == ",":
                    if args and not equal:
                        pos_args.append(args.pop())
                    arg = [(ENCODING, encoding)]
                    args.append(arg)
                    has_pos_args = has_pos_args or not equal
                    equal = False
                else:
                    arg.append(stm[i])
            else:
                if arg:
                    arg.append(stm[i])

        else:
            if arg:
                arg.append(stm[i])

    return args, pos_args


def to_bl_idname(idname):
    tp = getattr(bpy.types, idname, None)
    if tp and hasattr(tp, "bl_idname"):
        return getattr(tp, "bl_idname")

    return idname.lower().replace("_ot_", ".")


def to_idname(bl_idname):
    op = operator(bl_idname)
    if op:
        return op.idname()

    return None


def operator(bl_idname):
    try:
        ret = eval("bpy.ops.%s" % bl_idname)
        get_rna_type(ret)
    except:
        ret = None

    return ret


def operator_label(value):
    if isinstance(value, str):
        if "." not in value:
            value = to_bl_idname(value)

        op = operator(value)
        value = op and get_rna_type(op)

    if not value:
        return ""

    label = value.bl_rna.name
    if not label:
        label = value.bl_rna.identifier
        if "_OT_" in label:
            label = label.split("_OT_")[-1]
            label = label.replace("_", " ").title()

    return label


def add_default_args(text):
    stms, encoding = _split_statement(text)

    if len(stms) != 1:
        return text

    stm = stms[0]
    idx = _is_operator(stm)
    if idx == -1:
        return text

    sargs, spos_args = _extract_args(stm, idx, encoding)

    idx += 4
    if not spos_args:
        default_args = [
            (STRING, "'INVOKE_DEFAULT'"),
            (OP, ","),
            (NAME, "True"),
        ]
        if sargs:
            default_args.append((OP, ","))

        stm[idx:idx] = default_args

    stm = _join_statements(stms, encoding)

    return _untokenize(stm)


def parse_pos_args(pos_args):
    ctx = None
    exec_ctx = 'INVOKE_DEFAULT'
    undo = True

    if pos_args:
        for a in pos_args:
            a = eval(a)
            if isinstance(a, str):
                exec_ctx = a
            elif isinstance(a, dict):
                ctx = a
            elif isinstance(a, bool):
                undo = a

    return ctx, exec_ctx, undo


def find_operator(text):
    stms, encoding = _split_statement(text)

    if len(stms) != 1:
        return None, None, None

    s = stms[0]
    idx = _is_operator(s)
    if idx == -1:
        return None, None, None

    if s[idx][0] != NAME or s[idx + 1][0] != OP or s[idx + 2][0] != NAME:
        return None, None, None

    bl_idname = "%s.%s" % (s[idx][1], s[idx + 2][1])

    sargs, spos_args = _extract_args(s, idx, encoding)

    args = []
    for sarg in sargs:
        args.append(_untokenize(sarg).strip())

    if len(args) == 1 and not args[0]:
        args.pop()

    pos_args = []
    for sarg in spos_args:
        pos_args.append(_untokenize(sarg).strip())

    if len(pos_args) == 1 and not pos_args[0]:
        pos_args.pop()

    return bl_idname, args, pos_args


def find_statement(text):
    stms, encoding = _split_statement(text)

    if len(stms) != 1:
        return None, None

    stm = stms[0]
    depth = 0

    prop = ""
    prop_value = None
    for tp, value in stm:
        if tp == OP:
            if value in "([{":
                depth += 1

            elif value in ")]}":
                depth -= 1

            elif value == "=" and depth == 0:
                prop_value = ""
                continue

            elif value == ".":
                pass

            # else:
            #     return None, None

        if prop_value is None:
            prop += value
        else:
            prop_value += value

    if prop_value is None:
        prop = None

    return prop, prop_value


def _apply_properties(dct, key, value):
    if isinstance(value, dict):
        if key not in dct:
            dct[key] = dict()

        d = getattr(dct, key, None)
        if d is None:
            return None

        for k, v in value.items():
            _apply_properties(d, k, v)
    else:
        if hasattr(dct, key):
            try:
                setattr(dct, key, value)
            except:
                pass


def apply_properties(bl_rna_props, args, pm=None, pmi=None):
    exec_globals = pme.context.gen_globals()
    exec_globals.update(menu=pm.name, slot=pmi.name)
    for arg in args:
        key, _, value = arg.partition("=")
        key = key.strip()
        value = pme.context.eval(value.strip(), exec_globals)
        _apply_properties(bl_rna_props, key, value)


def compare_operators(o1, o2):
    return o1 and o2 and o1.as_pointer() == o2.as_pointer()


def get_rna_type(op):
    if isinstance(op, str):
        try:
            op = eval("bpy.ops.%s" % op)
        except:
            return None

    if hasattr(op, "get_rna"):
        return op.get_rna().rna_type
    else:
        return op.get_rna_type()

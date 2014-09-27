from __future__ import absolute_import

from lib2to3 import fixer_util
from lib2to3.pytree import Leaf, Node
from lib2to3.pygram import python_symbols as syms
from lib2to3.pgen2 import token

__version__ = '0.3'


def _is_import_stmt(node):
    return (node.type == syms.simple_stmt and node.children and
            node.children[0].type in (syms.import_name, syms.import_from))

def _new_touch_import(package, name, node):
    """ Adds an import statement if it was not already imported at top-level. """

    root = fixer_util.find_root(node)

    # Search existing top-level imports.
    # If there are existing __future__ imports, remember the location after them.
    insert_pos = 0
    for idx, node in enumerate(root.children):
        if _is_import_stmt(node):
            for offset, node2 in enumerate(root.children[idx:]):
                if _is_import_binding(node2, name, package):
                    # Already imported.
                    return
                if _is_future_import(node):
                    insert_pos = idx + offset
        if not _is_import_stmt(node):
            continue
        for offset, node2 in enumerate(root.children[idx:]):
            if not _is_import_stmt(node2):
                break
        insert_pos = idx + offset
        break

    # If there are no __future__ imports, find the docstring.
    # If that also fails, find the first non-blank, non-comment line.
    if insert_pos == 0:
        if root.children:
            node = root.children[0]
            if (node.type == syms.simple_stmt and node.children and
                node.children[0].type == token.STRING):
                insert_pos = 1

    if package is None:
        import_ = Node(syms.import_name, [
            Leaf(token.NAME, u"import"),
            Leaf(token.NAME, name, prefix=u" ")
        ])
    else:
        import_ = fixer_util.FromImport(package, [Leaf(token.NAME, name, prefix=u" ")])

    children = [import_, fixer_util.Newline()]
    root.insert_child(insert_pos, Node(syms.simple_stmt, children))


def _is_import_binding(node, name, package=None):
    """ Will return node if node will import name, or node
        will import * from package.  None is returned otherwise. """

    if node.type == syms.import_name and not package:
        imp = node.children[1]
        if imp.type == syms.dotted_as_names:
            for child in imp.children:
                if child.type == syms.dotted_as_name:
                    if child.children[2].value == name:
                        return node
                elif child.type == token.NAME and child.value == name:
                    return node
        elif imp.type == syms.dotted_as_name:
            last = imp.children[-1]
            if last.type == token.NAME and last.value == name:
                return node
        elif imp.type == token.NAME and imp.value == name:
            return node
    elif node.type == syms.import_from:
        # unicode(...) is used to make life easier here, because
        # from a.b import parses to ['import', ['a', '.', 'b'], ...]
        if package and unicode(node.children[1]).strip() != package:
            return None
        n = node.children[3]
        if package and _find(u"as", n):
            # See test_from_import_as for explanation
            return None
        elif n.type == syms.import_as_names and _find(name, n):
            return node
        elif n.type == syms.import_as_name:
            child = n.children[2]
            if child.type == token.NAME and child.value == name:
                return node
        elif n.type == token.NAME and n.value == name:
            return node
        elif package and n.type == token.STAR:
            return node
    return None


def check_future_import(node):
    """If this is a future import, return set of symbols that are imported,
    else return None."""
    # node should be the import statement here
    if not (node.type == syms.simple_stmt and node.children):
        return set()
    node = node.children[0]
    # now node is the import_from node
    if not (node.type == syms.import_from and
            node.children[1].type == token.NAME and
            node.children[1].value == u'__future__'):
        return set()
    node = node.children[3]
    # now node is the import_as_name[s]
    # print(python_grammar.number2symbol[node.type])
    if node.type == syms.import_as_names:
        result = set()
        for n in node.children:
            if n.type == token.NAME:
                result.add(n.value)
            elif n.type == syms.import_as_name:
                n = n.children[0]
                assert n.type == token.NAME
                result.add(n.value)
        return result
    elif node.type == syms.import_as_name:
        node = node.children[0]
        assert node.type == token.NAME
        return set([node.value])
    elif node.type == token.NAME:
        return set([node.value])
    else:
        assert 0, "strange import"

def add_future(node, symbol):

    root = fixer_util.find_root(node)

    for idx, node in enumerate(root.children):
        if node.type == syms.simple_stmt and \
           len(node.children) > 0 and node.children[0].type == token.STRING:
            # skip over docstring
            continue
        names = check_future_import(node)
        if not names:
            # not a future statement; need to insert before this
            break
        if symbol in names:
            # already imported
            return

    import_ = fixer_util.FromImport('__future__',
                                    [Leaf(token.NAME, symbol, prefix=" ")])
    children = [import_, fixer_util.Newline()]
    root.insert_child(idx, Node(syms.simple_stmt, children))


def touch_import(package, name, node):
    add_future(node, 'absolute_import')
    fixer_util.touch_import(package, name, node)


def is_listcomp(node):
    return (isinstance(node, Node) and
             node.type == syms.atom and
             len(node.children) >= 2 and
             isinstance(node.children[0], Leaf) and
             node.children[0].value == '[' and
             isinstance(node.children[-1], Leaf) and
             node.children[-1].value == ']')

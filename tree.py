#/*************************************************************************
#
#    tree.py: simple classes for representing trees
#
#    Copyright (C) 2010 Ian Katz
#
#    This software was written by Ian Katz
#    contact: ifreecarve@gmail.com
#
#    This file is part of FontClustr.
#
#    You should have received a copy of the Apache 2.0 license
#    along with FontClustr.  If not, see <http://www.apache.org/licenses/LICENSE-2.0>
#
#*************************************************************************/


TREE_BRANCH = 0
TREE_LEAF   = 1

class tree(object):
    def type(self):
        #the type of object
        pass

    def printout(self, leaf_func):
        def printout_h(atree, acc):
            if TREE_LEAF == atree.type():
                print acc, leaf_func(atree.ptr)
            else:
                printout_h(atree.lt, "-" + acc)
                printout_h(atree.rt, "=" + acc)

        printout_h(self, "")


    def num_leaves(self):
        #helper
        def num_leaves_h(atree, acc):
            if TREE_LEAF == atree.type():
                return acc + 1
            return num_leaves_h(atree.rt, num_leaves_h(atree.lt, acc))
        return num_leaves_h(self, 0)

    def leaves(self):
        #helper
        def leaves_h(atree, acc):
            if TREE_LEAF == atree.type():
                return acc.append(atree.value)
            return leaves_h(atree.rt, leaves_h(atree.lt, acc))
        return leaves_h(self, [])

    def has_loop(self):
        def has_loop_h(atree, acc, armed):
            if acc == atree and armed: return True
            if TREE_LEAF == atree.type(): return False
            return has_loop_h(atree.lt, acc, True) or has_loop_h(atree.rt, acc, True)

        return has_loop_h(self, self, False)


    def contains(self, ptr):
        if ptr == self: return true
        if TREE_LEAF == self.type(): return False
        return self.lt.contains(ptr) or self.rt.contains(ptr)


    def to_html(self, leaf_func):
        def to_html_h(atree, leaf_func, s):
            sp = s * " "
            li_event = "<li onClick='toggleSize(event, this);'>"
            if TREE_LEAF == atree.type():
                return sp + "<li>" + leaf_func(atree.ptr) + "</li>\n"
            else:
                ltside = sp + li_event + "<ul>\n" + to_html_h(atree.lt, leaf_func, s + 1) + sp + "</ul></li>\n"
                rtside = sp + li_event + "<ul>\n" + to_html_h(atree.rt, leaf_func, s + 1) + sp + "</ul></li>\n"
                return ltside + rtside

        return "<ul>\n" + to_html_h(self, leaf_func, 1) + "</ul>\n"


    #
    # links to "far" fonts: how?
    # maybe mirror on the tree?
    #
    # as we descend the tree, keep a pointer to the "other branch" when we call one side?
    #
    """
    def namedSubtrees(self):
        def nst_h(atree, other_side, next_hop, acc):
            if TREE_LEAF == atree.type():
                #next_hop = the number of nodes that will be added if we jump to the parent
                return acc + [(atree.ptr, (other_side, next_hop))]
            else:
                new_next_hop = next_hop - atree.num_leaves()
                leftside = nst_h(atree.lt, atree.rt, new_next_hop, acc)
                rightside = nst_h(atree.rt, atree.lt, new_next_hop, leftside)
                return rightside

        nst_h(
       """



class branch(tree):

    def __init__(self):
        pass

    def set_branches(self, lt, rt):
        self.lt = lt
        self.rt = rt

    def type(self):
        return TREE_BRANCH


class leaf(tree):

    def __init__(self):
        self.ptr = None

    def type(self):
        return TREE_LEAF

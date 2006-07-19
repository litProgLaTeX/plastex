#!/usr/bin/env python

"""
C.11.5 Index and Glossary (p211)

"""

import string, os
from plasTeX.Tokenizer import Token
from plasTeX import Command, Environment
from plasTeX.Logging import getLogger
from Sectioning import SectionUtils

try:
    from pyuca import Collator
    collator = Collator(os.path.join(os.path.dirname(__file__), 'allkeys.txt')).sort_key
except ImportError:
    collator = lambda x: x.lower()

class IndexUtils(object):
    """ Helper functions for generating indexes """

    linkType = 'index'
    level = Command.CHAPTER_LEVEL

    class Index(Command):
        """
        Utility class used to surface the index entries to the renderer
    
        """
    
        def __init__(self, *args, **kwargs):
            Command.__init__(self, *args, **kwargs)
            self.pages = []
            self.key = []
            self.sortkey = ''

        @property
        def totallen(self):
            """ Return the total number of entries generated by this entry """
            total = 1
            for item in self:
                total += item.totallen
            return total
    
        def __repr__(self):
            return '%s%s --> %s' % (''.join([x.source for x in self.key]), 
                                    ', '.join([str(x) for x in self.pages]), 
                                    Command.__repr__(self))

    class IndexGroup(list):
        title = None

    def invoke(self, tex):
        if isinstance(self, Environment):
            Environment.invoke(self, tex)
        else:
            Command.invoke(self, tex)
        self.attributes['title'] = self.ownerDocument.createElement('indexname').expand(tex)

    @property
    def groups(self):
        """
        Group index entries into batches according to the first letter

        """
        batches = []
        current = ''
        for item in self:
            try: 
                label = title = item.sortkey[0].upper()
                if title in string.letters:
                    pass
                elif title == '_':
                     title = '_ (Underscore)'
                else:
                     label = title = 'Symbols'
            except IndexError: 
                label = title = 'Symbols'
            if current != title:
                newgroup = self.IndexGroup()
                newgroup.title = title
                newgroup.id = label
                batches.append(newgroup)
                current = title
            batches[-1].append(item)

        for item in batches:
            item[:] = self.splitColumns(item,
                self.ownerDocument.config['document']['index-columns'])

        return batches

    def splitColumns(self, items, cols):
        """
        Divide the index entries into the specified number of columns

        Required Arguments:
        items -- list of column entries
        cols -- number of columns to create

        Returns:
        list of length `cols' containing groups of column entries

        """
        entries = [(0,0)]
        # Find the total number of entries
        grandtotal = 0
        for item in items:
            entries.append((item.totallen, item))
            grandtotal += entries[-1][0]
        entries.pop(0)
        entries.reverse()

        # Get total number of entries per column
        coltotal = int(grandtotal / cols)

        # Group entries into columns
        current = 0
        output = [[]]
        for num, item in entries:
            current += num
            if len(output) >= cols:
                output[-1].append(item)
            elif current > coltotal:
                output.append([item]) 
                current = num
            elif current == coltotal:
                output[-1].append(item)
                output.append([])
                current = 0
            else:
                output[-1].append(item)

        output.reverse()
        for item in output:
            item.reverse()

        # Get rid of empty columns
        output = [x for x in output if x]  

        # Pad to the correct number of columns
        for i in range(cols-len(output)):
            output.append([])

        return output

    def digest(self, tokens):
        """ Sort and group index entries """
        if isinstance(self, Environment):
            Environment.digest(self, tokens)
            if self.macroMode == self.MODE_END:
                return
            # Throw it all away, we don't need it.  We'll be generating
            # our own index entries below.
            while self.childNodes:
                self.pop()
        else:
            Command.digest(self, tokens)
        doc = self.ownerDocument
        current = self
        entries = sorted(self.ownerDocument.userdata.get('index', []))
        prev = IndexEntry([], None)
        for item in entries:
            # See how many levels we need to add/subtract between this one 
            # and the previous
            common = 0
            for prevkey, itemkey in zip(zip(prev.sortkey, prev.key), 
                                        zip(item.sortkey, item.key)):
                if prevkey == itemkey:
                    common += 1
                    continue
                break

#           print
#           print item
#           print (prev.key, prev.sortkey), (item.key, item.sortkey), common

            # Pop out to the common level
            i = common
            while i < len(prev.key):
#               print 'POP'
                current = current.parentNode
                i += 1

            # Add the appropriate number of levels
            i = common
            while i < len(item.key):
#               print 'ADD', item.sortkey[i]
                newidx = self.Index()
                newidx.key = item.key[i]
                newidx.sortkey = item.sortkey[i]
                newidx.parentNode = current
                current.append(newidx)
                current = newidx
                i += 1

            # Add the current page and format it
            current.pages.append(item.node)
            if item.format is not None:
                node = doc.createElement(item.format)
                text = doc.createTextNode(str(len(current.pages)))
                node.append(text)
                item.node.append(node)
            else:
                text = doc.createTextNode(str(len(current.pages)))
                item.node.append(text)
            prev = item

class theindex(IndexUtils, Environment, SectionUtils):
    pass

class printindex(IndexUtils, Command, SectionUtils):
    pass

class makeindex(Command):
    pass

class makeglossary(Command):
    pass

class glossary(Command):
    args = 'entry:nox'

class index(Command):
    args = 'entry:nox'

    def invoke(self, tex):
        result = Command.invoke(self, tex)
        sortkey, key, format = [], [], []
        entry = iter(self.attributes['entry'])
        current = []
        alphanumeric = [Token.CC_OTHER, Token.CC_LETTER, Token.CC_SPACE]

        # Parse the index tokens
        for tok in entry:
            if tok.catcode in alphanumeric:
                # Escape character
                if tok == '"':
                    for tok in entry:
                        current.append(tok)
                        break
                # Entry separator
                elif tok == '!':
                    key.append(current)
                    if len(sortkey) < len(key):
                        sortkey.append(current)
                    current = []
                # Sort key separator
                elif tok == '@':
                    sortkey.append(current)
                    current = []
                # Format separator
                elif tok == '|':
                    key.append(current)
                    if len(sortkey) < len(key):
                        sortkey.append(current)
                    current = format
                else:
                    current.append(tok)
                continue
            # Everything else
            current.append(tok)

        # Make sure to get the stuff at the end
        if not format:
            key.append(current)
            if len(sortkey) < len(key):
                sortkey.append(current)

        # Convert the sort keys to strings
        for i, item in enumerate(sortkey):
            sortkey[i] = tex.expandTokens(item).textContent

        # Expand the key tokens
        for i, item in enumerate(key):
            key[i] = tex.expandTokens(item) 

        # Get the format element
        if format:
            format = u''.join(format)
        else:
            format = None

        # Store the index information in the document
        userdata = self.ownerDocument.userdata
        if 'index' not in userdata:
            userdata['index'] = []
        userdata['index'].append(IndexEntry(key, self, sortkey, format))

        return result



class IndexEntry(object):
    """
    Utility class used to assist in the sorting of index entries

    """

    def __init__(self, key, node, sortkey=None, format=None):
        self.key = key
        if not sortkey:
            self.sortkey = key
        else:
            self.sortkey = sortkey
        self.format = format
        self.node = node

    def __cmp__(self, other):
        result = cmp(zip([collator(x) for x in self.sortkey], 
                         [collator(x.textContent) for x in self.key], 
                         self.key), 
                     zip([collator(x) for x in other.sortkey], 
                         [collator(x.textContent) for x in other.key], 
                         other.key))
        if result == 0 and len(self.key) != len(other.key):
            return cmp(len(self.key), len(other.key))
        return result

    def __repr__(self):
        return ' '.join(['@'.join(self.sortkey), 
                         '!'.join([x.source for x in self.key]), 
                         str(self.format)])

    def __str__(self):
        return repr(self)

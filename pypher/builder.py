import sys
import uuid

from collections import namedtuple

from six import with_metaclass

from .exception import (PypherException, PypherAliasException,
    PypherArgumentException)


_LINKS = {}
_MODULE = sys.modules[__name__]
_PREDEFINED_STATEMENTS = [('Match',), ('Create',), ('Merge',), ('Delete',),
    ('Remove',), ('Drop',), ('Where',), ('Distinct',), ('OrderBy', 'ORDER BY'),
    ('Set',), ('Skip',), ('Limit',), ('Return',), ('Unwind',), ('ASSERT'),
    ('Detach'), ('DetachDelete', 'DETACH DELETE'), ('Foreach'), ('Load'),
    ('CSV'), ('FROM'), ('Headers'), ('LoadCsvFrom', 'LOAD CSV FROM'),
    ('LoadCSVWithHeadersFrom', 'LOAD CSV WITH HEADERS FROM'), ('WITH'),
    ('UsingPeriodIcCommit', 'USING PERIODIC COMMIT'), ('Periodic'), ('Commit'),
    ('FieldTerminator', 'FIELDTERMINATOR'), ('Optional', 'OPTIONAL'),
    ('OptionalMatch', 'OPTIONAL MATCH'),
    ('OnCreateSet', 'ON CREATE SET'), ('OnMatchSet', 'ON MATCH SET'),
    ('CreateIndexOn', 'CREATE INDEX ON'), ('UsingIndex', 'USING INDEX'),
    ('DropIndexOn', 'DROP INDEX ON'),
    ('CreateConstraintOn', 'CREATE CONSTRAINT ON'),
    ('DropConstraintOn', 'DROP CONSTRAINT ON')]
_PREDEFINED_FUNCTIONS = [('size',), ('reverse',), ('head',), ('tail',),
    ('last',), ('extract',), ('filter',), ('reduce',), ('Type', 'type',),
    ('startNode',), ('endNode',), ('count',), ('ID', 'id',), ('collect',),
    ('sum',), ('percentileDisc',), ('stDev',), ('coalesce',), ('timestamp',),
    ('toInteger',), ('toFloat',), ('toBoolean',), ('keys',), ('properties',),
    ('length',), ('nodes',), ('relationships',), ('point',), ('distance',),
    ('abs',), ('rand',), ('ROUND', 'round',), ('CEIL', 'ceil',),
    ('Floor', 'floor',), ('sqrt',), ('sign',), ('sin',), ('cos',), ('tan',),
    ('cot',), ('asin',), ('acos',), ('atan',), ('atanZ',), ('haversin',),
    ('degrees',), ('radians',), ('pi',), ('log10',), ('log',), ('exp',),
    ('e',), ('toString',), ('replace',), ('substring',), ('left',),
    ('right',), ('trim',), ('ltrim',), ('toUpper',), ('toLower',),
    ('SPLIT', 'split',)]
RELATIONSHIP_DIRECTIONS = {
    '-': 'undirected',
    '>': 'out',
    '<': 'in',
    '<>': 'both',
}


def create_function(name, attrs=None):
    attrs = attrs or {}

    setattr(_MODULE, name, type(name, (Func,), attrs))


def create_statement(name, attrs=None):
    attrs = attrs or {}

    setattr(_MODULE, name, type(name, (Statement,), attrs))


Param = namedtuple('Param', 'name value')


class _Link(type):

    def __new__(cls, name, bases, attrs):
        cls = super(_Link, cls).__new__(cls, name, bases, attrs)
        aliases = attrs.get('_ALIASES', None)
        _LINKS[name.lower()] = name

        if aliases:
            for alias in aliases:
                if alias in _LINKS:
                    error = ('The alias: "{}" defined in "{}" is already'
                        ' used by "{}"'.format(alias, name, _LINKS[alias]))
                    raise PypherAliasException(error)
                _LINKS[alias] = name

        return cls


class Pypher(with_metaclass(_Link)):
    PARAM_PREFIX = 'NEO'

    def __init__(self, parent=None, *args, **kwargs):
        self._parent = parent
        self.link = None
        self.next = None
        self._set_attr = None
        self._bound_count = 0
        self._bound_params = {}
        self._bound_param_key = str(uuid.uuid4())[-5:]

    def reset(self):
        self.link = None
        self.next = None
        self._set_attr = None
        self._bound_count = 0
        self._bound_params = {}

    def _get_parent(self):
        return self._parent

    def _set_parent(self, parent):
        parent.bind_params(self.bound_params)

        self._parent = parent

        return self

    parent = property(_get_parent, _set_parent)

    @property
    def bound_params(self):
        return self._bound_params

    def safely_stringify_for_pudb(self):
        return None

    def bind_params(self, params=None):
        if not params:
            return self

        if isinstance(params, dict):
            for name, value in params.items():
                self.bind_param(value, name)
        else:
            for value in params:
                self.bind_param(value)

        return self.bound_params

    def bind_param(self, value, name=None):
        self._bound_count += 1

        try:
            if isinstance(value, Param):
                name = value.name
                value = value.value
            elif value in self._bound_params.values():
                for k, v in self._bound_params.items():
                    if v == value:
                        name = k
                        break
            elif value in self._bound_params.keys():
                for k, v in self._bound_params.items():
                    if v == k:
                        name = k
                        value = v
                        break
        except:
            pass

        if not name:
            name = self._param_name()

        self._bound_params[name] = value

        if self.parent:
            self.parent.bind_param(value=value, name=name)

        return Param(name=name, value=value)

    def _param_name(self, name=None):
        if not name:
            return '{}_{}_{}'.format(self.PARAM_PREFIX, self._bound_param_key,
                self._bound_count)

        return '{}_{}_{}'.format(name, self._bound_param_key,
                self._bound_count)

    def __getattr__(self, attr):
        attr_low = attr.lower()

        if attr_low in _LINKS:
            link = (getattr(_MODULE, _LINKS[attr_low]))()
            link.parent = self
        else:
            link = Statement(name=attr)
            link.parent = self

            self._set_attr = attr

        return self.add_link(link)

    def __call__(self, *args, **kwargs):
        func = self._bottom.__class__(*args, **kwargs)
        func.parent = self

        return self.remove_link(self._bottom).add_link(func)

    def __getitem__(self, *args):
        comp = Comprehension(parent=self, *args)

        return self.add_link(comp)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        token = self.next
        prev = token
        tokens = []

        while token:
            pre = ''
            suff = ''

            if token._CLEAR_PRECEEDING_WS:
                try:
                    tokens[-1] = tokens[-1].rstrip()
                except Exception as e:
                    pass

            if token._ADD_PRECEEDING_WS:
                try:
                    skip = tokens[-1][-1] == ' '
                except Exception as e:
                    skip = False

                if not skip:
                    pre = ' '

            if token._ADD_SUCEEDING_WS:
                suff = ' '

            part = '{}{}{}'.format(pre, str(token), suff)
            tokens.append(part)

            prev = token
            token = token.next

        return ''.join(tokens).strip()

    def __add__(self, other):
        return self.operator(operator='+', value=other)

    def __iadd__(self, other):
        return self.operator(operator='+=', value=other)

    def __radd__(self, other):
        return self.operator(operator='+=', value=other)

    def __sub__(self, other):
        return self.operator(operator='-', value=other)

    def __isub__(self, other):
        return self.operator(operator='-', value=other)

    def __rsub__(self, other):
        return self.operator(operator='-', value=other)

    def __mul__(self, other):
        return self.operator(operator='*', value=other)

    def __imul__(self, other):
        return self.operator(operator='*', value=other)

    def __rmul__(self, other):
        return self.operator(operator='*', value=other)

    def __div__(self, other):
        return self.operator(operator='/', value=other)

    def __idiv__(self, other):
        return self.operator(operator='/', value=other)

    def __rdiv__(self, other):
        return self.operator(operator='/', value=other)

    def __mod__(self, other):
        return self.operator(operator='%', value=other)

    def __and__(self, other):
        return self.operator(operator='&', value=other)

    def __or__(self, other):
        return self.operator(operator='|', value=other)

    def __ror__(self, other):
        return self.operator(operator='|', value=other)

    def __xor__(self, other):
        return self.operator(operator='^', value=other)

    def __rxor__(self, other):
        return self.operator(operator='^', value=other)

    def __gt__(self, other):
        return self.operator(operator='>', value=other)

    def __ge__(self, other):
        return self.operator(operator='>=', value=other)

    def __lt__(self, other):
        return self.operator(operator='<', value=other)

    def __le__(self, other):
        return self.operator(operator='<=', value=other)

    def __ne__(self, other):
        return self.operator(operator='!=', value=other)

    def __eq__(self, other):
        return self.operator(operator='=', value=other)

    def operator(self, operator, value):
        op = Operator(operator=operator, value=value, parent=self)
        op.parent = self

        return self.add_link(op)

    def property(self, name):
        prop = Property(name=name, parent=self)

        return self.add_link(prop)

    def alias(self, alias):
        return self.operator(operator='AS', value=alias)

    def rel_out(self, *args, **kwargs):
        kwargs['direction'] = 'out'
        rel = Relationship(*args, **kwargs)
        rel.parent = self

        return self.add_link(rel)

    def rel_in(self, *args, **kwargs):
        kwargs['direction'] = 'in'
        rel = Relationship(*args, **kwargs)
        rel.parent = self

        return self.add_link(rel)

    def func(self, name, *args, **kwargs):
        kwargs['name'] = name
        func = Func(*args, **kwargs)
        func.parent = self

        return self.add_link(func)

    def add_link(self, link):
        token = self.next

        if not token:
            self.next = link
            self._bottom = link

            return self

        while token:
            try:
                token.next.next
                token = token.next
                continue
            except Exception as e:
                token.next = link
                self._bottom = link
                break

        return self

    def remove_link(self, remove):
        link = self.next

        if not link:
            return self
        elif id(link) == id(remove):
            self.next = None
            self._bottom = None

            return self

        while link:
            if id(link.next) == id(remove):
                link.next = link.next.next
                break

            link = link.next

        return self


class _BaseLink(Pypher):
    _CLEAR_PRECEEDING_WS = False
    _ADD_PRECEEDING_WS = False
    _ADD_SUCEEDING_WS = True

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        super(_BaseLink, self).__init__()

    def __unicode__(self):
        return self.__class__.__name__.upper()


class Alias(_BaseLink):

    def __getattr__(self, attr):
        pass

    def alias(self, alias):
        return self


class Statement(_BaseLink):
    _ADD_PRECEEDING_WS = True
    _ADD_SUCEEDING_WS = True
    _CAPITALIZE = True

    def __init__(self, *args, **kwargs):
        try:
            self._name = kwargs.pop('name')
        except:
            self._name = None

        super(Statement, self).__init__(*args, **kwargs)

    @property
    def name(self):
        if self._name:
            return self._name

        if self._CAPITALIZE:
            return self.__class__.__name__.upper()

        return self.__class__.__name__

    def __unicode__(self):
        if self.args:
            parts = []

            for arg in self.args:
                if isinstance(arg, Pypher):
                    arg.parent = self.parent

                parts.append(str(arg))

            parts = ', '.join(parts)

            return '{} {}'.format(self.name, parts)

        return self.name


class Property(Statement):
    _ADD_PRECEEDING_WS = False
    _CLEAR_PRECEEDING_WS = True
    _ALIASES = ['prop',]

    def __unicode__(self):
        return '.{}'.format(self.name)


class Label(Statement):
    _ADD_PRECEEDING_WS = False
    _CLEAR_PRECEEDING_WS = True

    def __unicode__(self):
        labels = []

        for arg in self.args:
            param = self.bind_param(arg)
            labels.append(param.name)

        labels = ':'.join(labels)

        return ':{labels}'.format(labels=labels)


class IN(Statement):

    def __unicode__(self):
        args = []

        for arg in self.args:
            param = self.bind_param(arg)
            args.append(param.name)

        args = ', '.join(args)

        return 'IN [{args}]'.format(args=args)


class Func(Statement):
    _CAPITALIZE = False

    def __unicode__(self):
        args = []

        for arg in self.args:
            param = self.bind_param(arg)
            args.append(param.name)

        args = ', '.join(args)

        return '{function}({args})'.format(function=self.name,
            args=args)


class Comprehension(_BaseLink):

    def __unicode__(self):
        args = ''.join(map(str, self.args))

        return '[{args}]'.format(args=args)


class Operator(_BaseLink):
    _ADD_PRECEEDING_WS = True
    _ADD_SUCEEDING_WS = False

    def __init__(self, operator=None, value=None, parent=None):
        self.operator = operator or self.operator
        self.value = value

        super(Operator, self).__init__(parent=parent)

    def __unicode__(self):
        if self.value:
            param = self.bind_param(self.value)

            return '{} {}'.format(self.operator, param.name)

        return self.operator


class AND(Operator):
    operator = 'AND'


class OR(Operator):
    operator = 'OR'


class Entity(_BaseLink):
    _ADD_PRECEEDING_WS = False
    _ADD_SUCEEDING_WS = False
    _CLEAR_PRECEEDING_WS = False

    def __init__(self, variable=None, labels=None, parent=None, **properties):
        if labels and not isinstance(labels, (list, set, tuple)):
            labels = [labels]

        self.variable = variable or ''
        self._labels = labels
        self._properties = properties

        super(Entity, self).__init__(parent=parent)

    @property
    def labels(self):
        variable = self.variable

        if self._labels:
            labels = ':'.join(self._labels)

            return '{variable}:{labels}'.format(variable=variable,
                labels=labels)

        return variable

    @property
    def properties(self):
        properties = []

        for k, v in self._properties.items():
            name = self._param_name(k)
            param = self.bind_param(value=v, name=name)

            properties.append('{key}: {val}'.format(key=k, val=param.name))

        if properties:
            return '{{{props}}}'.format(props=', '.join(properties))

        return ''


class Node(Entity):

    def __unicode__(self):
        properties = self.properties

        if properties:
            properties = ' ' + properties

        return '({labels}{properties})'.format(labels=self.labels,
            properties=properties)


class Relationship(Entity):
    _ALIASES = ['rel',]
    _DEFAULT_DIRECTION = 'undirected'
    _DIRECTIONS = {
        'undirected': '-{}-',
        'in': '<-{}-',
        'out': '-{}->',
    }

    def __init__(self, variable=None, labels=None, parent=None,
                 direction=None, **properties):
        super(Relationship, self).__init__(variable=variable, labels=labels,
            parent=parent, **properties)
        self._direction = None
        self.direction = direction

    def _get_direction(self):
        direction = self._direction.lower()

        return self._DIRECTIONS[direction]

    def _set_direction(self, direction=None):
        if not direction:
            direction = self._DEFAULT_DIRECTION
        elif direction in RELATIONSHIP_DIRECTIONS:
            direction = RELATIONSHIP_DIRECTIONS[direction]
        elif direction in RELATIONSHIP_DIRECTIONS.values():
            direction = direction
        else:
            error = 'The direction: {} is not valid'.format(direction)

            raise PypherArgumentException(error)

        self._direction = direction

    direction = property(_get_direction, _set_direction)

    def __unicode__(self):
        properties = self.properties

        if properties:
            properties = ' ' + properties

        fill = '[{labels}{properties}]'.format(labels=self.labels,
            properties=properties)

        return self.direction.format(fill)


class Anon(object):

    def __init__(self):
        pass

    def __getattr__(self, attr):
        py = Pypher()

        getattr(py, attr)

        return py


# Create an anonymous Pypher factory
__ = Anon()


# dynamically create all pre defined Statments and functions
for state in _PREDEFINED_STATEMENTS:
    name = state[0]

    try:
        attrs = {'name': state[1]}
    except Exception as e:
        attrs = {}

    create_statement(name=name, attrs=attrs)


for fun in _PREDEFINED_FUNCTIONS:
    name = fun[0]

    try:
        attrs = {'name': fun[1]}
    except Exception as e:
        attrs = {'name': name}

    create_function(name=name, attrs=attrs)

from __future__ import annotations
from generator.core.tsl_config import config
from generator.core.ctrl.tsl_lib import TSLLib

from typing import Generator, Dict, Iterator, Set, List, Tuple, NewType, Union
import re
import networkx as nx
from dataclasses import dataclass
import pandas as pd
from enum import Enum
from natsort import natsort_key


class TSLInspectionLevelOfDetail(Enum):
  '''
  Inspection level of detail.
  The default adds primitive-classes, primitives and the dependencies between them and between primitives (through their implementations).
  This is necessary to ensure a correct generated library.
  If the level of detail is increased, the dependency graph is extended with the following information:
  (i) TEST: Primitive-Tests are added to the graph and connected with their associated primitive.
  (i) PRIMITIVE_INSTANTIATION: Adds all possible instantiations of a primitive (e.g., add<float, sse>) and its dependencies.
  (ii) TEST_IMPLEMENTATION: Adds all test implementations and their dependencies (to primitives).
  (iii) TEST_INSTANTIATION: Adds all possible instantiations of a test (e.g., add<float, sse>::test1) and its concrete dependencies.
  '''
  DEFAULT = 1
  TEST = 2
  TEST_IMPLEMENTATION = 3
  PRIMITIVE_INSTANTIATION = 4
  TEST_INSTANTIATION = 5

class TSLDependencyGraphLevelOfDetail(Enum):
  CLASS = 1
  PRIMITIVE = 2
  PRIMITIVE_IMPLEMENTATION = 3
  TEST = 4
  TEST_IMPLEMENTATION = 5

class TSLDependencyGraph:
  '''
  Dependency graph for the TSL.
  The dependency graph is a directed graph, where the nodes are of type:
  (i) PrimitiveClassNode: Represents a primitive-class
  (ii) PrimitiveNode: Represents a primitive
  (iii) PrimitiveImplementationNode: Represents a concrete primitive implementation (aka. primitive definition, e.g., add<float, sse>)
  (iv) PrimitiveTestNode: Represents a test case for a primitive
  (v) PrimitiveTestImplementationNode: Represents a concrete test implementation (e.g., add<float, sse>::test1)
  The nodes are connected with edges, which are labeled with the following information:
  (i) "part of": PrimitiveNode -> PrimitiveClassNode
  (ii) "overload of": PrimitiveNode -> PrimitiveNode (for function overloading)
  (iii) "concrete instantiation of": PrimitiveImplementationNode -> PrimitiveNode
  (iv) "requirement of": PrimitiveNode -> PrimitiveNode (for primitive dependencies, e.gl, mod depends on cast --> mod requires cast --> cast is requirement of mod)
  (v) "concrete requirement of": PrimitiveImplementationNode -> PrimitiveImplementationNode (if an edge "requirement of" exists between two PrimitiveNodes, all possible instantiations carry the same dependency)
  (vi) "test of": PrimitiveTestNode -> PrimitiveNode
  (vii) "concrete instantiation of": PrimitiveTestImplementationNode -> PrimitiveTestNode
  (viii) "requirement of": PrimitiveNode -> PrimitiveTestNode (for primitive dependencies, e.gl, mod depends on cast --> mod requires cast --> cast is requirement of mod)
  (ix) "concrete requirement of": PrimitiveImplementationNode -> PrimitiveTestImplementationNode (if an edge "requirement of" exists between PrimitiveTestNode and PrimitiveNode, all possible instantiations carry the same dependency)
  '''

  @dataclass(order=True, unsafe_hash=True, frozen=True)
  class PrimitiveClassNode:
    _class_name: str
    type: str = "class"
    size: int = 10
    def __str__(self):
      return f"{self._class_name}"
    def __repr__(self):
      return str(self)
    @classmethod
    def create(cls, name: str) -> TSLDependencyGraph.PrimitiveClassNode:
      return cls(name)
    @property
    def class_name(self) -> str:
      return self._class_name

  class PrimitiveNode:
    type: str = "primitive"
    size: int = 5
    def __init__(self, name: str):
      self._primitive_name: str = name
      self._valid: bool = True
    def __str__(self):
      return f"{self._primitive_name}"
    def __repr__(self):
      return str(self)
    @classmethod
    def create(cls, name: str) -> TSLDependencyGraph.PrimitiveNode:
      return cls(name)
    @property
    def primitive_name(self) -> str:
      return self._primitive_name
    @property
    def valid(self) -> bool:
      return self._valid
    @valid.setter
    def valid(self, value: bool) -> None:
      self._valid = value
    def __lt__(self, other: TSLDependencyGraph.PrimitiveNode) -> bool:
      # Sort by name using natural sorting
      if isinstance(other, TSLDependencyGraph.PrimitiveNode):
        return natsort_key(str(self)) < natsort_key(str(other))
      else:
        return NotImplemented
    def __le__(self, other: TSLDependencyGraph.PrimitiveNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveNode):
        return natsort_key(str(self)) <= natsort_key(str(other))
      else:
        return NotImplemented
    def __gt__(self, other: TSLDependencyGraph.PrimitiveNode) -> bool:
      return not self.__le__(other)
    def __ge__(self, other: TSLDependencyGraph.PrimitiveNode) -> bool:
      return not self.__lt__(other)
    def __eq__(self, other: TSLDependencyGraph.PrimitiveNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveNode):
        return str(self) == str(other)
      else:
        return NotImplemented
    def __ne__(self, other: TSLDependencyGraph.PrimitiveNode) -> bool:
      return not self.__eq__(other)
    def __hash__(self) -> int:
      return hash(self._primitive_name)
        

  class PrimitiveImplementationNode:
    type: str = "primitive_implementation"
    size: int = 3
    implementation_regex_str = re.compile(rf'(?P<primitive_name>[^<]+)\s*<\s*(?P<ctype>[^,]+)\s*,\s*(?P<extension>[^>]+)\s*>')
    def __init__(self, primitive_name: str, extension: str, ctype: str) -> None:
      self._primitive_name: str = primitive_name
      self._extension: str = extension
      self._ctype: str = ctype
      self._valid: bool = True    
    def __str__(self):
      return f"{self._primitive_name}<{self._ctype}, {self._extension}>"
    def __repr__(self):
      return str(self)
    @classmethod
    def create(cls, name: str, extension: str = None, ctype: str = None) -> TSLDependencyGraph.PrimitiveImplementationNode:
      if extension is not None:
        if ctype is not None:
          return cls(name, extension, ctype)
        else:
          raise ValueError("ctype must be specified if extension is specified")
      match = cls.implementation_regex_str.match(name)
      if match is None:
        raise ValueError(f"Invalid implementation name: {name}")
      else:
        return cls(match.group("primitive_name").strip(), match.group("extension").strip(), match.group("ctype").strip())    
    @property
    def primitive_name(self) -> str:
      return self._primitive_name
    @property
    def extension(self) -> str:
      return self._extension
    @property
    def ctype(self) -> str:
      return self._ctype
    @property
    def valid(self) -> bool:
      return self._valid
    @valid.setter
    def valid(self, value: bool) -> None:
      self._valid = value
    def __lt__(self, other: TSLDependencyGraph.PrimitiveImplementationNode) -> bool:
      # Sort by name using natural sorting
      if isinstance(other, TSLDependencyGraph.PrimitiveImplementationNode):
        return natsort_key(str(self)) < natsort_key(str(other))
      else:
        return NotImplemented
    def __le__(self, other: TSLDependencyGraph.PrimitiveImplementationNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveImplementationNode):
        return natsort_key(str(self)) <= natsort_key(str(other))
      else:
        return NotImplemented
    def __gt__(self, other: TSLDependencyGraph.PrimitiveImplementationNode) -> bool:
      return not self.__le__(other)
    def __ge__(self, other: TSLDependencyGraph.PrimitiveImplementationNode) -> bool:
      return not self.__lt__(other)
    def __eq__(self, other: TSLDependencyGraph.PrimitiveImplementationNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveImplementationNode):
        return str(self) == str(other)
      else:
        return NotImplemented
    def __ne__(self, other: TSLDependencyGraph.PrimitiveImplementationNode) -> bool:
      return not self.__eq__(other)
    def __hash__(self) -> int:
      return hash((self._primitive_name, self._extension, self._ctype))
    
  class PrimitiveTestNode:
    type: str = "test"
    size: int = 3
    def __init__(self, primitive_name: str, test_name: str) -> None:
      self._primitive_name: str = primitive_name
      self._test_name: str = test_name
      self._valid: bool = True
      self._safe: bool = True
    def __str__(self):
      return f"{self._primitive_name}::{self._test_name}"
    def __repr__(self):
      return str(self)
    @classmethod
    def create(cls, name: str, test_name: str = None) -> TSLDependencyGraph.PrimitiveTestNode:
      if test_name is not None:
        return cls(name, test_name)
      else:
        return cls(*name.split("::"))
    @property
    def primitive_name(self) -> str:
      return self._primitive_name
    @property
    def test_name(self) -> str:
      return self._test_name
    @property
    def valid(self) -> bool:
      return self._valid
    @valid.setter
    def valid(self, value: bool) -> None:
      self._valid = value
    @property
    def unsafe(self) -> bool:
      return not self._safe
    @property
    def safe(self) -> bool:
      return self._safe
    @safe.setter
    def safe(self, value: bool) -> None:
      self._safe = value
    def __lt__(self, other: TSLDependencyGraph.PrimitiveTestNode) -> bool:
      # Sort by name using natural sorting
      if isinstance(other, TSLDependencyGraph.PrimitiveTestNode):
        return natsort_key(str(self)) < natsort_key(str(other))
      else:
        return NotImplemented
    def __le__(self, other: TSLDependencyGraph.PrimitiveTestNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveTestNode):
        return natsort_key(str(self)) <= natsort_key(str(other))
      else:
        return NotImplemented
    def __gt__(self, other: TSLDependencyGraph.PrimitiveTestNode) -> bool:
      return not self.__le__(other)
    def __ge__(self, other: TSLDependencyGraph.PrimitiveTestNode) -> bool:
      return not self.__lt__(other)
    def __eq__(self, other: TSLDependencyGraph.PrimitiveTestNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveTestNode):
        return str(self) == str(other)
      else:
        return NotImplemented
    def __ne__(self, other: TSLDependencyGraph.PrimitiveTestNode) -> bool:
      return not self.__eq__(other)
    def __hash__(self) -> int:
      return hash((self._primitive_name, self._test_name))
    
  class PrimitiveTestImplementationNode:
    type: str = "test_implementation"
    size: int = 3
    implementation_regex_str = re.compile(rf'(?P<primitive_name>[^:]+)\s*::\s*(?P<test_name>[^<]+)\s*<\s*(?P<ctype>[^,]+)\s*,\s*(?P<extension>[^>]+)\s*>')
    def __init__(self, primitive_name: str, test_name: str, extension: str, ctype: str):
      self._primitive_name: str = primitive_name
      self._test_name: str = test_name
      self._extension: str = extension
      self._ctype: str = ctype
      self._valid: bool = True
      self._safe: bool = True
    def __str__(self):
      return f"{self._primitive_name}::{self._test_name}<{self._ctype}, {self._extension}>"
    def __repr__(self):
      return str(self)
    @classmethod
    def create(cls, name: str, test_name: str = None, extension: str = None, ctype: str = None) -> TSLDependencyGraph.PrimitiveTestImplementationNode:
      if test_name is not None:
        if extension is None or ctype is None:
          raise ValueError("If test_name is specified, extension and ctype must be specified as well")
        else:
          return cls(name, test_name, extension, ctype)
      else:
        match = cls.implementation_regex_str.match(name)
        if match is None:
          raise ValueError(f"Invalid implementation name: {name}")
        else:
          return cls(match.group("primitive_name").strip(), match.group("test_name").strip(), match.group("extension").strip(), match.group("ctype").strip())
    @property
    def primitive_name(self) -> str:
      return self._primitive_name
    @property
    def test_name(self) -> str:
      return self._test_name
    @property
    def extension(self) -> str:
      return self._extension
    @property
    def ctype(self) -> str:
      return self._ctype
    @property
    def valid(self) -> bool:
      return self._valid
    @valid.setter
    def valid(self, value: bool) -> None:
      self._valid = value
    @property
    def unsafe(self) -> bool:
      return not self._safe
    @property
    def safe(self) -> bool:
      return self._safe
    @safe.setter
    def safe(self, value: bool) -> None:
      self._safe = value
    def __lt__(self, other: TSLDependencyGraph.PrimitiveTestImplementationNode) -> bool:
      # Sort by name using natural sorting
      if isinstance(other, TSLDependencyGraph.PrimitiveTestImplementationNode):
        return natsort_key(str(self)) < natsort_key(str(other))
      else:
        return NotImplemented
    def __le__(self, other: TSLDependencyGraph.PrimitiveTestImplementationNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveTestImplementationNode):
        return natsort_key(str(self)) <= natsort_key(str(other))
      else:
        return NotImplemented
    def __gt__(self, other: TSLDependencyGraph.PrimitiveTestImplementationNode) -> bool:
      return not self.__le__(other)
    def __ge__(self, other: TSLDependencyGraph.PrimitiveTestImplementationNode) -> bool:
      return not self.__lt__(other)
    def __eq__(self, other: TSLDependencyGraph.PrimitiveTestImplementationNode) -> bool:
      if isinstance(other, TSLDependencyGraph.PrimitiveTestImplementationNode):
        return str(self) == str(other)
      else:
        return NotImplemented
    def __ne__(self, other: TSLDependencyGraph.PrimitiveTestImplementationNode) -> bool:
      return not self.__eq__(other)
    def __hash__(self) -> int:
      return hash((self._primitive_name, self._test_name, self._extension, self._ctype))
  
  NodeType = Union[PrimitiveClassNode, PrimitiveNode, PrimitiveImplementationNode, PrimitiveTestNode, PrimitiveTestImplementationNode]
    
  class ProblemsContainer:
    '''
    Container for errors and warnings.
    Errors result from the following situations:
    - A primitive depends on an unknown primitive
    - A primitive has no implementations (if level_of_detail is greater or equal PRIMITIVE_INSTANTIATION)
    - A primitive test has no implementation (if level_of_detail is greater or equal TEST_IMPLEMENTATION)
    - A primitive test implementation depends on an unknown primitive (if level_of_detail is greater or equal TEST_IMPLEMENTATION)
    Warnings result from the following situations:
    - A primitive has no tests (if level_of_detail is greater or equal TEST and the test is not marked as "implicit reliable") = "untested"
    - A primitive test implementatoin depends on an untested primitive (if level_of_detail is greater or equal TEST_IMPLEMENTATION)
    '''
    def __init__(self):
      self.__errors: Dict[TSLDependencyGraph.NodeType, List[str]] = {}
      self.__warnings: Dict[TSLDependencyGraph.NodeType, List[str]] = {}
    
    def has_errors(self) -> bool:
      if len(self.__errors) > 0:
        return True
      return False
    
    def has_warnings(self) -> bool:
      if len(self.__warnings) > 0:
        return True
      return False
    
    def add_error(self, offending_node: TSLDependencyGraph.NodeType, error_description: str) -> None:
      if offending_node not in self.__errors:
        self.__errors[offending_node] = []
      self.__errors[offending_node].append(error_description)

    def add_warning(self, offending_node: TSLDependencyGraph.NodeType, warning_description: str) -> None:
      if offending_node not in self.__warnings:
        self.__warnings[offending_node] = []
      self.__warnings[offending_node].append(warning_description)

    def get_errors(self) -> Dict[TSLDependencyGraph.NodeType, List[str]]:
      return self.__errors
    
    def get_warnings(self) -> Dict[TSLDependencyGraph.NodeType, List[str]]:
      return self.__warnings
  
  @property
  def graph(self) -> nx.DiGraph:
    return self.__dependency_graph
  
  def nodes_by_type(self, node_types_of_interest: list) -> Generator[NodeType, None, None]:
    '''
    Returns all nodes of the given node_types_of_interest.
    '''
    yield from filter(lambda node: any(isinstance(node, node_type) for node_type in node_types_of_interest), self.__dependency_graph.nodes)

  def edges_by_label(self, edge_label: str, type: str, nodes_of_interest: list = []) -> Generator[Tuple[NodeType, NodeType], None, None]:
    '''
    Returns all edges of the given edge_label.
    If nodes_of_interest is not empty, only edges directly connected to the given nodes are returned.
    '''
    if type == "in":
      if len(nodes_of_interest) == 0:
        edges_of_interest = self.__dependency_graph.in_edges()
      else:
        edges_of_interest = self.__dependency_graph.in_edges(nodes_of_interest)
    elif type == "out":
      if len(nodes_of_interest) == 0:
        edges_of_interest = self.__dependency_graph.out_edges()
      else:
        edges_of_interest = self.__dependency_graph.out_edges(nodes_of_interest)
    elif type == "all":
      if len(nodes_of_interest) == 0:
        edges_of_interest = self.__dependency_graph.edges()
      else:
        edges_of_interest = self.__dependency_graph.edges(nodes_of_interest)
    else:
      raise ValueError(f"Unknown edge type {type} (expected 'in', 'out' or 'all')")
    for edge in filter(lambda edge: "label" in self.__dependency_graph.get_edge_data(*edge) and self.__dependency_graph.get_edge_data(*edge)["label"] == edge_label, edges_of_interest):
      yield edge
  
  def traverse_nodes(self, start_nodes: List[NodeType], reversed: bool, self_contained: bool = False) -> Generator[NodeType, None, None]:
    '''
    Traverses (breadth first) the dependency graph starting from the given start_nodes.
    If self_contained is True, the start_nodes are yielded first.
    If reversed is True, the graph is traversed in reverse order.
    '''
    for current_node in start_nodes:
      if self_contained:
        yield current_node
      for edge in nx.bfs_edges(self.__dependency_graph, current_node, reverse=reversed):
        yield edge[1]

  def traverse_by_type(self, start_nodes: List[NodeType], relevant_node_type: list, reversed:bool, self_contained: bool = False) -> Generator[NodeType, None, None]:
    '''
    Traverses (breadth first) the dependency graph starting from the given start_nodes.
    If self_contained is True, the start_nodes are yielded first.
    If reversed is True, the graph is traversed in reverse order.
    Only nodes of the given relevant_node_type are yielded.    
    '''
    for node in self.travers(start_nodes, reversed, self_contained):
      if any(isinstance(node, node_type) for node_type in relevant_node_type):
        yield node

  def slice(self, filter_node_type: NodeType, relevant_node_names: list = [], relevant_node_type: list = []) -> nx.DiGraph:
    '''
    Creates a subgraph of the dependency graph, where all nodes of the given filter_node_type are included (with their respective edges).
    All requirements were added too.
    If relevant_node_names is not empty, only nodes with the given names are included.
    If relevant_node_type is not empty, only nodes of the given types are included.
    '''
    if len(relevant_node_type) == 0:
      start_nodes: List[TSLDependencyGraph.NodeType] = [node for node in self.nodes_by_type([filter_node_type])]
    else:
      start_nodes: List[TSLDependencyGraph.NodeType] = [node for node in self.nodes_by_type([filter_node_type]) if node.name in relevant_node_names]
    if len(relevant_node_names) == 0:
      return self.__dependency_graph.subgraph(self.traverse_nodes(start_nodes, reversed=True, self_contained=True))
    else:
      return self.__dependency_graph.subgraph(self.traverse_by_type(start_nodes, relevant_node_type, reversed=True, self_contained=True))

  def sorted_classes(self) -> Generator[PrimitiveClassNode, None, None]:
    '''
    Returns a list of all primitive-classes sorted by their dependencies and lexicographical by their respective name.
    '''
    yield from nx.lexicographical_topological_sort(self.__dependency_graph.subgraph(self.nodes_by_type([TSLDependencyGraph.PrimitiveClassNode])))

  def __add_primitive_classes(self, tsl_lib: TSLLib) -> None:
    '''
    Iterates over all primitive-classes within the tsl_lib.
    Creates PrimitiveClassNode(s) for every primitive-class and add them to the dependency graph.
    '''
    for primitive_class in tsl_lib.primitive_class_set:
      self.__dependency_graph.add_node(TSLDependencyGraph.PrimitiveClassNode.create(primitive_class.name))

  def __add_primitives(self, tsl_lib: TSLLib) -> None:
    '''
    Iterates over all primitives within the tsl_lib.
    Creates PrimitiveNodes for every primitive and add them to the dependency graph.
    Adds Edges between every primitive and their associated primitive-class.
    If the primitive name is not equal to the functor name (function overloading), two nodes are added:
    (i) a primitive-node for the primitive with its associated class
    (ii) a primitive-node for the overload with the functor name
    Additionally, the overload is connected with the primitive node via a named edge (overload of).
    '''
    for class_name, primitive in tsl_lib.known_primitives:
      primitive_class_node = TSLDependencyGraph.PrimitiveClassNode.create(class_name)
      if primitive.declaration.name != primitive.declaration.functor_name:
        primitive_node = TSLDependencyGraph.PrimitiveNode.create(primitive.declaration.name)
        primitive_functor_node = TSLDependencyGraph.PrimitiveNode.create(primitive.declaration.functor_name)
        self.__dependency_graph.add_node(primitive_node)
        self.__dependency_graph.add_node(primitive_functor_node)
        self.__dependency_graph.add_edge(primitive_functor_node, primitive_node, label="overload of")
        self.__dependency_graph.add_edge(primitive_node, primitive_class_node, label="part of")
      else:
        primitive_node = TSLDependencyGraph.PrimitiveNode.create(primitive.declaration.name)
        self.__dependency_graph.add_node(primitive_node)
        self.__dependency_graph.add_edge(primitive_node, primitive_class_node, label="part of")

  def __add_primitive_implementation_dependencies(self, tsl_lib: TSLLib, primitive_pattern: re.Pattern, level_of_detail: TSLInspectionLevelOfDetail) -> None:
    '''
    Iterates over all definitions for every primitive.
    If level_of_detail is greater or equal PRIMITIVE_INSTANTIATION, for the target_extension 
    and all provided ctypes a PrimitiveImplementationNode is added to the dependency graph as well as a named
    edge ("concrete instantiation") betwwen the implementation-node and the primitive-node.
    For every definition, the implementation is checked, whether other tsl-primitives are used.
    If a requirement is found, an edge (with the label "requirement of") is added to the graph, 
    connecting the required primitive node with the dependent one.
    The (rare) case of a primitive depending on itself is ignored (no id-edges are added).
    If an required primitive does not exist in the graph, an error is added to self.__problems.
    If level_of_detail is greater or equal PRIMITIVE_INSTANTIATION, for the target_extension
    and all provided ctypes a PrimitiveImplementationNode for the __required__ primitive is added as well as 
    a named edge ("concrete requirement of") between the dependent implementation-node and the required one.
    '''
    for _, primitive in tsl_lib.known_primitives:
      primitive_name = primitive.declaration.functor_name
      primitive_node = TSLDependencyGraph.PrimitiveNode.create(primitive_name)
      for definition in primitive.definitions:
        if level_of_detail.value >= TSLInspectionLevelOfDetail.PRIMITIVE_INSTANTIATION:
          extension = definition.target_extension
          for ctype in definition.ctypes:
            primitive_instantiation_node = TSLDependencyGraph.PrimitiveImplementationNode.create(primitive_name, extension, ctype)
            self.__dependency_graph.add_edge(primitive_instantiation_node, primitive_node, label="concrete instantiation of")
        implementation_str = definition.data["implementation"]
        for match in primitive_pattern.finditer(implementation_str):
          required_primitive_name = match.group("primitive")
          if required_primitive_name != primitive_name:
            required_primitive_node = TSLDependencyGraph.PrimitiveNode.create(required_primitive_name)
            if required_primitive_node not in self.__dependency_graph:
              primitive_node.valid = False
              self.__problems.add_error(primitive_node, f"Unknown primitive {required_primitive_name} (required by {primitive_node}")
              continue
            self.__dependency_graph.add_edge(required_primitive_node, primitive_node, label="requirement of")
            if level_of_detail.value >= TSLInspectionLevelOfDetail.PRIMITIVE_INSTANTIATION:              
              # Check, if a specific tsl extension was specified
              if "simd_type" in match.groupdict():
                if "ctype" in match.group_dict() and "extension" in match.group_dict():
                  required_instantiation_node = TSLDependencyGraph.PrimitiveImplementationNode(
                    TSLDependencyGraph.PrimitiveImplementationNode.create_full_qualified_name(required_primitive_name, match.group("extension"), match.group("ctype"))
                  )
                  self.__dependency_graph.add_node(required_instantiation_node)
                  for ctype in definition.ctypes:
                    primitive_instantiation_node = TSLDependencyGraph.PrimitiveImplementationNode(
                      TSLDependencyGraph.PrimitiveImplementationNode.create_full_qualified_name(primitive_name, extension, ctype)
                    )
                    self.__dependency_graph.add_edge(
                      required_instantiation_node, 
                      primitive_instantiation_node, label="concrete requirement of")
                else:
                  raise ValueError("Found simd_type but no ctype AND extension")
              else:
                # Generic one -> add all possible nodes
                for ctype in definition.ctypes:
                  primitive_instantiation_node = TSLDependencyGraph.PrimitiveImplementationNode(
                    TSLDependencyGraph.PrimitiveImplementationNode.create_full_qualified_name(primitive_name, extension, ctype)
                  )
                  required_instantiation_node = TSLDependencyGraph.PrimitiveImplementationNode(
                    TSLDependencyGraph.PrimitiveImplementationNode.create_full_qualified_name(required_primitive_name, extension, ctype)
                  )
                  self.__dependency_graph.add_node(required_instantiation_node)
                  self.__dependency_graph.add_edge(required_instantiation_node, primitive_instantiation_node, label="concrete requirement of")

  def __add_tests(self, tsl_lib: TSLLib) -> None:
    '''
    Iterates over all test cases of all primitives.
    Adds a PrimitiveTestNode per test to the dependency graph and connects the test-node with the corresponding primitive node with a named
    edge ("test of").
    If no tests are present, a warning is added to self.__problems.
    '''
    for _, primitive in tsl_lib.known_primitives:
      primitive_name = primitive.declaration.functor_name
      primitive_node = TSLDependencyGraph.PrimitiveNode(primitive_name)
      has_tests: bool = False
      for test_name, _ in primitive.get_tests(copy=False):
        has_tests = True
        test_node = TSLDependencyGraph.PrimitiveTestNode(TSLDependencyGraph.PrimitiveTestNode.create_full_qualified_name(primitive_name, test_name))
        self.__dependency_graph.add_node(test_node)
        self.__dependency_graph.add_edge(test_node, primitive_node, label="test of")
      if not has_tests:
        self.__problems.add_warning(primitive_node, f"Primitive {primitive_name} has no tests")

  def __add_primitive_tests_implementation_dependencies(self, tsl_lib: TSLLib, primitive_pattern: re.Pattern, level_of_detail: TSLInspectionLevelOfDetail) -> None:
    '''
    Iterates  over all test implementations of all primitives.
    If level_of_detail is greater or equal TEST_INSTANTIATION, for the target_extension
    and all provided ctypes a PrimitiveTestImplementationNode is added to the dependency graph as well as a named
    edge ("concrete instantiation of") betwwen the implementation-node and the test-node.
    For every test implementation, the implementation is checked, whether other tsl-primitives are used.
    If a requirement is found, an edge (with the label "requirement of") is added to the graph,
    connecting the required primitive node with the dependent test.
    The case of a primitive depending on itself is ignored (no id-edges are added).
    If a required primitive does not exist in the graph, an error is added to self.__problems.
    If level_of_detail is greater or equal TEST_INSTANTIATION, for the target_extension
    and all provided ctypes a PrimitiveImplementationNode for the __required__ primitive is added as well as
    a named edge ("concrete requirement of") between the dependent implementation-node and the required one.
    If a required primitive does not exist in the graph, an exception is raised.
    '''
    for _, primitive in tsl_lib.known_primitives:
      primitive_name = primitive.declaration.functor_name
      for test_name, test_implementation in primitive.get_tests(copy=False):
        test_node = TSLDependencyGraph.PrimitiveTestNode(TSLDependencyGraph.PrimitiveTestNode.create_full_qualified_name(primitive_name, test_name))
        if level_of_detail.value >= TSLInspectionLevelOfDetail.TEST_INSTANTIATION:
          for target_extension, ctype_list in primitive.specialization_dict().items():
            for ctype in ctype_list:
              primitive_test_instantiation_node = TSLDependencyGraph.PrimitiveTestImplementationNode(
                TSLDependencyGraph.PrimitiveTestImplementationNode.create_full_qualified_name(primitive_name, test_name, target_extension, ctype)
              )
              self.__dependency_graph.add_node(primitive_test_instantiation_node)
              self.__dependency_graph.add_edge(primitive_test_instantiation_node, test_node, label="concrete instantiation of")
        for match in primitive_pattern.finditer(test_implementation):
          required_primitive_name = match.group("primitive").strip()
          if required_primitive_name != primitive_name:
            required_primitive_node = TSLDependencyGraph.PrimitiveNode(required_primitive_name)
            if required_primitive_node not in self.__dependency_graph:
              self.__problems.add_error(test_node, f"Unknown primitive {required_primitive_name} (required by {test_node}")
              continue
            self.__dependency_graph.add_edge(required_primitive_node, test_node, label="requirement of")
            if level_of_detail.value >= TSLInspectionLevelOfDetail.TEST_INSTANTIATION:
              # Check, if a specific tsl extension was specified
              if "simd_type" in match.groupdict():
                if "ctype" in match.group_dict() and "extension" in match.group_dict():
                  required_instantiation_node = TSLDependencyGraph.PrimitiveImplementationNode(
                    TSLDependencyGraph.PrimitiveImplementationNode.create_full_qualified_name(required_primitive_name, match.group("extension").strip(), match.group("ctype").strip())
                  )
                  if required_instantiation_node not in self.__dependency_graph:
                    self.__problems.add_error(test_node, f"Unknown primitive specialization {required_instantiation_node} (required by {test_node}")
                    continue
                  for target_extension, ctype_list in primitive.specialization_dict().items():
                    for ctype in ctype_list:
                      primitive_test_instantiation_node = TSLDependencyGraph.PrimitiveTestImplementationNode(
                        TSLDependencyGraph.PrimitiveTestImplementationNode.create_full_qualified_name(primitive_name, test_name, target_extension, ctype)
                      )
                      self.__dependency_graph.add_edge(
                        required_instantiation_node, 
                        primitive_test_instantiation_node, label="concrete requirement of")
                else:
                  raise ValueError("Found simd_type but no ctype AND extension")
              else:
                # Generic one -> add all possible nodes
                for target_extension, ctype_list in primitive.specialization_dict().items():
                  for ctype in ctype_list:
                    required_instantiation_node = TSLDependencyGraph.PrimitiveImplementationNode(
                      TSLDependencyGraph.PrimitiveImplementationNode.create_full_qualified_name(required_primitive_name, match.group("extension").strip(), match.group("ctype").strip())
                    )
                    if required_instantiation_node not in self.__dependency_graph:
                      self.__problems.add_error(test_node, f"Unknown primitive specialization {required_instantiation_node} (required by {test_node}")
                      continue
                    primitive_test_instantiation_node = TSLDependencyGraph.PrimitiveTestImplementationNode(
                      TSLDependencyGraph.PrimitiveTestImplementationNode.create_full_qualified_name(primitive_name, test_name, target_extension, ctype)
                    )
                    self.__dependency_graph.add_edge(
                      required_instantiation_node, 
                      primitive_test_instantiation_node, label="concrete requirement of")

  def __add_implicit_class_dependencies(self) -> None:
    '''
    Adds implicit class dependencies.
    If a primitive P1 (associated with class C1) depends on another primitive P2 (associated with class C2),
    the dependency between C1 and C2 is added to the graph.
    '''
    for primitive_node in self.nodes_by_type([TSLDependencyGraph.PrimitiveNode]):
      for _, class_node in self.edges_by_label("part of", "out", [primitive_node]):
        if not isinstance(class_node, TSLDependencyGraph.PrimitiveClassNode):
          raise ValueError(f"Expected PrimitiveClassNode but found {class_node}")
        for required_primitive_node, _ in self.edges_by_label("requirement of", "in", [primitive_node]):
          if not isinstance(required_primitive_node, TSLDependencyGraph.PrimitiveNode):
            raise ValueError(f"Expected PrimitiveNode but found {required_primitive_node}")
          for _, required_class_node in self.edges_by_label("part of", "out", [required_primitive_node]):
            if not isinstance(required_class_node, TSLDependencyGraph.PrimitiveClassNode):
              raise ValueError(f"Expected PrimitiveClassNode but found {required_class_node}")
            self.__dependency_graph.add_edge(required_class_node, class_node, label="implicit requirement of")
    
  def __analyze_tests(self) -> None:
    '''
    Analyzes the given test nodes and adds warnings to self.__problems if a test is not marked as "implicit reliable" and
    the corresponding primitive is not tested.
    '''
    for primitive_node in self.nodes_by_type([TSLDependencyGraph.PrimitiveNode]):
      has_tests: bool = False
      for test_node, _ in self.edges_by_label("test of", "in", [primitive_node]):
        has_tests = True

  def __init__(self, tsl_lib: TSLLib, level_of_detail: TSLInspectionLevelOfDetail = TSLInspectionLevelOfDetail.TEST_INSTANTIATION) -> None:
    self.__dependency_graph: nx.DiGraph = nx.DiGraph()
    self.__level_of_detail = level_of_detail
    self.__problems: TSLDependencyGraph.ProblemsContainer = TSLDependencyGraph.ProblemsContainer()

    ### Step 1: Add all primitive-classes to the dependency graph
    self.__add_primitive_classes(tsl_lib)
    ### Step 2: Add all primitives to the dependency graph and connect the primitives with their associated primitive-classes
    self.__add_primitives(tsl_lib)
    ### Step 3: Create Regex for parsing implementations
    # regex str for all known primitives, e.g., (?P<primitive>add|sub|mul|div)
    known_primitives_regex = rf'(?P<primitive>{"|".join(tsl_lib.distinct_primitive_names())})'
    # regex str ensuring that the primitive name is not part of a longer word, e.g., (?<!([a-zA-Z]|_))add(?!([a-zA-Z]|_|\[|\.|\())
    primitive_regex = rf'(?<!([a-zA-Z]|_))({known_primitives_regex})(?!([a-zA-Z]|_|\[|\.|\())'
    if level_of_detail.value >= TSLInspectionLevelOfDetail.PRIMITIVE_INSTANTIATION.value:
      # regex str for all known extensions, e.g., (?P<extension>sse|avx2|avx512)
      extension_regex = rf'(?P<extension>{"|".join(map(lambda extension: extension.name, tsl_lib.extension_set))})'
      # regex str for all known ctypes, e.g., (?P<ctype>float|double|uint8_t)
      ctype_regex = rf'(?P<ctype>{"|".join(tsl_lib.primitive_class_set.known_ctypes)})'
      # regex str to capture all simd types (with arbitrary number of whitespaces in between), the trailing ? is meant to indicate, that it is possible, that we don't find it. In such a case we assume that the dependent simd type equals the current simd type
      simd_regex = rf'(?P<simd_type>simd\s*<\s*{ctype_regex}\s*,\s*{extension_regex})?'
      # combined regex str 
      tsl_primitive_regex = rf'{primitive_regex}\s*<\s*{simd_regex}'
    else:
      tsl_primitive_regex = rf'{primitive_regex}'  
    # compile regex
    primitive_pattern = re.compile(tsl_primitive_regex)

    # Step 4: Inspect Primitive implementations for dependencies
    self.__add_primitive_implementation_dependencies(tsl_lib, primitive_pattern, level_of_detail)

    # Step 5: Add implicit class dependencies (derived from the primitive dependencies)
    self.__add_implicit_class_dependencies()

    # Step 6: If level of detail is greater or equal TEST, add tests to the dependency graph and connect them with their associated primitive
    if level_of_detail.value < TSLInspectionLevelOfDetail.TEST.value:
      return
    self.__add_tests(tsl_lib)

    # Step 7: If level of detail is greater or equal TEST_IMPLEMENTATION, inspect test implementations for dependencies
    if level_of_detail.value < TSLInspectionLevelOfDetail.TEST_IMPLEMENTATION:
      return
    self.__add_primitive_tests_implementation_dependencies(tsl_lib, primitive_pattern, level_of_detail)

  def subgraph(self, level_of_detail: TSLDependencyGraphLevelOfDetail) -> nx.DiGraph:
    if level_of_detail == TSLDependencyGraphLevelOfDetail.CLASS:
      return self.__dependency_graph.subgraph([node for node in self.nodes_by_type([TSLDependencyGraph.PrimitiveClassNode])])
    if self.__level_of_detail.value > TSLInspectionLevelOfDetail.CLASS.value:
      if level_of_detail == TSLDependencyGraphLevelOfDetail.PRIMITIVE:
        return self.__dependency_graph.subgraph([node for node in self.nodes_by_type([TSLDependencyGraph.PrimitiveClassNode, TSLDependencyGraph.PrimitiveNode])])
      if level_of_detail == TSLDependencyGraphLevelOfDetail.PRIMITIVE_IMPLEMENTATION:
        return self.__dependency_graph.subgraph([node for node in self.nodes_by_type([TSLDependencyGraph.PrimitiveClassNode, TSLDependencyGraph.PrimitiveNode, TSLDependencyGraph.PrimitiveImplementationNode])])
      if self.__level_of_detail > TSLInspectionLevelOfDetail.PRIMITIVE_INSTANTIATION.value:
        if level_of_detail == TSLDependencyGraphLevelOfDetail.TEST:
          return self.__dependency_graph.subgraph([node for node in self.nodes_by_type([TSLDependencyGraph.PrimitiveClassNode, TSLDependencyGraph.PrimitiveNode, TSLDependencyGraph.PrimitiveImplementationNode, TSLDependencyGraph.PrimitiveTestNode])])
        else:
          return self.__dependency_graph.subgraph([node for node in self.nodes_by_type([TSLDependencyGraph.PrimitiveClassNode, TSLDependencyGraph.PrimitiveNode, TSLDependencyGraph.PrimitiveImplementationNode, TSLDependencyGraph.PrimitiveTestNode, TSLDependencyGraph.PrimitiveTestImplementationNode])])
    raise ValueError("Inspection level lower than subgraph level")

  



  def predecessors_by_type(self, node: NodeType, node_types_of_interest: list) -> Generator[NodeType, None, None]:
    for edge in filter(lambda edge: any(isinstance(edge[0], node_type) for node_type in node_types_of_interest), self.__dependency_graph.in_edges(node)):
      yield edge[0]

  def first_predecessor_by_type(self, node: NodeType, node_types_of_interest: list) -> NodeType|None:
    for edge in filter(lambda edge: any(isinstance(edge[0], node_type) for node_type in node_types_of_interest), self.__dependency_graph.in_edges(node)):
      return edge[0]
    return None

  def successors_by_type(self, node: NodeType, node_types_of_interest: list) -> Generator[NodeType, None, None]:
    for edge in filter(lambda edge: any(isinstance(edge[1], node_type) for node_type in node_types_of_interest), self.__dependency_graph.out_edges(node)):
      yield edge[1]
  
  def first_successor_by_type(self, node: NodeType, node_types_of_interest: list) -> NodeType|None:
    for edge in filter(lambda edge: any(isinstance(edge[1], node_type) for node_type in node_types_of_interest), self.__dependency_graph.out_edges(node)):
      return edge[1]
    return None

  def is_acyclic(self) -> bool:
    return nx.is_directed_acyclic_graph(self.__dependency_graph)

  def get_cycles_as_str(self) -> List[str]:
    return list(map(lambda list_of_nodes: " -> ".join(map(lambda node: node.name, list_of_nodes)), nx.simple_cycles(self.__dependency_graph)))
  
  def class_nodes(self) -> Generator[TSLDependencyGraph.PrimitiveClassNode, None, None]:
    for primitive_class in self.__tsl_lib.primitive_class_set:
      yield self.PrimitiveClassNode(primitive_class.name)
  
  def get_required_primitives(self, node: NodeType, self_contained: bool = False) -> Generator[TSLDependencyGraph.PrimitiveNode, None, None]:
    yield from self.traverse_by_type([node], [TSLDependencyGraph.PrimitiveNode], True, self_contained)
    
  def get_dependent_primitives(self, node: NodeType, self_contained: bool = False) -> Generator[TSLDependencyGraph.PrimitiveNode, None, None]:
    yield from self.traverse_by_type([node], [TSLDependencyGraph.PrimitiveNode], False, self_contained)
  
  def get_associated_class(self, node: NodeType) -> TSLDependencyGraph.PrimitiveClassNode:
    if isinstance(node, self.PrimitiveClassNode):
      return node
    elif isinstance(node, TSLDependencyGraph.PrimitiveNode):
      successor = self.first_successor_by_type(node, [self.PrimitiveClassNode])
      if successor is not None:
        return successor
      raise Exception(f"Primitive {node.name} has no associated class.")
    elif isinstance(node, self.PrimitiveTestNode):
      primitive_node = self.first_successor_by_type(node, [TSLDependencyGraph.PrimitiveNode])
      if primitive_node is not None:
        successor = self.first_successor_by_type(primitive_node, [self.PrimitiveClassNode])
        if successor is not None:
          return successor
        raise Exception(f"Primitive {node.name} has no associated class.")
      raise Exception(f"Test {node.name} has no associated primitive.")
        
  def get_required_classes(self, node: NodeType) -> Set[TSLDependencyGraph.PrimitiveClassNode]:
    node_set: Set[TSLDependencyGraph.PrimitiveClassNode] = set()
    if not isinstance(node, TSLDependencyGraph.PrimitiveClassNode):
      node_set.add(self.get_associated_class(node))
    for child_node in self.traverse_by_type([node], [TSLDependencyGraph.PrimitiveNode, TSLDependencyGraph.PrimitiveTestNode], True, False):
      node_set.add(self.get_associated_class(child_node))
    return node_set

  def get_dependent_classes(self, node: NodeType) -> Set[TSLDependencyGraph.PrimitiveClassNode]:
    node_set: Set[TSLDependencyGraph.PrimitiveClassNode] = set()
    if not isinstance(node, TSLDependencyGraph.PrimitiveClassNode):
      node_set.add(self.get_associated_class(node))
    for child_node in self.traverse_by_type([node], [TSLDependencyGraph.PrimitiveNode, TSLDependencyGraph.PrimitiveTestNode], False, False):
      node_set.add(self.get_associated_class(child_node))    

  def get_required_tests(self, node: NodeType) -> Set[TSLDependencyGraph.PrimitiveTestNode]:
    node_set: Set[TSLDependencyGraph.PrimitiveTestNode] = set()
    for child_node in self.traverse_by_type([node], [TSLDependencyGraph.PrimitiveTestNode], True, False):
      node_set.add(child_node)
    return node_set
  
  def get_dependent_tests(self, node: NodeType) -> Set[TSLDependencyGraph.PrimitiveTestNode]:
    node_set: Set[TSLDependencyGraph.PrimitiveTestNode] = set()
    for successor_node in self.traverse_by_type([node], [TSLDependencyGraph.PrimitiveTestNode], False, False):
      node_set.add(successor_node)
    return node_set
    
  def tested_primitive_count(self) -> int:
    nodes = self.nodes_by_type([TSLDependencyGraph.PrimitiveNode])
    result = 0
    for primitive_node in nodes:
      if len([test_case for test_case in self.predecessors_by_type(primitive_node, [TSLDependencyGraph.PrimitiveTestNode])]) > 0:
        result += 1
    return result
  
  def missing_tests(self) -> Generator[TSLDependencyGraph.PrimitiveNode, None, None]:
    nodes = self.nodes_by_type([TSLDependencyGraph.PrimitiveNode])
    for primitive_node in nodes:
      if self.first_predecessor_by_type(primitive_node, [TSLDependencyGraph.PrimitiveTestNode]) is None:
        yield primitive_node

  def unsafe_tests_as_str(self) -> Generator[str, None, None]:
    def traverse_dfs(node: TSLDependencyGraph.NodeType, output_str: str) -> Generator[str, None, None]:
      if self.first_successor_by_type(node, [TSLDependencyGraph.PrimitiveTestNode, TSLDependencyGraph.PrimitiveNode]) is None:
        yield output_str
      else:
        if isinstance(node, TSLDependencyGraph.PrimitiveNode):
          for successor_node in self.successors_by_type(node, [TSLDependencyGraph.PrimitiveTestNode]):
            yield from traverse_dfs(successor_node, f"{output_str}")
        elif isinstance(node, TSLDependencyGraph.PrimitiveTestNode):
          test = node.name.split("::")
          for successor_node in self.successors_by_type(node, [TSLDependencyGraph.PrimitiveNode]):
            if len(output_str) == 0:
              yield from traverse_dfs(successor_node, f"{test[0]}::<{test[1]}>")
            else:
              yield from traverse_dfs(successor_node, f"{test[0]}::<{test[1]}> -> {output_str}")

    for unsafe_primitive in self.missing_tests():
      for message in traverse_dfs(unsafe_primitive, f"{unsafe_primitive.name}::<MISSING>"):
        if message != f"{unsafe_primitive.name}::<MISSING>":
          yield f"{message}"


  def as_str(self, include_tests: bool = False) -> str:
    class_count = sum(1 for _ in self.nodes_by_type([TSLDependencyGraph.PrimitiveClassNode]))
    primitives_count = sum(1 for _ in self.nodes_by_type([TSLDependencyGraph.PrimitiveNode]))

    missing_tests = [primitive.name for primitive in self.missing_tests()]
    unsafe_test = [message for message in self.unsafe_tests_as_str()]
    unsafe_set = {test_chain.split(" ")[0] for test_chain in unsafe_test}
    longest_primitive_name = max(len(max(missing_tests, key=len)), len(max(unsafe_test, key=len)))
    output_missing_tests = "\n".join(['                          ' + primitive for primitive in missing_tests])
    output_unsafe_tests  = "\n".join(['                          ' + message for message in unsafe_test])
    result = f"""TSL - Summary:
  - # Primitive Classes:  {class_count}
  - # Primitives:         {primitives_count}"""
    if include_tests:
      tests_count = sum(1 for _ in self.nodes_by_type([TSLDependencyGraph.PrimitiveTestNode]))
      tested_primitive_count = self.tested_primitive_count()
      test_coverage = tested_primitive_count / primitives_count
      average_tests_per_primitive = (tests_count / primitives_count)
      result = f"""{result}
  - # Tests:              {tests_count}
  - Primitives w/ Tests:  {tested_primitive_count}
  - Primitives w/o Tests: 
{output_missing_tests}
                          {'='*longest_primitive_name}
                          {primitives_count - tested_primitive_count}
  - Unsafe Tests:          
{output_unsafe_tests}
                          {'='*longest_primitive_name}
                          {len(unsafe_set)} ({len(unsafe_test)} specific missing dependencies)
  - Test Coverage:        {test_coverage * 100:.2f}%
  - Avg. Tests/Primitive: {average_tests_per_primitive:.2f}"""
    return result

  def draw(self, out_name: str = "dependency_graph"):
    from networkx.drawing.nx_agraph import to_agraph
    g = to_agraph(self.__dependency_graph)
    # pos = nx.nx_agraph.graphviz_layout(self.__graph)
    g.layout()
    config.generation_out_path.joinpath(out_name).with_suffix(".png").parent.mkdir(parents=True, exist_ok=True)
    g.draw(config.generation_out_path.joinpath(out_name).with_suffix(".png"), prog='dot')
    
  def to_pandas(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
    edge_list = []
    node_list = []
    # Iterate over edges and nodes in the dependency graph
    for source, target in self.__dependency_graph.edges():
      source_node = source
      target_node = target
      edge_data = {
        'from': source_node.id(),
        'to': target_node.id(),
        'weight': 1,
        'strength': "medium",
        **self.__dependency_graph.get_edge_data(source, target)
      }
      edge_list.append(edge_data)
    for node in self.__dependency_graph.nodes():
      node_data = {
        'id': node.id(),
        **node.attributes()
      }
      node_list.append(node_data)
    edge_df = pd.DataFrame(edge_list)
    node_df = pd.DataFrame(node_list)
    return edge_df, node_df
  
  def to_json(self, out_name: str = "dependency_graph") -> None:
    edge_df, node_df = self.to_pandas()
    edge_df.to_json(config.generation_out_path.joinpath(out_name).with_suffix(".edges.json"))
    node_df.to_json(config.generation_out_path.joinpath(out_name).with_suffix(".nodes.json"))

  def to_jaal(self) -> None:
    from jaal import Jaal
    edge_df, node_df = self.to_pandas()
    port=8050
    while True:
      try:
        Jaal(edge_df, node_df).plot(directed=True,port=port)
      except Exception as err:
        print(f"Unexpected {err.__class__.__name__} while trying to start Jaal on port {port}")
        port+=1


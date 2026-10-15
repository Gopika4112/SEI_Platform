
import os
import tree_sitter_python
import tree_sitter_javascript

from tree_sitter import Language, Parser
from typing import Dict, Any, Optional


class CodeParser:
    """
    Parses source code using Tree-sitter.

    Supports Python and JavaScript source files.
    Extracts classes, functions, imports, variables, and basic function calls.
    """

    def __init__(self, language: str = "python"):
        self.language = language.lower()

        if self.language in ("python", "py"):
            grammar = Language(tree_sitter_python.language())
            self.language = "python"

        elif self.language in ("javascript", "js", "jsx"):
            grammar = Language(tree_sitter_javascript.language())
            self.language = "javascript"

        else:
            raise ValueError(
                f"Language '{language}' is not currently supported."
            )

        self.parser = Parser(grammar)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a source file and extract its code structures.

        Python files use the existing Python traversal logic.
        JavaScript files use the JavaScript extraction logic.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Source file not found: {file_path}"
            )

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:
            code = file.read()

        if self.language == "javascript":
            extracted = self.extract_javascript(code)
            extracted["file_path"] = file_path
            return extracted

        tree = self.parser.parse(code.encode("utf-8"))
        root_node = tree.root_node

        extracted = {
            "file_path": file_path,
            "language": "python",
            "classes": [],
            "functions": [],
            "imports": [],
            "variables": [],
        }

        self._traverse(root_node, code, extracted)

        return extracted

    def _traverse(
        self,
        node,
        code: str,
        result: Dict[str, Any],
        current_class: Optional[str] = None,
        in_function: bool = False,
    ):
        """
        Recursively traverse a Python AST and extract code structures.
        """
        node_text = code[node.start_byte:node.end_byte]

        # Python imports
        if node.type in ("import_statement", "import_from_statement"):
            result["imports"].append({
                "type": node.type,
                "text": node_text,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })

        # Python class definitions
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")

            class_name = (
                code[name_node.start_byte:name_node.end_byte]
                if name_node
                else "UnknownClass"
            )

            # Extract base classes
            bases = []
            superclasses_node = node.child_by_field_name("superclasses")

            if superclasses_node:
                for child in superclasses_node.children:
                    if child.type in ("identifier", "attribute"):
                        bases.append(
                            code[child.start_byte:child.end_byte]
                        )

            docstring = self._extract_docstring(node, code)

            class_data = {
                "name": class_name,
                "bases": bases,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "text": node_text,
                "docstring": docstring,
                "methods": [],
            }

            result["classes"].append(class_data)

            body_node = node.child_by_field_name("body")

            if body_node:
                self._traverse(
                    body_node,
                    code,
                    result,
                    current_class=class_name,
                    in_function=in_function,
                )

            return

        # Python function definitions
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")

            function_name = (
                code[name_node.start_byte:name_node.end_byte]
                if name_node
                else "UnknownFunction"
            )

            # Extract function parameters
            parameters = []
            parameters_node = node.child_by_field_name("parameters")

            if parameters_node:
                for param in parameters_node.children:
                    if param.type in (
                        "identifier",
                        "typed_parameter",
                        "default_parameter",
                        "dictionary_splat_pattern",
                        "list_splat_pattern",
                    ):
                        parameters.append(
                            code[param.start_byte:param.end_byte]
                        )

            docstring = self._extract_docstring(node, code)

            function_data = {
                "name": function_name,
                "parent_class": current_class,
                "parameters": parameters,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "text": node_text,
                "docstring": docstring,
            }

            if current_class:
                # Attach the function to its class as a method.
                for cls in reversed(result["classes"]):
                    if cls["name"] == current_class:
                        cls["methods"].append(function_data)
                        break
            else:
                result["functions"].append(function_data)

            # Traverse the function body for nested structures.
            body_node = node.child_by_field_name("body")

            if body_node:
                self._traverse(
                    body_node,
                    code,
                    result,
                    current_class=current_class,
                    in_function=True,
                )

            return

        # Module-level Python assignments
        elif node.type == "assignment" and current_class is None and not in_function:
            left_node = node.child_by_field_name("left")

            if left_node and left_node.type == "identifier":
                variable_name = code[
                    left_node.start_byte:left_node.end_byte
                ]

                result["variables"].append({
                    "name": variable_name,
                    "line": node.start_point[0] + 1,
                    "text": node_text,
                })

        # Continue traversing remaining children
        for child in node.children:
            self._traverse(
                child,
                code,
                result,
                current_class,
                in_function,
            )

    def _extract_docstring(self, node, code: str) -> str:
        """
        Extract a leading Python string expression from a class or function.
        """
        body_node = node.child_by_field_name("body")

        if not body_node:
            return ""

        first_statement = None

        for child in body_node.children:
            if child.type != "comment":
                first_statement = child
                break

        if not first_statement:
            return ""

        if first_statement.type == "expression_statement":
            if not first_statement.children:
                return ""

            expression = first_statement.children[0]

            if expression.type == "string":
                text = code[
                    expression.start_byte:expression.end_byte
                ]

                if text.startswith('"""') and text.endswith('"""'):
                    return text[3:-3].strip()

                if text.startswith("'''") and text.endswith("'''"):
                    return text[3:-3].strip()

                if text.startswith('"') and text.endswith('"'):
                    return text[1:-1].strip()

                if text.startswith("'") and text.endswith("'"):
                    return text[1:-1].strip()

        return ""

    def _node_text(self, node, source_bytes: bytes) -> str:
        """Return the source text covered by a Tree-sitter node."""
        return source_bytes[
            node.start_byte:node.end_byte
        ].decode("utf-8", errors="replace")

    def extract_javascript(
        self,
        source_code: str,
    ) -> Dict[str, Any]:
        """
        Extract basic JavaScript structures.

        Supports function declarations, arrow/function expressions assigned
        to variables, class declarations and methods, imports, variables,
        inheritance, and function calls.
        """
        source_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        root = tree.root_node

        result = {
            "language": "javascript",
            "classes": [],
            "functions": [],
            "imports": [],
            "variables": [],
            "calls": [],
            "has_syntax_errors": root.has_error,
        }

        def get_parameters(function_node):
            parameters_node = function_node.child_by_field_name("parameters")
            if parameters_node is None:
                parameters_node = function_node.child_by_field_name("parameter")

            if parameters_node is None:
                return []

            if parameters_node.type in ("formal_parameters", "parameters"):
                return [
                    self._node_text(child, source_bytes)
                    for child in parameters_node.named_children
                ]

            return [self._node_text(parameters_node, source_bytes)]

        def walk(node, current_class=None, in_function=False):
            node_type = node.type

            # JavaScript class declarations
            if node_type == "class_declaration":
                name_node = node.child_by_field_name("name")

                class_name = (
                    self._node_text(name_node, source_bytes)
                    if name_node
                    else "<anonymous>"
                )

                heritage_node = next(
                    (
                        child
                        for child in node.named_children
                        if child.type == "class_heritage"
                    ),
                    None,
                )
                bases = (
                    [
                        self._node_text(child, source_bytes)
                        for child in heritage_node.named_children
                    ]
                    if heritage_node
                    else []
                )

                class_data = {
                    "name": class_name,
                    "bases": bases,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "text": self._node_text(node, source_bytes),
                    "docstring": "",
                    "methods": [],
                }

                result["classes"].append(class_data)
                current_class = class_name

            # Named JavaScript function declarations
            elif node_type == "function_declaration":
                name_node = node.child_by_field_name("name")

                function_name = (
                    self._node_text(name_node, source_bytes)
                    if name_node
                    else "<anonymous>"
                )

                parameters = get_parameters(node)

                result["functions"].append({
                    "name": function_name,
                    "parent_class": current_class,
                    "parameters": parameters,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "text": self._node_text(node, source_bytes),
                    "docstring": "",
                    "kind": "function",
                })
                in_function = True

            # JavaScript class methods
            elif node_type == "method_definition":
                name_node = node.child_by_field_name("name")

                if name_node:
                    method_name = self._node_text(
                        name_node,
                        source_bytes,
                    )

                    parameters = get_parameters(node)

                    method_data = {
                        "name": method_name,
                        "parent_class": current_class,
                        "parameters": parameters,
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "text": self._node_text(node, source_bytes),
                        "docstring": "",
                        "kind": "method",
                    }

                    # Attach the method to its containing class.
                    for cls in reversed(result["classes"]):
                        if cls["name"] == current_class:
                            cls["methods"].append(method_data)
                            break
                in_function = True

            # ES module imports
            elif node_type == "import_statement":
                result["imports"].append({
                    "type": node_type,
                    "text": self._node_text(node, source_bytes),
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                })

            # Function calls
            elif node_type == "call_expression":
                function_node = node.child_by_field_name("function")

                if function_node:
                    result["calls"].append({
                        "name": self._node_text(
                            function_node,
                            source_bytes,
                        ),
                        "start_line": node.start_point[0] + 1,
                    })

            # Module-level variables and functions assigned to variables
            elif node_type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                value_node = node.child_by_field_name("value")

                if name_node:
                    name = self._node_text(name_node, source_bytes)

                    if current_class is None and not in_function:
                        declaration_node = node.parent
                        if declaration_node and declaration_node.type in (
                            "lexical_declaration",
                            "variable_declaration",
                        ):
                            declaration_keyword = self._node_text(
                                declaration_node.children[0],
                                source_bytes,
                            )
                            declaration_text = (
                                f"{declaration_keyword} "
                                f"{self._node_text(node, source_bytes)}"
                            )
                        else:
                            declaration_text = self._node_text(
                                node,
                                source_bytes,
                            )

                        result["variables"].append({
                            "name": name,
                            "line": node.start_point[0] + 1,
                            "text": declaration_text,
                        })

                    if value_node and value_node.type in (
                        "arrow_function",
                        "function_expression",
                    ):
                        result["functions"].append({
                            "name": name,
                            "parent_class": current_class,
                            "parameters": get_parameters(value_node),
                            "start_line": value_node.start_point[0] + 1,
                            "end_line": value_node.end_point[0] + 1,
                            "text": self._node_text(value_node, source_bytes),
                            "docstring": "",
                            "kind": "function",
                        })

            elif node_type in ("arrow_function", "function_expression"):
                in_function = True

            # Visit children to discover nested structures.
            for child in node.children:
                walk(child, current_class, in_function)

        walk(root)

        return result

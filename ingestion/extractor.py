
import os
import re
import tree_sitter_python
import tree_sitter_javascript

from tree_sitter import Language, Parser
from typing import Dict, Any, List, Tuple, Optional


class EntityRelationshipExtractor:
    """
    Extracts structural relationships from Python and JavaScript source code.

    Relationships:
        IMPORTS
        CALLS
        INHERITS
        DEFINED_IN
        HAS_METHOD
    """

    def __init__(self):
        self.parsers = {
            "python": Parser(
                Language(tree_sitter_python.language())
            ),
            "javascript": Parser(
                Language(tree_sitter_javascript.language())
            ),
        }

    def extract_relationships(
        self,
        file_path: str,
        ast_nodes: Dict[str, Any],
    ) -> List[Tuple[Dict[str, Any], str, Dict[str, Any]]]:
        """
        Extract graph relationships from the AST dictionary returned
        by CodeParser.parse_file().
        """
        extension = os.path.splitext(file_path)[1].lower()

        language = ast_nodes.get("language", "").lower()

        if not language:
            language = (
                "javascript"
                if extension in (".js", ".jsx", ".mjs", ".cjs")
                else "python"
            )

        if language in ("js", "jsx", "javascript"):
            return self._extract_javascript_relationships(
                file_path, ast_nodes
            )

        return self._extract_python_relationships(
            file_path, ast_nodes
        )

    def _make_node(
        self,
        name: str,
        type_label: str,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a graph node dictionary."""
        meta = dict(metadata or {})
        meta["file_path"] = file_path

        return {
            "name": name,
            "label": type_label,
            "metadata": meta,
        }

    # ---------------------------------------------------------
    # PYTHON RELATIONSHIPS
    # ---------------------------------------------------------

    def _extract_python_relationships(
        self,
        file_path: str,
        ast_nodes: Dict[str, Any],
    ) -> List[Tuple[Dict[str, Any], str, Dict[str, Any]]]:
        """Extract relationships from Python parser output."""
        relationships = []
        file_name = os.path.basename(file_path)

        file_node = self._make_node(
            file_name,
            "File",
            file_path,
            {"absolute_path": file_path, "language": "python"},
        )

        # 1. IMPORTS
        for imp in ast_nodes.get("imports", []):
            import_text = imp.get("text", "")
            imported_modules = self._parse_python_import_targets(
                import_text
            )

            for module in imported_modules:
                module_node = self._make_node(
                    module, "Module", file_path
                )
                relationships.append(
                    (file_node, "IMPORTS", module_node)
                )

        # 2. CLASSES, INHERITANCE, AND METHODS
        for cls in ast_nodes.get("classes", []):
            class_name = cls.get("name", "UnknownClass")

            class_node = self._make_node(
                class_name,
                "Class",
                file_path,
                {
                    "start_line": cls.get("start_line"),
                    "end_line": cls.get("end_line"),
                    "language": "python",
                },
            )

            relationships.append(
                (class_node, "DEFINED_IN", file_node)
            )

            for base in cls.get("bases", []):
                base_node = self._make_node(
                    base, "Class", file_path
                )
                relationships.append(
                    (class_node, "INHERITS", base_node)
                )

            for method in cls.get("methods", []):
                method_name = method.get("name", "UnknownMethod")

                method_node = self._make_node(
                    method_name,
                    "Method",
                    file_path,
                    {
                        "parent_class": class_name,
                        "start_line": method.get("start_line"),
                        "end_line": method.get("end_line"),
                        "language": "python",
                    },
                )

                relationships.append(
                    (class_node, "HAS_METHOD", method_node)
                )
                relationships.append(
                    (method_node, "DEFINED_IN", file_node)
                )

                for call in self._extract_calls_from_text(
                    method.get("text", ""),
                    "python",
                ):
                    called_node = self._make_node(
                        call, "Function", file_path
                    )
                    relationships.append(
                        (method_node, "CALLS", called_node)
                    )

        # 3. STANDALONE FUNCTIONS
        for func in ast_nodes.get("functions", []):
            function_name = func.get("name", "UnknownFunction")

            function_node = self._make_node(
                function_name,
                "Function",
                file_path,
                {
                    "start_line": func.get("start_line"),
                    "end_line": func.get("end_line"),
                    "language": "python",
                },
            )

            relationships.append(
                (function_node, "DEFINED_IN", file_node)
            )

            for call in self._extract_calls_from_text(
                func.get("text", ""),
                "python",
            ):
                called_node = self._make_node(
                    call, "Function", file_path
                )
                relationships.append(
                    (function_node, "CALLS", called_node)
                )

        return relationships

    # ---------------------------------------------------------
    # JAVASCRIPT RELATIONSHIPS
    # ---------------------------------------------------------

    def _extract_javascript_relationships(
        self,
        file_path: str,
        ast_nodes: Dict[str, Any],
    ) -> List[Tuple[Dict[str, Any], str, Dict[str, Any]]]:
        """Extract relationships from JavaScript parser output."""
        relationships = []
        file_name = os.path.basename(file_path)

        file_node = self._make_node(
            file_name,
            "File",
            file_path,
            {
                "absolute_path": file_path,
                "language": "javascript",
            },
        )

        # 1. IMPORTS
        for imp in ast_nodes.get("imports", []):
            import_text = imp.get("text", imp.get("code", ""))

            for module in self._parse_javascript_import_targets(
                import_text
            ):
                module_node = self._make_node(
                    module,
                    "Module",
                    file_path,
                    {"language": "javascript"},
                )

                relationships.append(
                    (file_node, "IMPORTS", module_node)
                )

        # 2. CLASSES, INHERITANCE, AND METHODS
        for cls in ast_nodes.get("classes", []):
            class_name = cls.get("name", "UnknownClass")

            class_node = self._make_node(
                class_name,
                "Class",
                file_path,
                {
                    "start_line": cls.get("start_line"),
                    "end_line": cls.get("end_line"),
                    "language": "javascript",
                },
            )

            relationships.append(
                (class_node, "DEFINED_IN", file_node)
            )

            # The JavaScript parser may provide bases as an empty list.
            for base in cls.get("bases", []):
                base_node = self._make_node(
                    base,
                    "Class",
                    file_path,
                    {"language": "javascript"},
                )
                relationships.append(
                    (class_node, "INHERITS", base_node)
                )

            for method in cls.get("methods", []):
                method_name = method.get("name", "UnknownMethod")

                method_node = self._make_node(
                    method_name,
                    "Method",
                    file_path,
                    {
                        "parent_class": class_name,
                        "start_line": method.get("start_line"),
                        "end_line": method.get("end_line"),
                        "language": "javascript",
                    },
                )

                relationships.append(
                    (class_node, "HAS_METHOD", method_node)
                )
                relationships.append(
                    (method_node, "DEFINED_IN", file_node)
                )

                for call in self._extract_calls_from_text(
                    method.get("text", method.get("code", "")),
                    "javascript",
                ):
                    called_node = self._make_node(
                        call,
                        "Function",
                        file_path,
                        {"language": "javascript"},
                    )

                    relationships.append(
                        (method_node, "CALLS", called_node)
                    )

        # 3. STANDALONE FUNCTIONS
        for func in ast_nodes.get("functions", []):
            # Methods are already handled under their classes.
            if func.get("kind") == "method":
                continue

            function_name = func.get("name", "UnknownFunction")

            function_node = self._make_node(
                function_name,
                "Function",
                file_path,
                {
                    "start_line": func.get("start_line"),
                    "end_line": func.get("end_line"),
                    "language": "javascript",
                },
            )

            relationships.append(
                (function_node, "DEFINED_IN", file_node)
            )

            function_text = func.get(
                "text", func.get("code", "")
            )

            for call in self._extract_calls_from_text(
                function_text,
                "javascript",
            ):
                called_node = self._make_node(
                    call,
                    "Function",
                    file_path,
                    {"language": "javascript"},
                )

                relationships.append(
                    (function_node, "CALLS", called_node)
                )

        return relationships

    # ---------------------------------------------------------
    # IMPORT PARSING
    # ---------------------------------------------------------

    def _parse_python_import_targets(
        self,
        import_text: str,
    ) -> List[str]:
        """
        Extract module names from Python imports.

        Examples:
            import os, sys       -> os, sys
            import numpy as np   -> numpy
            from pathlib import Path -> pathlib
        """
        targets = []
        import_text = import_text.strip()

        from_match = re.match(
            r"^from\s+([\w.]+)\s+import\b",
            import_text,
        )

        if from_match:
            targets.append(from_match.group(1))
        else:
            import_match = re.match(
                r"^import\s+(.+)$",
                import_text,
            )

            if import_match:
                for part in import_match.group(1).split(","):
                    name = part.split(" as ")[0].strip()

                    if name:
                        targets.append(name)

        return targets

    def _parse_javascript_import_targets(
        self,
        import_text: str,
    ) -> List[str]:
        """
        Extract module paths from JavaScript ES module imports.

        Examples:
            import express from "express" -> express
            import { getUser } from "./users.js" -> ./users.js
            import "./setup.js" -> ./setup.js
        """
        import_text = import_text.strip()
        targets = []

        # Match the module string in an ES import statement.
        match = re.search(
            r"""(?:\bfrom\s*)?["']([^"']+)["']""",
            import_text,
        )

        if match:
            targets.append(match.group(1))

        return targets

    # ---------------------------------------------------------
    # FUNCTION CALL EXTRACTION
    # ---------------------------------------------------------

    def _extract_calls_from_text(
        self,
        code_text: str,
        language: str = "python",
    ) -> List[str]:
        """
        Parse a function or method body and extract call targets.

        This identifies syntactic call names; it does not resolve
        them to definitions across files.
        """
        language = language.lower()

        if language in ("js", "jsx", "javascript"):
            parser = self.parsers["javascript"]
            call_node_types = ("call_expression",)
        else:
            parser = self.parsers["python"]
            call_node_types = ("call",)

        tree = parser.parse(code_text.encode("utf-8"))
        calls = []

        def traverse(node):
            if node.type in call_node_types:
                function_node = node.child_by_field_name("function")

                if function_node:
                    function_text = code_text[
                        function_node.start_byte:
                        function_node.end_byte
                    ]

                    # For obj.method() or this.method(), retain
                    # the method name, matching existing Python logic.
                    if "." in function_text:
                        function_text = function_text.split(".")[-1]

                    if function_text:
                        calls.append(function_text)

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)

        # Preserve order while removing duplicate call names.
        return list(dict.fromkeys(calls))


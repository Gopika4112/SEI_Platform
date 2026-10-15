import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class CodeChunk:
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

class SemanticChunker:
    """
    Chunks parsed AST results of source files into distinct, syntax-aware CodeChunk objects
    representing classes, methods, functions, and modules.
    """
    def __init__(self):
        pass

    def _get_class_chunk_content(self, cls: Dict[str, Any], max_len: int = 2000) -> str:
        """
        Returns the class content. If the class text exceeds max_len,
        reconstructs a summary containing only the signature, docstring, and method outline.
        """
        full_text = cls.get("text", "")
        if len(full_text) <= max_len:
            return full_text
            
        # Reconstruct class overview to avoid huge payloads
        name = cls.get("name", "Class")
        bases = ", ".join(cls.get("bases", []))
        bases_str = f"({bases})" if bases else ""
        docstring = cls.get("docstring", "")
        docstring_str = f'\n    """\n    {docstring}\n    """' if docstring else ""
        
        methods_outline = []
        for m in cls.get("methods", []):
            params = ", ".join(m.get("parameters", []))
            methods_outline.append(f"    def {m['name']}({params}): ...")
            
        methods_str = "\n".join(methods_outline)
        outline = f"class {name}{bases_str}:{docstring_str}\n\n    # Methods Outline:\n{methods_str}"
        return outline

    def chunk_file(self, file_path: str, ast_nodes: Dict[str, Any]) -> List[CodeChunk]:
        """
        Creates semantic chunks from the parsed AST of a file.
        
        Args:
            file_path: The absolute path of the parsed file.
            ast_nodes: The dict returned by CodeParser.parse_file.
            
        Returns:
            A list of CodeChunk objects ready for vector database indexing.
        """
        chunks = []
        file_name = os.path.basename(file_path)
        
        # 1. Chunk class definitions
        for cls in ast_nodes.get("classes", []):
            class_id = f"{file_path}::class::{cls['name']}"
            chunks.append(CodeChunk(
                id=class_id,
                content=self._get_class_chunk_content(cls, max_len=2000),
                metadata={
                    "file_path": file_path,
                    "name": cls["name"],
                    "entity_type": "class",
                    "start_line": cls["start_line"],
                    "end_line": cls["end_line"],
                    "bases": cls["bases"],
                    "docstring": cls["docstring"]
                }
            ))
            
            # 2. Chunk class methods
            for method in cls.get("methods", []):
                method_id = f"{file_path}::method::{cls['name']}::{method['name']}"
                chunks.append(CodeChunk(
                    id=method_id,
                    content=method["text"],
                    metadata={
                        "file_path": file_path,
                        "name": method["name"],
                        "parent_class": cls["name"],
                        "entity_type": "method",
                        "start_line": method["start_line"],
                        "end_line": method["end_line"],
                        "parameters": method["parameters"],
                        "docstring": method["docstring"]
                    }
                ))
                

import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class CodeChunk:
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


class SemanticChunker:
    """
    Chunks parsed AST results into syntax-aware CodeChunk objects.

    Supports:
    - Python classes, methods, functions, and modules
    - JavaScript classes, methods, functions, and modules
    - Plain-text and Markdown documentation
    """

    def __init__(self):
        pass

    def _get_class_chunk_content(
        self,
        cls: Dict[str, Any],
        max_len: int = 2000,
        language: str = "python",
    ) -> str:
        """
        Return the full class text when it fits within max_len.
        Otherwise, create a compact class overview.
        """
        full_text = cls.get("text", "")

        if len(full_text) <= max_len:
            return full_text

        name = cls.get("name", "Class")
        bases = ", ".join(cls.get("bases", []))
        bases_str = f" extends {bases}" if (
            language == "javascript" and bases
        ) else (f"({bases})" if bases else "")

        docstring = cls.get("docstring", "")
        methods_outline = []

        for method in cls.get("methods", []):
            method_name = method.get("name", "method")
            params = ", ".join(method.get("parameters", []))

            if language == "javascript":
                methods_outline.append(
                    f"    {method_name}({params}) {{ ... }}"
                )
            else:
                methods_outline.append(
                    f"    def {method_name}({params}): ..."
                )

        methods_str = "\n".join(methods_outline)

        if language == "javascript":
            docstring_str = (
                f"\n    // {docstring}" if docstring else ""
            )
            outline = (
                f"class {name}{bases_str} {{{docstring_str}\n"
                f"\n    // Methods Outline:\n{methods_str}\n}}"
            )
        else:
            docstring_str = (
                f'\n    """\n    {docstring}\n    """'
                if docstring else ""
            )
            outline = (
                f"class {name}{bases_str}:{docstring_str}\n"
                f"\n    # Methods Outline:\n{methods_str}"
            )

        return outline

    def _chunk_class(
        self,
        file_path: str,
        cls: Dict[str, Any],
        language: str,
    ) -> List[CodeChunk]:
        """Create a class chunk and its method chunks."""
        chunks = []
        class_name = cls.get("name", "UnknownClass")

        class_id = f"{file_path}::class::{class_name}"

        class_metadata = {
            "file_path": file_path,
            "name": class_name,
            "entity_type": "class",
            "language": language,
            "start_line": cls.get("start_line", 1),
            "end_line": cls.get("end_line", 1),
            "bases": cls.get("bases", []),
            "docstring": cls.get("docstring", ""),
        }

        chunks.append(
            CodeChunk(
                id=class_id,
                content=self._get_class_chunk_content(
                    cls,
                    max_len=2000,
                    language=language,
                ),
                metadata=class_metadata,
            )
        )

        for method in cls.get("methods", []):
            method_name = method.get("name", "UnknownMethod")
            method_id = (
                f"{file_path}::method::{class_name}::{method_name}"
            )

            chunks.append(
                CodeChunk(
                    id=method_id,
                    content=method.get(
                        "text",
                        method.get("code", ""),
                    ),
                    metadata={
                        "file_path": file_path,
                        "name": method_name,
                        "parent_class": class_name,
                        "entity_type": "method",
                        "language": language,
                        "start_line": method.get("start_line", 1),
                        "end_line": method.get("end_line", 1),
                        "parameters": method.get("parameters", []),
                        "docstring": method.get("docstring", ""),
                    },
                )
            )

        return chunks

    def _chunk_function(
        self,
        file_path: str,
        func: Dict[str, Any],
        language: str,
    ) -> CodeChunk:
        """Create a chunk for a standalone function."""
        function_name = func.get("name", "UnknownFunction")
        function_id = f"{file_path}::function::{function_name}"

        return CodeChunk(
            id=function_id,
            content=func.get("text", func.get("code", "")),
            metadata={
                "file_path": file_path,
                "name": function_name,
                "entity_type": "function",
                "language": language,
                "start_line": func.get("start_line", 1),
                "end_line": func.get("end_line", 1),
                "parameters": func.get("parameters", []),
                "docstring": func.get("docstring", ""),
            },
        )

    def chunk_file(
        self,
        file_path: str,
        ast_nodes: Dict[str, Any],
    ) -> List[CodeChunk]:
        """
        Create semantic chunks from the parsed AST.

        The JavaScript branch is selected using the language field
        returned by CodeParser. The file extension is used as a fallback.
        """
        chunks = []
        file_name = os.path.basename(file_path)

        language = ast_nodes.get("language", "").lower()

        if not language:
            extension = os.path.splitext(file_path)[1].lower()
            language = (
                "javascript"
                if extension in (".js", ".jsx", ".mjs", ".cjs")
                else "python"
            )

        if language in ("js", "jsx", "javascript"):
            language = "javascript"
            chunks.extend(
                self._chunk_javascript(file_path, file_name, ast_nodes)
            )
        else:
            chunks.extend(
                self._chunk_python(file_path, file_name, ast_nodes)
            )

        return chunks

    def _chunk_python(
        self,
        file_path: str,
        file_name: str,
        ast_nodes: Dict[str, Any],
    ) -> List[CodeChunk]:
        """Chunk Python classes, methods, functions, and module data."""
        chunks = []

        # 1. Classes and methods
        for cls in ast_nodes.get("classes", []):
            chunks.extend(
                self._chunk_class(file_path, cls, "python")
            )

        # 2. Standalone functions
        for func in ast_nodes.get("functions", []):
            chunks.append(
                self._chunk_function(file_path, func, "python")
            )

        # 3. Module overview
        imports_text = "\n".join(
            imp.get("text", "")
            for imp in ast_nodes.get("imports", [])
        )

        vars_text = "\n".join(
            var.get("text", "")
            for var in ast_nodes.get("variables", [])
        )

        module_content = (
            f"# Module: {file_name}\n\n"
            f"## Imports\n{imports_text}\n\n"
            f"## Globals\n{vars_text}"
        )

        chunks.append(
            CodeChunk(
                id=f"{file_path}::module",
                content=module_content,
                metadata={
                    "file_path": file_path,
                    "name": file_name,
                    "entity_type": "module",
                    "language": "python",
                    "start_line": 1,
                    "end_line": 1,
                },
            )
        )

        return chunks

    def _chunk_javascript(
        self,
        file_path: str,
        file_name: str,
        ast_nodes: Dict[str, Any],
    ) -> List[CodeChunk]:
        """
        Chunk JavaScript classes, methods, functions, and module data.

        Uses the structure returned by CodeParser.extract_javascript().
        """
        chunks = []

        # 1. Classes and their methods
        for cls in ast_nodes.get("classes", []):
            chunks.extend(
                self._chunk_class(file_path, cls, "javascript")
            )

        # 2. Standalone functions
        for func in ast_nodes.get("functions", []):
            # Avoid indexing a function again if it is already
            # represented as a method of a class.
            if func.get("kind") == "method":
                continue

            chunks.append(
                self._chunk_function(file_path, func, "javascript")
            )

        # 3. Imports
        imports_text = "\n".join(
            imp.get("text", imp.get("code", ""))
            for imp in ast_nodes.get("imports", [])
        )

        # 4. Module-level variables
        vars_text = "\n".join(
            var.get("text", "")
            for var in ast_nodes.get("variables", [])
        )

        # 5. Module overview
        module_content = (
            f"// Module: {file_name}\n\n"
            f"// Imports\n{imports_text}\n\n"
            f"// Variables\n{vars_text}"
        )

        chunks.append(
            CodeChunk(
                id=f"{file_path}::module",
                content=module_content,
                metadata={
                    "file_path": file_path,
                    "name": file_name,
                    "entity_type": "module",
                    "language": "javascript",
                    "start_line": 1,
                    "end_line": 1,
                },
            )
        )

        return chunks

    def chunk_text_file(
        self,
        file_path: str,
        content: str,
        chunk_size: int = 1500,
        overlap: int = 200,
    ) -> List[CodeChunk]:
        """
        Chunk plain-text or Markdown files into paragraph-based sections.
        """
        chunks = []
        file_name = os.path.basename(file_path)

        paragraphs = content.split("\n\n")
        current_chunk = []
        current_len = 0
        chunk_index = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()

            if not paragraph:
                continue

            paragraph_len = len(paragraph)

            if (
                current_len + paragraph_len > chunk_size
                and current_chunk
            ):
                chunk_text = "\n\n".join(current_chunk)
                doc_id = f"{file_path}::doc::{chunk_index}"

                chunks.append(
                    CodeChunk(
                        id=doc_id,
                        content=chunk_text,
                        metadata={
                            "file_path": file_path,
                            "name": (
                                f"{file_name} (Part {chunk_index + 1})"
                            ),
                            "entity_type": "documentation",
                            "start_line": 1,
                            "end_line": 1,
                        },
                    )
                )

                chunk_index += 1

                # Retain the last paragraph when it fits the overlap.
                if len(current_chunk[-1]) < overlap:
                    current_chunk = [current_chunk[-1], paragraph]
                    current_len = (
                        len(current_chunk[0]) + paragraph_len + 2
                    )
                else:
                    current_chunk = [paragraph]
                    current_len = paragraph_len

            else:
                current_chunk.append(paragraph)
                current_len += paragraph_len + 2

        # Save the final chunk.
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            doc_id = f"{file_path}::doc::{chunk_index}"

            chunks.append(
                CodeChunk(
                    id=doc_id,
                    content=chunk_text,
                    metadata={
                        "file_path": file_path,
                        "name": (
                            f"{file_name} (Part {chunk_index + 1})"
                        ),
                        "entity_type": "documentation",
                        "start_line": 1,
                        "end_line": 1,
                    },
                )
            )

        return chunks


import logging
import re
import sqlparse
from typing import List, Dict, Any
from langchain_text_splitters import MarkdownHeaderTextSplitter

logger = logging.getLogger(__name__)

class DocumentParser:
    """Document parser factory"""

    @staticmethod
    def parse_markdown(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """
        Parse a Markdown document and split it by headings
        Returns: [{"content": "...", "metadata": {...}}]
        """
        # Define Markdown heading separators
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        docs = markdown_splitter.split_text(content)

        results = []
        for doc in docs:
            # Base metadata
            meta = doc.metadata.copy()
            meta["source"] = source_name
            meta["type"] = "markdown"

            # Build richer contextual content
            # Include the heading path in the content to aid retrieval
            header_path = " > ".join([v for k, v in meta.items() if k.startswith("Header")])
            enriched_content = f"[Document context] {source_name}\n[Section] {header_path}\n\n{doc.page_content}"

            results.append({
                "content": enriched_content,
                "metadata": meta
            })

        return results

    @staticmethod
    def parse_sql(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """
        Parse a SQL file and split it by CREATE TABLE statements
        """
        # Perform initial cleanup with sqlparse
        statements = sqlparse.split(content)

        results = []
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            # Keep CREATE TABLE statements and significant comments
            if "CREATE TABLE" in stmt.upper():
                match = re.search(r'CREATE\s+TABLE\s+[`"\[]?(\w+)[`"\]]?', stmt, re.IGNORECASE)
                table_name = match.group(1) if match else "unknown_table"

                meta = {
                    "source": source_name,
                    "type": "sql_schema",
                    "table_name": table_name
                }

                enriched_content = f"[Database table schema] {table_name}\n[Source] {source_name}\n\n{stmt}"

                results.append({
                    "content": enriched_content,
                    "metadata": meta
                })

        return results

    @staticmethod
    def parse_openapi(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """
        Parse OpenAPI/Swagger JSON text
        """
        import json
        try:
            data = json.loads(content)
            paths = data.get("paths", {})
            results = []

            for path, methods in paths.items():
                for method, details in methods.items():
                    summary = details.get("summary", "No summary")
                    desc = details.get("description", "")

                    api_desc = f"API: {method.upper()} {path}\nSummary: {summary}\nDescription: {desc}"

                    meta = {
                        "source": source_name,
                        "type": "api_spec",
                        "path": path,
                        "method": method.upper()
                    }

                    enriched_content = f"[API definition] {method.upper()} {path}\n[Source] {source_name}\n\n{json.dumps(details, ensure_ascii=False, indent=2)}"

                    results.append({
                        "content": enriched_content,
                        "metadata": meta
                    })
            return results
        except Exception as e:
            logger.error(f"OpenAPI parsing failed: {e}")
            return [{"content": content, "metadata": {"source": source_name, "type": "text_error"}}]

    @staticmethod
    def parse_text(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """General text processing"""
        return [{
            "content": content,
            "metadata": {"source": source_name, "type": "text"}
        }]

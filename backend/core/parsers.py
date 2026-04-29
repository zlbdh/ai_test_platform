import logging
import re
import sqlparse
from typing import List, Dict, Any
from langchain_text_splitters import MarkdownHeaderTextSplitter

logger = logging.getLogger(__name__)

class DocumentParser:
    """文档解析器工厂类"""
    
    @staticmethod
    def parse_markdown(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """
        解析 Markdown 文档，按标题切分
        返回: [{"content": "...", "metadata": {...}}]
        """
        # 定义 Markdown 分割头
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        docs = markdown_splitter.split_text(content)
        
        results = []
        for doc in docs:
            # 基础元数据
            meta = doc.metadata.copy()
            meta["source"] = source_name
            meta["type"] = "markdown"
            
            # 构建更丰富的上下文内容
            # 将标题路径合并到内容中，方便检索
            header_path = " > ".join([v for k, v in meta.items() if k.startswith("Header")])
            enriched_content = f"【文档上下文】{source_name}\n【章节】{header_path}\n\n{doc.page_content}"
            
            results.append({
                "content": enriched_content,
                "metadata": meta
            })
            
        return results

    @staticmethod
    def parse_sql(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """
        解析 SQL 文件，按 CREATE TABLE 语句切分
        """
        # 使用 sqlparse 初步清洗
        statements = sqlparse.split(content)
        
        results = []
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
                
            # 只关注 CREATE TABLE 和重要注释
            if "CREATE TABLE" in stmt.upper():
                match = re.search(r'CREATE\s+TABLE\s+[`"\[]?(\w+)[`"\]]?', stmt, re.IGNORECASE)
                table_name = match.group(1) if match else "unknown_table"
                
                meta = {
                    "source": source_name,
                    "type": "sql_schema",
                    "table_name": table_name
                }
                
                enriched_content = f"【数据库表结构】{table_name}\n【来源】{source_name}\n\n{stmt}"
                
                results.append({
                    "content": enriched_content,
                    "metadata": meta
                })
        
        return results

    @staticmethod
    def parse_openapi(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """
        解析 OpenAPI/Swagger JSON 文本
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
                    
                    enriched_content = f"【API接口定义】{method.upper()} {path}\n【来源】{source_name}\n\n{json.dumps(details, ensure_ascii=False, indent=2)}"
                    
                    results.append({
                        "content": enriched_content,
                        "metadata": meta
                    })
            return results
        except Exception as e:
            logger.error(f"OpenAPI 解析失败: {e}")
            return [{"content": content, "metadata": {"source": source_name, "type": "text_error"}}]

    @staticmethod
    def parse_text(content: str, source_name: str = "") -> List[Dict[str, Any]]:
        """通用文本处理"""
        return [{
            "content": content,
            "metadata": {"source": source_name, "type": "text"}
        }]

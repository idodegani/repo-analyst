"""Code chunking module.

This module handles intelligent chunking of code files using AST for Python
and paragraph-based chunking for Markdown.
"""

import ast
from typing import List, Dict
from pathlib import Path


class CodeChunker:
    """Chunks code files into semantic units.
    
    Uses AST-based chunking for Python (extracts functions/classes)
    and paragraph-based chunking for Markdown files.
    """
    
    def __init__(self, config):
        """Initialize the code chunker.
        
        Args:
            config: Config object with chunking settings
        """
        self.config = config
        self.chunk_size = config.get('chunking', 'chunk_size')
        self.overlap = config.get('chunking', 'overlap')
    
    def chunk_file(self, content: str, file_path: str) -> List[Dict]:
        """Chunk a file based on its type.
        
        Args:
            content: File content as string
            file_path: Path to the file (used to determine type)
            
        Returns:
            List of chunk dictionaries with text, file_path, line numbers, and type
        """
        if file_path.endswith('.py'):
            return self._chunk_python(content, file_path)
        elif file_path.endswith('.md'):
            return self._chunk_markdown(content, file_path)
        return []
    
    def _chunk_python(self, content: str, file_path: str) -> List[Dict]:
        """Extract functions and classes as chunks using AST.
        
        Args:
            content: Python file content
            file_path: Path to the file
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        lines = content.split('\n')
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    start_line = node.lineno
                    end_line = node.end_lineno or start_line
                    
                    chunk_text = '\n'.join(lines[start_line-1:end_line])
                    
                    # Only add if not too large
                    if len(chunk_text) <= self.chunk_size * 1.5:
                        chunks.append({
                            'text': chunk_text,
                            'file_path': file_path,
                            'start_line': start_line,
                            'end_line': end_line,
                            'type': node.__class__.__name__
                        })
                    else:
                        # Split large classes/functions with overlap
                        chunks.extend(self._split_large_chunk(
                            chunk_text, file_path, start_line
                        ))
        
        except SyntaxError:
            # Fallback: split by lines with overlap
            chunks = self._split_large_chunk(content, file_path, 1)
        
        return chunks
    
    def _chunk_markdown(self, content: str, file_path: str) -> List[Dict]:
        """Split markdown by paragraphs with overlap.
        
        Args:
            content: Markdown file content
            file_path: Path to the file
            
        Returns:
            List of chunk dictionaries
        """
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = ""
        start_line = 1
        current_line = 1
        
        for para in paragraphs:
            if current_chunk and len(current_chunk) + len(para) > self.chunk_size:
                chunks.append({
                    'text': current_chunk.strip(),
                    'file_path': file_path,
                    'start_line': start_line,
                    'end_line': current_line,
                    'type': 'markdown'
                })
                # Overlap
                if len(current_chunk) > self.overlap:
                    current_chunk = current_chunk[-self.overlap:] + " " + para
                    start_line = current_line - self.overlap // 20
                else:
                    current_chunk = para
                    start_line = current_line
            else:
                current_chunk += ("\n\n" if current_chunk else "") + para
            
            current_line += para.count('\n') + 2
        
        if current_chunk:
            chunks.append({
                'text': current_chunk.strip(),
                'file_path': file_path,
                'start_line': start_line,
                'end_line': current_line,
                'type': 'markdown'
            })
        
        return chunks
    
    def _split_large_chunk(self, text: str, file_path: str, start_line: int) -> List[Dict]:
        """Split large chunks that exceed size limit.
        
        Args:
            text: Text to split
            file_path: Path to the file
            start_line: Starting line number
            
        Returns:
            List of chunk dictionaries
        """
        # Simple line-based splitting with overlap
        lines = text.split('\n')
        chunks = []
        chunk_lines = self.chunk_size // 50  # Rough estimate
        overlap_lines = self.overlap // 50
        
        for i in range(0, len(lines), chunk_lines - overlap_lines):
            chunk_text = '\n'.join(lines[i:i + chunk_lines])
            if chunk_text.strip():  # Only add non-empty chunks
                chunks.append({
                    'text': chunk_text,
                    'file_path': file_path,
                    'start_line': start_line + i,
                    'end_line': start_line + i + len(chunk_text.split('\n')),
                    'type': 'code_section'
                })
        
        return chunks

"""Repository file loader.

This module handles file discovery and loading from the repository.
"""

import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class RepositoryLoader:
    """Discovers and loads files from a code repository.
    
    Walks the repository directory structure, filters by file extensions,
    and excludes specified directories.
    """
    
    def __init__(self, config):
        """Initialize the repository loader.
        
        Args:
            config: Config object with repository settings
        """
        self.config = config
        self.repo_path = Path(config.get('repository', 'path'))
        self.extensions = config.get('repository', 'file_extensions')
        self.exclude_dirs = config.get('repository', 'exclude_dirs')
    
    def discover_files(self) -> List[Path]:
        """Find all relevant files in the repository.
        
        Returns:
            List of Path objects for discovered files
        """
        files = []
        for root, dirs, filenames in os.walk(self.repo_path):
            # Remove excluded directories from search
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for filename in filenames:
                if any(filename.endswith(ext) for ext in self.extensions):
                    files.append(Path(root) / filename)
        
        logger.info(f"Found {len(files)} files")
        return files
    
    def load_file(self, file_path: Path) -> str:
        """Load file content with error handling.
        
        Args:
            file_path: Path to the file to load
            
        Returns:
            File content as string, or empty string on error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                return ""
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return ""


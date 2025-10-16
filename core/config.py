"""Configuration loader for Repo Analyst.

This module handles loading and validation of the config.yaml file.
"""

import yaml
import os
from pathlib import Path


class Config:
    """Configuration manager for the RAG system.
    
    Loads configuration from config.yaml and validates required settings.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            EnvironmentError: If required environment variables are missing
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self._validate()
    
    def _validate(self):
        """Check required settings and paths.
        
        Raises:
            FileNotFoundError: If repository path doesn't exist
            EnvironmentError: If API key environment variable is not set
        """
        repo_path = Path(self.config['repository']['path'])
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository path not found: {repo_path}")
        
        # Check API key
        api_key_env = self.config['llm']['api_key_env']
        if not os.getenv(api_key_env):
            raise EnvironmentError(f"Missing environment variable: {api_key_env}")
    
    def get(self, *keys, default=None):
        """Get nested config value.
        
        Args:
            *keys: Variable number of keys for nested lookup
            default: Default value if key path not found
            
        Returns:
            Configuration value at the key path, or default if not found
            
        Example:
            config.get('repository', 'path')
            config.get('llm', 'model', default='gpt-4')
        """
        value = self.config
        for key in keys:
            value = value.get(key, {})
        return value if value != {} else default


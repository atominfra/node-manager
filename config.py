import os
from dotenv import dotenv_values

class Config:
    _instance = None
    _loaded = False
    _config_data = {}  # Dictionary to store configuration values

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.load_env_variables()
        return cls._instance

    def load_env_variables(self):
        if not self._loaded:
            # Load environment variables from the .env file
            env_config = dotenv_values(".env")  # Load configuration from .env file

            # Create a configuration dictionary with environment variables overriding .env values
            self._config_data = {
                **env_config,
                **os.environ,  # Override with actual environment variables
            }

            self._loaded = True  # Mark as loaded to prevent reloading

    def get(self, key: str) -> str:
        """Retrieve a configuration value by key."""
        try:
            return self._config_data[key]
        except KeyError:
            raise KeyError(f"Configuration key '{key}' not found.")


# Create a single instance of the Config class
config = Config()
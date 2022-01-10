from copy import deepcopy
import os
from pathlib import Path
import sys
import importlib
from typing import Union

from turboreload import importer
from django.utils import autoreload

logger = autoreload.logger


def reload_module_by_path(path: Union[str, Path]):
    if not isinstance(path, Path):
        path = Path(path)

    path_parts: list[str] = str(path).removesuffix(path.suffix).split(os.path.sep)

    module_path = []
    for path_part in path_parts[::-1]:
        module_path.insert(0, path_part)

        module_name = ".".join(module_path)

        if module_name in sys.modules:
            logger.info(f"Reloading {module_name}")
            updated_module = importlib.reload(sys.modules[module_name])

            sys.modules[module_name] = updated_module
            importer.updated_modules[module_name] = updated_module
            break

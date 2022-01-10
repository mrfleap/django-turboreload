from copy import deepcopy
import inspect
from types import FunctionType, ModuleType
import importhook

import ast
from collections import defaultdict

from turboreload.util import reload_module_by_path

updated_modules = {}


def get_imports_from_file(file_path) -> dict[str, str]:
    imports = defaultdict(list)

    with open(file_path) as f:
        p = ast.parse(f.read())

    for stmt in p.body:
        if isinstance(stmt, ast.ImportFrom):
            module_name = stmt.module

            for alias in stmt.names:
                imports[alias.name] = module_name

    return imports


class UpdatableModule(ModuleType):
    def __init__(self, module, module_name):
        super().__init__(module_name)

        self.module = module
        self.module_name = module_name

    def _updatable_module_get_module(self):
        if self.module_name in updated_modules:
            # print(f"Found {self.module_name} in updated_modules, using that")
            return updated_modules[self.module_name].module

        return self.module

    def __call__(self, *args, **kwargs):
        # if not self.setup:
        #     super().__call__(*args, **kwargs)
        return self._updatable_module_get_module().__call__(*args, **kwargs)

    def __getattr__(self, name):
        if name in ["module", "module_name"]:
            return object.__getattr__(self, name)

        # if not self.setup:
        #     super().__call__(*args, **kwargs)
        attr = getattr(self._updatable_module_get_module(), name)

        if isinstance(attr, FunctionType):
            func = getattr(self._updatable_module_get_module(), name)

            globals_used = func.__code__.co_names
            func_path = inspect.getfile(func)

            imports = get_imports_from_file(func_path)
            modules_used = set()

            for global_var in globals_used:
                if global_var in imports:
                    modules_used.add(imports[global_var])

            initial_deps = {mod_name: mod for mod_name, mod in updated_modules.items() if mod_name in modules_used}

            def updatable_func(*args, **kwargs):
                latest_deps = {mod_name: mod for mod_name, mod in updated_modules.items() if mod_name in modules_used}
                if latest_deps != initial_deps:
                    reload_module_by_path(func_path)

                func = getattr(self._updatable_module_get_module(), name)

                return func(*args, **kwargs)

            return updatable_func

        return attr

    def __setattr__(self, name, val):
        if name in ["module", "module_name"]:
            return object.__setattr__(self, name, val)
        return self._updatable_module_get_module().__setattr__(name, val)

    @property
    def __spec__(self):
        return self._updatable_module_get_module().__spec__

    @property
    def __file__(self):
        return self._updatable_module_get_module().__file__

    @property
    def __name__(self):
        return self._updatable_module_get_module().__name__

    @property
    def __cached__(self):
        return self._updatable_module_get_module().__cached__

    @property
    def __original_module__(self):
        return self.__updatable_module_get_module().__original_module__

    @property
    def __package__(self):
        return self.__updatable_module_get_module().__package__

    @property
    def __reset_module__(self):
        return self._updatable_module_get_module().__reset_module__


@importhook.on_import(importhook.ANY_MODULE)
def on_any_import(module):
    return UpdatableModule(importhook.copy_module(module), module.__name__)


# def install():
#     """Inserts the finder into the import machinery"""
#     # sys.meta_path.insert(0, MyMetaFinder())
#     print("Custom importer installed")

from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import threading
from django.utils import autoreload
import logging
import sys
import importlib
import inspect


logger = autoreload.logger


def reload_module_by_path(path: Path):
    # module_name = inspect.getmodulename(path)
    path_parts: list[str] = str(path).removesuffix(path.suffix).split(os.path.sep)

    module_path = []
    for path_part in path_parts[::-1]:
        module_path.insert(0, path_part)

        module_name = ".".join(module_path)

        logger.info(f"Checking {module_name}")
        if module_name in sys.modules:
            logger.info(f"Reloading {module_name}")
            sys.modules[module_name] = importlib.reload(sys.modules[module_name])
            return


class TurboreloadException(Exception):
    pass


class BaseTurboReloader:
    def notify_file_changed(self, path):
        results = autoreload.file_changed.send(sender=self, file_path=path)
        logger.debug("%s notified as changed. Signal results: %s.", path, results)
        if not any(res[1] for res in results):
            logger.info("%s changed, reloading.", path)
            reload_module_by_path(path)
            raise TurboreloadException()


class WatchmanReloader(BaseTurboReloader, autoreload.WatchmanReloader):
    pass


class StatReloader(BaseTurboReloader, autoreload.StatReloader):
    pass


def get_reloader():
    """Return the most suitable reloader for this environment."""
    try:
        WatchmanReloader.check_availability()
    except autoreload.WatchmanUnavailable:
        return StatReloader()
    return WatchmanReloader()


def run_with_reloader(main_func, *args, **kwargs):
    reloader = get_reloader()

    while True:
        try:
            start_django(reloader, main_func, *args, **kwargs)
        except KeyboardInterrupt:
            break


def start_django(reloader, main_func, *args, **kwargs):
    autoreload.ensure_echo_on()

    main_func = autoreload.check_errors(main_func)
    django_main_thread = multiprocessing.Process(target=main_func, args=args, kwargs=kwargs, name="django-main-thread")
    django_main_thread.daemon = True
    django_main_thread.start()

    while not reloader.should_stop:
        try:
            reloader.run(django_main_thread)
        except autoreload.WatchmanUnavailable as ex:
            # It's possible that the watchman service shuts down or otherwise
            # becomes unavailable. In that case, use the StatReloader.
            reloader = autoreload.StatReloader()
            logger.error("Error connecting to Watchman: %s", ex)
            logger.info("Watching for file changes with %s", reloader.__class__.__name__)
        except TurboreloadException:
            django_main_thread.kill()
            break

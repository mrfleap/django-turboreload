from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import threading
import weakref
from django.utils import autoreload
import logging
import sys
import importlib
import inspect

from turboreload import importer
from turboreload.util import reload_module_by_path


logger = autoreload.logger


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

    def watched_files(self, include_globs=True):
        """
        Yield all files that need to be watched, including module files and
        files within globs.
        """
        yield from iter_all_python_module_files()
        yield from self.extra_files
        if include_globs:
            for directory, patterns in self.directory_globs.items():
                for pattern in patterns:
                    yield from directory.glob(pattern)


modules_and_files = frozenset()


def iter_all_python_module_files():
    # This is a hot path during reloading. Create a stable sorted list of
    # modules based on the module name and pass it to iter_modules_and_files().
    # This ensures cached results are returned in the usual case that modules
    # aren't loaded on the fly.
    global modules_and_files

    keys = sorted(sys.modules)
    modules = tuple(m for m in map(sys.modules.__getitem__, keys) if not isinstance(m, weakref.ProxyTypes))
    modules_and_files |= autoreload.iter_modules_and_files(modules, frozenset(autoreload._error_files))

    return modules_and_files


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
    # importer.install()
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

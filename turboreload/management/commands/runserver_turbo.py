from django.core.management.commands import runserver
from django.core.management.base import BaseCommand, CommandError
from turboreload import turboreload


class Command(runserver.Command):
    help = "Runs the Django server with turboreloading capabilities"

    # def add_arguments(self, parser):
    #     parser.add_argument('', nargs='+', type=int)

    def handle(self, *args, **options):
        print("handle")
        super().handle(*args, **options)

    def run(self, **options):
        """Run the server, using the autoreloader if needed."""
        use_reloader = options["use_reloader"]

        if use_reloader:
            turboreload.run_with_reloader(self.inner_run, **options)
        else:
            self.inner_run(None, **options)

import multiprocessing as mp
import os
from typing import Any

import click

from lightning_app.core.api import start_server
from lightning_app.core.queues import QueuingSystem
from lightning_app.runners.runtime import Runtime
from lightning_app.utilities.app_helpers import _is_headless
from lightning_app.utilities.load_app import extract_metadata_from_app


class SingleProcessRuntime(Runtime):
    """Runtime to launch the LightningApp into a single process."""

    def __post_init__(self):
        pass

    def dispatch(self, *args, open_ui: bool = True, **kwargs: Any):
        """Method to dispatch and run the LightningApp."""
        queue = QueuingSystem.SINGLEPROCESS

        self.app.delta_queue = queue.get_delta_queue()
        self.app.state_update_queue = queue.get_caller_queue(work_name="single_worker")
        self.app.error_queue = queue.get_error_queue()

        if self.start_server:
            self.app.should_publish_changes_to_api = True
            self.app.api_publish_state_queue = QueuingSystem.MULTIPROCESS.get_api_state_publish_queue()
            self.app.api_delta_queue = QueuingSystem.MULTIPROCESS.get_api_delta_queue()
            has_started_queue = QueuingSystem.MULTIPROCESS.get_has_server_started_queue()
            kwargs = dict(
                host=self.host,
                port=self.port,
                api_publish_state_queue=self.app.api_publish_state_queue,
                api_delta_queue=self.app.api_delta_queue,
                has_started_queue=has_started_queue,
                spec=extract_metadata_from_app(self.app),
                root_path=self.app.root_path,
            )
            server_proc = mp.Process(target=start_server, kwargs=kwargs)
            self.processes["server"] = server_proc
            server_proc.start()

            # wait for server to be ready.
            has_started_queue.get()

        if open_ui and not _is_headless(self.app):
            click.launch(self._get_app_url())

        try:
            self.app._run()
        except KeyboardInterrupt:
            self.terminate()
            raise
        finally:
            self.terminate()

    @staticmethod
    def _get_app_url() -> str:
        return os.getenv("APP_SERVER_HOST", "http://127.0.0.1:7501/view")

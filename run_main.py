# run_main.py

from fastapi import FastAPI
from gunicorn.app.base import BaseApplication

from config import settings
from main import app as main_app


class Application(BaseApplication):
    def __init__(
        self, 
        app: FastAPI, 
        options: dict,
        ):
        self.options = options
        self.application = app
        super().__init__()
    
    def load(self):
        return self.application
    
    @property
    def config_options(self) -> dict:
        return {
            # pair
            k: v
            # For each option 
            for k, v in self.options.items()
            # If the option is in the settings and value is not None
            if k in self.cfg.settings and v is not None
        }
    
    def load_config(self) -> dict:
        for key, value in self.config_options.items():
            if key in self.cfg.settings:
                self.cfg.set(key.lower(), value)


def get_app_options(
    host: str = settings.run.host,
    port: int = settings.run.port,
    workers: int = settings.run.workers,
    timeout: int = settings.run.timeout,
    ) -> dict:
    return {
        "bind": f"{host}:{port}",
        "workers": workers,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": timeout,
    }


def main():
    app = Application(
        app=main_app,
        options=get_app_options()
    )
    
    app.run()


if __name__ == "__main__":
    main()

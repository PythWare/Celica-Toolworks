__all__ = ["run_app"]

def run_app():
    from .gui import run_app as launch

    return launch()

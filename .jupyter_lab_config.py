# pylint: disable
from pathlib import Path

c.JupyterLabTemplates.template_dirs = [
    str((Path.cwd() / "notebooks/tmpl").absolute())
]
c.JupyterLabTemplates.include_default = False
c.JupyterLabTemplates.include_core_paths = False

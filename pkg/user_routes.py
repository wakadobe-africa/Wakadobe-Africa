"""Compatibility module.

Routes were split into dedicated modules to keep reader and admin concerns orthogonal.
Importing this module still registers all routes as before.
"""

from pkg import admin_routes  # noqa: F401
from pkg import core_routes  # noqa: F401
from pkg import reader_routes  # noqa: F401

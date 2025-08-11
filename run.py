import os
import sys

if getattr(sys, "frozen", False):
    root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    root = os.path.abspath(os.path.dirname(__file__))

if root not in sys.path:
    sys.path.insert(0, root)

from pyile.bootstrap.build import bootstrap
if not bootstrap():
    print("Bootstrap failed. Pyile can not start.")
    print("Check log file at `pyile/bootstrap/bootstrap.log`")
    sys.exit(1)

from pyile.lib.ui.gui.interface import Interface
interface = Interface()
interface.mainloop()


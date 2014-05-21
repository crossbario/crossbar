from pprint import pprint

from crossbar.worker.reloader import TrackingModuleReloader

r = TrackingModuleReloader(silence = True)
#pprint(r._module_mtimes)

from foobar import getfoo

print getfoo()

print r.reload()

print getfoo()

print r.reload()

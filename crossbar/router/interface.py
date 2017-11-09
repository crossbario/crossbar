from txaio import make_logger


class RouterInterface(object):
    log = make_logger()

    def __init__(self, router, uri):
        self.router = router
        self.uri = uri

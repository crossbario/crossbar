from autobahn.twisted.util import sleep


def setup_auth(session, details):
    def register(_):
        def authenticate(*args, **kw):
            print("test.authenticate: {} {}".format(args, kw))
            return {
                "allow": False,
                "role": "role0",
                # corresponds to a private-key of all "a"s
                "pubkey": "e734ea6c2b6257de72355e472aa05a4c487e6b463c029ed306df2f01b5636b58",
            }

        reg = session.register(authenticate, u"test.authenticate")
        print("registered: {}\n\n\n".format(reg))
        return reg

    # we wait here to simulate slow startup of the authenticator
    d = sleep(5)
    d.addCallback(register)
    return d

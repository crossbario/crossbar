if __name__ == '__main__':
    from pkg_resources import load_entry_point
    import sys

    sys.exit(
        load_entry_point('crossbar', 'console_scripts', 'crossbar')()
    )

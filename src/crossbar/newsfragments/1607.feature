Added container shutdown and restart modes, and got rid of a
special-case for controller shutdown (if any container-component
failed in the first two seconds, the node would shutdown). Use
shutdown trigger `shutdown_on_worker_exit_with_error' along with
container shutdown option `shutdown-on-any-component-failed` to
maintain similar behavior.
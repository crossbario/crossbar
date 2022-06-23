###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ('RemoteDockerApi', )


class RemoteDockerApi(RemoteApi):
    # yapf: disable
    PREFIX = u'crossbarfabriccenter.remote.docker.'

    PROCS = {
        # these are node level procedures
        u'node': [
            (u'get_info', u'get_docker_info'),
            (u'get_ping', u'get_docker_ping'),
            (u'get_version', u'get_docker_version'),
            (u'get_df', u'get_docker_df'),
            (u'get_containers', u'get_docker_containers'),
            (u'get_container', u'get_docker_container'),
            (u'get_images', u'get_docker_images'),
            (u'get_image', u'get_docker_image'),

            (u'fs_open', u'fs_docker_open'),
            (u'fs_get', u'fs_docker_get'),
            (u'fs_put', u'fs_docker_put'),

            (u'create', u'create_docker_container'),
            (u'start', u'start_docker_container'),
            (u'stop', u'stop_docker_container'),
            (u'restart', u'restart_docker_container'),
            (u'pause', u'pause_docker_container'),
            (u'unpause', u'unpause_docker_container'),
            (u'destroy', u'destroy_docker_container'),

            (u'delete_image', u'delete_docker_image'),
            (u'prune_images', u'prune_docker_images'),

            (u'request_tty', u'request_docker_tty'),

            (u'watch', u'watch_docker_container'),
            (u'shell', u'shell_docker_container'),
            (u'backlog', u'backlog_docker_container'),
            (u'keystroke', u'keystroke_docker_container')
        ],
    }

    EVENTS = {
        # these are node level topics
        u'node': [
            u'on_container_create',
            u'on_container_start',
            u'on_container_attach',
            u'on_container_commit',
            u'on_container_kill',
            u'on_container_die',
            u'on_container_stop',
            u'on_container_destroy',
            u'on_container_pause',
            u'on_container_unpause',
            u'on_image_untag',
            u'on_image_delete',
            u'on_image_pull',
            u'on_image_tag',
            u'on_docker_image_update_started',
            u'on_docker_image_update_progress',
            u'on_docker_image_update_finished',
            u'on_docker_image_remove_started',
            u'on_docker_image_remove_progress',
            u'on_docker_image_remove_finished',
        ],
    }

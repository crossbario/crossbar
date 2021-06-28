#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json

from twisted.internet.defer import inlineCallbacks

from crossbar.test import TestCase
from crossbar._logging import LogCapturer
from crossbar.bridge.rest import WebhookResource
from crossbar.bridge.rest.test import MockPublisherSession, renderResource

github_test_token = b"whatever"
github_request_data = b"""payload=%7B%22zen%22%3A%22Approachable+is+better+than+simple.%22%2C%22hook_id%22%3A50271743%2C%22hook%22%3A%7B%22type%22%3A%22Repository%22%2C%22id%22%3A50271743%2C%22name%22%3A%22web%22%2C%22active%22%3Atrue%2C%22events%22%3A%5B%22%2A%22%5D%2C%22config%22%3A%7B%22content_type%22%3A%22form%22%2C%22insecure_ssl%22%3A%220%22%2C%22secret%22%3A%22%2A%2A%2A%2A%2A%2A%2A%2A%22%2C%22url%22%3A%22https%3A%2F%2Fthula.meejah.ca%2Fwebhook%2Fgithub%22%7D%2C%22updated_at%22%3A%222018-09-12T21%3A33%3A06Z%22%2C%22created_at%22%3A%222018-09-12T21%3A33%3A06Z%22%2C%22url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fhooks%2F50271743%22%2C%22test_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fhooks%2F50271743%2Ftest%22%2C%22ping_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fhooks%2F50271743%2Fpings%22%2C%22last_response%22%3A%7B%22code%22%3Anull%2C%22status%22%3A%22unused%22%2C%22message%22%3Anull%7D%7D%2C%22repository%22%3A%7B%22id%22%3A30720845%2C%22node_id%22%3A%22MDEwOlJlcG9zaXRvcnkzMDcyMDg0NQ%3D%3D%22%2C%22name%22%3A%22AutobahnPython%22%2C%22full_name%22%3A%22meejah%2FAutobahnPython%22%2C%22owner%22%3A%7B%22login%22%3A%22meejah%22%2C%22id%22%3A145599%2C%22node_id%22%3A%22MDQ6VXNlcjE0NTU5OQ%3D%3D%22%2C%22avatar_url%22%3A%22https%3A%2F%2Favatars3.githubusercontent.com%2Fu%2F145599%3Fv%3D4%22%2C%22gravatar_id%22%3A%22%22%2C%22url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%22%2C%22html_url%22%3A%22https%3A%2F%2Fgithub.com%2Fmeejah%22%2C%22followers_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Ffollowers%22%2C%22following_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Ffollowing%7B%2Fother_user%7D%22%2C%22gists_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fgists%7B%2Fgist_id%7D%22%2C%22starred_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fstarred%7B%2Fowner%7D%7B%2Frepo%7D%22%2C%22subscriptions_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fsubscriptions%22%2C%22organizations_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Forgs%22%2C%22repos_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Frepos%22%2C%22events_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fevents%7B%2Fprivacy%7D%22%2C%22received_events_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Freceived_events%22%2C%22type%22%3A%22User%22%2C%22site_admin%22%3Afalse%7D%2C%22private%22%3Afalse%2C%22html_url%22%3A%22https%3A%2F%2Fgithub.com%2Fmeejah%2FAutobahnPython%22%2C%22description%22%3A%22WebSocket+%26+WAMP+for+Python+on+Twisted+and+asyncio%22%2C%22fork%22%3Atrue%2C%22url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%22%2C%22forks_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fforks%22%2C%22keys_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fkeys%7B%2Fkey_id%7D%22%2C%22collaborators_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fcollaborators%7B%2Fcollaborator%7D%22%2C%22teams_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fteams%22%2C%22hooks_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fhooks%22%2C%22issue_events_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fissues%2Fevents%7B%2Fnumber%7D%22%2C%22events_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fevents%22%2C%22assignees_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fassignees%7B%2Fuser%7D%22%2C%22branches_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fbranches%7B%2Fbranch%7D%22%2C%22tags_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Ftags%22%2C%22blobs_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fgit%2Fblobs%7B%2Fsha%7D%22%2C%22git_tags_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fgit%2Ftags%7B%2Fsha%7D%22%2C%22git_refs_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fgit%2Frefs%7B%2Fsha%7D%22%2C%22trees_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fgit%2Ftrees%7B%2Fsha%7D%22%2C%22statuses_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fstatuses%2F%7Bsha%7D%22%2C%22languages_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Flanguages%22%2C%22stargazers_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fstargazers%22%2C%22contributors_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fcontributors%22%2C%22subscribers_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fsubscribers%22%2C%22subscription_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fsubscription%22%2C%22commits_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fcommits%7B%2Fsha%7D%22%2C%22git_commits_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fgit%2Fcommits%7B%2Fsha%7D%22%2C%22comments_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fcomments%7B%2Fnumber%7D%22%2C%22issue_comment_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fissues%2Fcomments%7B%2Fnumber%7D%22%2C%22contents_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fcontents%2F%7B%2Bpath%7D%22%2C%22compare_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fcompare%2F%7Bbase%7D...%7Bhead%7D%22%2C%22merges_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fmerges%22%2C%22archive_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2F%7Barchive_format%7D%7B%2Fref%7D%22%2C%22downloads_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fdownloads%22%2C%22issues_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fissues%7B%2Fnumber%7D%22%2C%22pulls_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fpulls%7B%2Fnumber%7D%22%2C%22milestones_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fmilestones%7B%2Fnumber%7D%22%2C%22notifications_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fnotifications%7B%3Fsince%2Call%2Cparticipating%7D%22%2C%22labels_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Flabels%7B%2Fname%7D%22%2C%22releases_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Freleases%7B%2Fid%7D%22%2C%22deployments_url%22%3A%22https%3A%2F%2Fapi.github.com%2Frepos%2Fmeejah%2FAutobahnPython%2Fdeployments%22%2C%22created_at%22%3A%222015-02-12T19%3A58%3A50Z%22%2C%22updated_at%22%3A%222016-02-03T23%3A20%3A21Z%22%2C%22pushed_at%22%3A%222018-09-06T04%3A39%3A18Z%22%2C%22git_url%22%3A%22git%3A%2F%2Fgithub.com%2Fmeejah%2FAutobahnPython.git%22%2C%22ssh_url%22%3A%22git%40github.com%3Ameejah%2FAutobahnPython.git%22%2C%22clone_url%22%3A%22https%3A%2F%2Fgithub.com%2Fmeejah%2FAutobahnPython.git%22%2C%22svn_url%22%3A%22https%3A%2F%2Fgithub.com%2Fmeejah%2FAutobahnPython%22%2C%22homepage%22%3A%22http%3A%2F%2Fautobahn.ws%2Fpython%22%2C%22size%22%3A12914%2C%22stargazers_count%22%3A0%2C%22watchers_count%22%3A0%2C%22language%22%3A%22Python%22%2C%22has_issues%22%3Afalse%2C%22has_projects%22%3Atrue%2C%22has_downloads%22%3Atrue%2C%22has_wiki%22%3Atrue%2C%22has_pages%22%3Afalse%2C%22forks_count%22%3A0%2C%22mirror_url%22%3Anull%2C%22archived%22%3Afalse%2C%22open_issues_count%22%3A0%2C%22license%22%3A%7B%22key%22%3A%22mit%22%2C%22name%22%3A%22MIT+License%22%2C%22spdx_id%22%3A%22MIT%22%2C%22url%22%3A%22https%3A%2F%2Fapi.github.com%2Flicenses%2Fmit%22%2C%22node_id%22%3A%22MDc6TGljZW5zZTEz%22%7D%2C%22forks%22%3A0%2C%22open_issues%22%3A0%2C%22watchers%22%3A0%2C%22default_branch%22%3A%22master%22%7D%2C%22sender%22%3A%7B%22login%22%3A%22meejah%22%2C%22id%22%3A145599%2C%22node_id%22%3A%22MDQ6VXNlcjE0NTU5OQ%3D%3D%22%2C%22avatar_url%22%3A%22https%3A%2F%2Favatars3.githubusercontent.com%2Fu%2F145599%3Fv%3D4%22%2C%22gravatar_id%22%3A%22%22%2C%22url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%22%2C%22html_url%22%3A%22https%3A%2F%2Fgithub.com%2Fmeejah%22%2C%22followers_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Ffollowers%22%2C%22following_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Ffollowing%7B%2Fother_user%7D%22%2C%22gists_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fgists%7B%2Fgist_id%7D%22%2C%22starred_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fstarred%7B%2Fowner%7D%7B%2Frepo%7D%22%2C%22subscriptions_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fsubscriptions%22%2C%22organizations_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Forgs%22%2C%22repos_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Frepos%22%2C%22events_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Fevents%7B%2Fprivacy%7D%22%2C%22received_events_url%22%3A%22https%3A%2F%2Fapi.github.com%2Fusers%2Fmeejah%2Freceived_events%22%2C%22type%22%3A%22User%22%2C%22site_admin%22%3Afalse%7D%7D"""


class WebhookTestCase(TestCase):
    """
    Unit tests for L{WebhookResource}.
    """
    @inlineCallbacks
    def test_basic(self):
        """
        A message, when a request has gone through to it, publishes a WAMP
        message on the configured topic.
        """
        session = MockPublisherSession(self)
        resource = WebhookResource({"topic": "com.test.webhook"}, session)

        with LogCapturer() as l:
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": []},
                                           body=b'{"foo": "has happened"}')

        self.assertEqual(len(session._published_messages), 1)
        self.assertEqual(
            {
                "body": '{"foo": "has happened"}',
                "headers": {
                    "Content-Type": [],
                    'Date': ['Sun, 1 Jan 2013 15:21:01 GMT'],
                    'Host': ['localhost:8000']
                }
            }, session._published_messages[0]["args"][0])

        self.assertEqual(request.code, 202)
        self.assertEqual(request.get_written_data(), b"OK")

        logs = l.get_category("AR201")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 202)

    @inlineCallbacks
    def test_github_signature_fail(self):
        """
        Error if we're to check github signatures, but they're missing entirely
        """
        session = MockPublisherSession(self)
        resource = WebhookResource(
            options={
                "topic": "com.test.webhook",
                "github_secret": "deadbeef",
            },
            session=session,
        )

        request = yield renderResource(resource,
                                       b"/",
                                       method=b"POST",
                                       headers={b"Content-Type": []},
                                       body=b'{"foo": "has happened"}')

        self.assertEqual(len(session._published_messages), 0)
        self.assertEqual(request.code, 400)
        received_json = json.loads(request.get_written_data().decode('utf8'))
        self.assertEqual(received_json, {"error": "Malformed request to the REST bridge.", "args": [], "kwargs": {}})

    @inlineCallbacks
    def test_github_signature_invalid(self):
        """
        A correctly-formatted GitHub signature, but it's invalid
        """
        session = MockPublisherSession(self)
        resource = WebhookResource(
            options={
                "topic": "com.test.webhook",
                "github_secret": "deadbeef",
            },
            session=session,
        )

        request = yield renderResource(resource,
                                       b"/",
                                       method=b"POST",
                                       headers={b"Content-Type": []},
                                       body=b'{"foo": "has happened"}')

        self.assertEqual(len(session._published_messages), 0)
        self.assertEqual(request.code, 400)
        received_json = json.loads(request.get_written_data().decode('utf8'))
        self.assertEqual(received_json, {
            "error": "Malformed request to the REST bridge.",
            "args": [],
            "kwargs": {},
        })

    @inlineCallbacks
    def test_github_signature_valid(self):
        """
        A correctly-formatted GitHub signature
        """
        session = MockPublisherSession(self)
        resource = WebhookResource(
            options={
                "topic": "com.test.webhook",
                "github_secret": github_test_token,
            },
            session=session,
        )

        yield renderResource(
            resource,
            b"/webhook",
            method=b"POST",
            headers={
                b"Content-Type": [],
                b"X-Hub-Signature": [b"sha1=5054d1d2e6f5d293fbea8fdeed5117f2854ccf7a"],
            },
            body=github_request_data,
        )

        self.assertEqual(len(session._published_messages), 1)
        msg = session._published_messages[0]
        data = msg['args'][0]
        self.assertEqual(
            data['body'].encode('utf8'),
            github_request_data.strip(),
        )

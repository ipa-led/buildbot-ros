#!/usr/bin/env python

# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

# This is the gitpoller adapted for use with pull requests.
# Extraneous code has been removed (e.g. commit-related methods).
# A modification has been added using name to allow for multiple instances.



from twisted.internet import defer

from buildbot.changes import base, github
from buildbot.util import bytes2unicode
from buildbot.util import httpclientservice


class GitPRPoller(github.GitHubPullrequestPoller):
    """This source will poll a remote git repo for pull requests
    and submit changes for the PR's branches to the change master."""
    secrets = ("sshPrivateKey", "sshHostKey", "OathToken")

    @defer.inlineCallbacks
    def reconfigService(self,
                        owner,
                        repo,
                        branches=None,
                        pollInterval=10 * 60,
                        category=None,
                        baseURL=None,
                        pullrequest_filter=True,
                        token=None,
                        pollAtLaunch=False,
                        magic_link=False,
                        repository_type="https",
                        github_property_whitelist=None,
                        **kwargs):
        yield base.ReconfigurablePollingChangeSource.reconfigService(
            self, name=self.name, **kwargs)

        if baseURL is None:
            baseURL = github.HOSTED_BASE_URL
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]

        http_headers = {'User-Agent': 'Buildbot'}
        self.token = None
        if token is not None:
            self.token = yield self.renderSecrets(token)
            http_headers.update({'Authorization': 'token ' + self.token})

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, baseURL, headers=http_headers)

        self.owner = owner
        self.repo = repo
        self.branches = branches
        self.github_property_whitelist = github_property_whitelist
        self.pollInterval = pollInterval
        self.pollAtLaunch = pollAtLaunch
        self.repository_type = github.link_urls[repository_type]
        self.magic_link = magic_link

        if github_property_whitelist is None:
            self.github_property_whitelist = []

        if callable(pullrequest_filter):
            self.pullrequest_filter = pullrequest_filter
        else:
            self.pullrequest_filter = (lambda _: pullrequest_filter)

        self.category = category if callable(category) else bytes2unicode(
        category)
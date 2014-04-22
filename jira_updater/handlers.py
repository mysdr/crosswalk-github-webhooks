# Copyright (c) 2014 Intel Corporation. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Responds to the "pull_request_changed" event signal and updates JIRA
based on the PR description.

If the PR was opened, its body is scanned for references to JIRA issue
ids or URLs. For each one that is mentioned, a comment is added to the issue
in JIRA referencing the PR in Github.

If the PR was closed, each issue mentioned in the following form will be
resolved:

BUG=<any text>ISSUE-1

with typical examples being:

BUG=ISSUE-1
BUG=http://jira.server/browse/ISSUE-1
"""

import logging
import re

from django.conf import settings
from django.dispatch import receiver
from jirahelper import JiraHelper

from github_webhooks.signals import pull_request_changed


def search_issues(pr_body):
    """
    Parse the PR body searching for issue IDs and return a list
    of issues in the form:
    {
        'id': <issue id>,
        'resolve': <True if the comment indicates that
           the issue is fixed by this PR>
    }
    """
    issues = {}
    regexp = re.compile(r'(%s-\d+)' % settings.JIRA_PROJECT)
    for line in pr_body.splitlines():
        for issue in regexp.findall(line):
            should_resolve = line.startswith('BUG=')
            issues[issue] = {'id': issue, 'resolve': should_resolve}
    # Create a list with the values in the dict.
    flattened_issues = [v for v in issues.values()]
    return flattened_issues


@receiver(pull_request_changed)
def handle_pull_request(sender, **kwargs):
    payload = kwargs['payload']
    pr_body = payload['pull_request']['body']
    pr_action = payload['action']

    # This happens when a pull request only has a title and no message body.
    if pr_body is None:
        logging.info('Pull request %d has an empty body. Skipping.')
        return

    jira = JiraHelper()
    for issue in search_issues(pr_body):
        if pr_action == 'opened':
            jira.comment_issue(issue['id'], payload)
            logging.debug('Commented on issue %s' % issue['id'])
        elif pr_action == 'closed' and\
                payload['pull_request']['merged'] and\
                issue['resolve']:
            jira.resolve_issue(issue['id'], payload)
            logging.debug('Resolved issue %s' % issue['id'])
        else:
            logging.debug('Nothing to do with issue %s' %
                          issue['id'])

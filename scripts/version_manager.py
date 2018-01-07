#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file was part of lago project.
# This file was part of INSPIRE-SCHEMAS.
# This file is part of python-foreman.
# Copyright (C) 2014 Red Hat, Inc.
# Copyright (C) 2016 CERN.
#
# INSPIRE-SCHEMAS is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# INSPIRE-SCHEMAS is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE-SCHEMAS; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""
Script to generate the version, changelog and releasenotes from the git
repository.
"""
from __future__ import print_function

import argparse
import copy
import os
import re
import sys
from collections import OrderedDict, defaultdict

import dulwich.repo
import dulwich.walk

PROJECT_NAME = 'inspire-schemas'
BUG_URL_REG = re.compile(
    r'.*(closes #|fixes #|adresses #)(?P<bugid>\d+)'
)
BUGTRACKER_URL = 'http://github.com/inspirehep/' + PROJECT_NAME
VALID_TAG = re.compile(r'^\d+\.\d+(\.\d+)?$')
FEAT_HEADER = re.compile(
    r'\nsem-ver:\s*.*(feature|deprecat).*\n',
    flags=re.IGNORECASE,
)
FEAT_INVENIO = re.compile(r'\n\* NEW')
MAJOR_HEADER = re.compile(r'\nsem-ver:\s*.*break.*\n', flags=re.IGNORECASE)
MAJOR_INVENIO = re.compile(r'\n\* INCOMPATIBLE')


def get_repo_object(repo, object_name):
    try:
        object_name = object_name.encode()
    except Exception:
        pass

    return repo.get_object(object_name)


def fit_to_cols(what, indent, cols=79):
    lines = []
    free_cols = cols - len(indent)
    while len(what) > free_cols and ' ' in what.lstrip():
        cutpoint = free_cols
        extra_indent = ''
        if what[free_cols] != ' ':
            try:
                prev_space = what[:free_cols].rindex(' ')
                lines.append(indent + what[:prev_space])
                cutpoint = prev_space + 1
                extra_indent = '          '
            except ValueError:
                lines.append(indent + what[:free_cols] + '-')
        else:
            lines.append(indent + what[:free_cols])
        what = extra_indent + what[cutpoint:]
    lines.append(indent + what)
    return '\n'.join(lines)


def get_github_from_commit_msg(commit_msg):
    bugs = []
    for line in commit_msg.split(b'\n'):
        match = BUG_URL_REG.match(line.decode('utf-8'))
        if match:
            bugs.append(match.groupdict()['bugid'])
    return ' '.join(bugs)


def pretty_commit(commit, version=None, commit_type='bug'):
    message = commit.message.decode('utf-8')  # noqa
    subject = commit.message.split(b'\n', 1)[0]  # noqa
    short_hash = commit.sha().hexdigest()[:8]  # noqa
    author = commit.author  # noqa
    bugs = get_github_from_commit_msg(commit.message)
    if bugs:
        bugtracker_url = BUGTRACKER_URL + '/issue/'  # noqa
        changelog_bugs = fit_to_cols(
            'FIXED ISSUES: {bugtracker_url}{bugs}'.format(**vars()),
            indent='    ',
        ) + '\n'
    else:
        changelog_bugs = ''  # noqa

    feature_header = ''
    if commit_type == 'feature':
        feature_header = 'FEATURE'
    elif commit_type == 'api_break':
        feature_header = 'MAJOR'
    else:
        feature_header = 'MINOR'  # noqa

    changelog_message = fit_to_cols(  # noqa
        '{feature_header} {short_hash}: {subject}'.format(**vars()),
        indent='    ',
    )

    return (
        (
            '* {version} "{author}"\n'
            if version is not None else ''
        ) + '{changelog_message}\n' + '{changelog_bugs}'
    ).format(**vars())


def get_tags(repo):
    return {
        commit: os.path.basename(tag_ref)
        for tag_ref, commit in repo.get_refs().items()
        if tag_ref.startswith(b'refs/tags/') and VALID_TAG.match(
            tag_ref[len('refs/tags/'):].decode()
        )
    }


def get_refs(repo):
    refs = defaultdict(set)
    for ref, commit in repo.get_refs().items():
        refs[commit].add(commit)
        refs[commit].add(ref)
    return refs


def fuzzy_matches_ref(fuzzy_ref, ref):
    cur_section = ''
    for path_section in reversed(ref.split(b'/')):
        cur_section = os.path.normpath(os.path.join(path_section, cur_section))
        if fuzzy_ref == cur_section:
            return True
    return False


def fuzzy_matches_refs(fuzzy_ref, refs):
    return any(fuzzy_matches_ref(fuzzy_ref, ref) for ref in refs)


def get_children_per_parent(repo_path):
    repo = dulwich.repo.Repo(repo_path)
    children_per_parent = defaultdict(set)

    for entry in repo.get_walker(order=dulwich.walk.ORDER_TOPO):
        for parent in entry.commit.parents:
            children_per_parent[parent].add(entry.commit.sha().hexdigest())

    return children_per_parent


def get_first_parents(repo_path):
    repo = dulwich.repo.Repo(repo_path)
    #: these are the commits that are parents of more than one other commit
    first_parents = []
    on_merge = False

    for entry in repo.get_walker(order=dulwich.walk.ORDER_TOPO):
        commit = entry.commit
        # In order to properly work on python 2 and 3 we need some utf magic
        parents = commit.parents and [i.decode('utf-8') for i in
                                      commit.parents]
        if not parents:
            if commit.sha().hexdigest() not in first_parents:
                first_parents.append(commit.sha().hexdigest())
        elif len(parents) == 1 and not on_merge:
            if commit.sha().hexdigest() not in first_parents:
                first_parents.append(commit.sha().hexdigest())
            if parents[0] not in first_parents:
                first_parents.append(parents[0])
        elif len(parents) > 1 and not on_merge:
            on_merge = True
            if commit.sha().hexdigest() not in first_parents:
                first_parents.append(commit.sha().hexdigest())
            if parents[0] not in first_parents:
                first_parents.append(parents[0])
        elif parents and commit.sha().hexdigest() in first_parents:
            if parents[0] not in first_parents:
                first_parents.append(parents[0])

    return first_parents


def has_firstparent_child(sha, first_parents, parents_per_child):
    return any(
        child for child in parents_per_child[sha] if child in first_parents
    )


def get_merged_commits(repo, commit, first_parents, children_per_parent):
    merge_children = set()

    to_explore = set([commit.sha().hexdigest()])

    while to_explore:
        next_sha = to_explore.pop()
        next_commit = get_repo_object(repo, next_sha)
        if (
            next_sha not in first_parents and not has_firstparent_child(
                next_sha, first_parents, children_per_parent
            ) or next_sha in commit.parents
        ):
            merge_children.add(next_sha)

        non_first_parents = (
            parent
            for parent in next_commit.parents if parent not in first_parents
        )
        for child_sha in non_first_parents:
            if child_sha not in merge_children and child_sha != next_sha:
                to_explore.add(child_sha)

    return merge_children


def get_children_per_first_parent(repo_path):
    repo = dulwich.repo.Repo(repo_path)
    first_parents = get_first_parents(repo_path)
    children_per_parent = get_children_per_parent(repo_path)
    children_per_first_parent = OrderedDict()

    for first_parent in first_parents:
        commit = get_repo_object(repo, first_parent)
        if len(commit.parents) > 1:
            children = get_merged_commits(
                repo=repo,
                commit=commit,
                first_parents=first_parents,
                children_per_parent=children_per_parent,
            )
        else:
            children = set()

        children_per_first_parent[first_parent] = [
            get_repo_object(repo, child) for child in children
        ]

    return children_per_first_parent


def get_version(commit, tags, maj_version=0, feat_version=0, fix_version=0,
                children=None):
    children = children or []
    commit_type = get_commit_type(commit, children)
    commit_sha = commit.sha().hexdigest().encode('utf-8')

    if commit_sha in tags:
        maj_version, feat_version = tags[commit_sha].split(b'.')[:2]
        maj_version = int(maj_version)
        feat_version = int(feat_version)
        fix_version = 0
    elif commit_type == 'api_break':
        maj_version += 1
        feat_version = 0
        fix_version = 0
    elif commit_type == 'feature':
        feat_version += 1
        fix_version = 0
    else:
        fix_version += 1

    version = (maj_version, feat_version, fix_version)
    return version


def is_api_break(commit):
    return (
        MAJOR_HEADER.search(commit.message.decode('utf-8')) or
        MAJOR_INVENIO.search(commit.message.decode('utf-8'))
    )


def is_feature(commit):
    return (
        FEAT_HEADER.search(commit.message.decode('utf-8')) or
        FEAT_INVENIO.search(commit.message.decode('utf-8'))
    )


def get_commit_type(commit, children=None, tags=None, prev_version=None):
    children = children or []
    tags = tags or []
    prev_version = prev_version or (0, 0, 0)
    commit_sha = commit.sha().hexdigest()

    if commit_sha in tags:
        maj_version, feat_version = tags[commit_sha].split(b'.')[:2]
        maj_version = int(maj_version)
        feat_version = int(feat_version)
        if maj_version > prev_version[0]:
            return 'api_break'
        elif feat_version > prev_version[1]:
            return 'feature'
        return 'bug'

    if any(is_api_break(child) for child in children + [commit]):
        return 'api_break'
    elif any(is_feature(child) for child in children + [commit]):
        return 'feature'
    else:
        return 'bug'


def get_changelog(repo_path, from_commit=None):
    """
    Given a repo path and an option commit/tag/refspec to start from, will
    get the rpm compatible changelog

    Args:
        repo_path (str): path to the git repo
        from_commit (str): refspec (partial commit hash, tag, branch, full
            refspec, partial refspec) to start the changelog from

    Returns:
        str: Rpm compatible changelog
    """
    repo = dulwich.repo.Repo(repo_path)
    tags = get_tags(repo)
    refs = get_refs(repo)
    changelog = []
    maj_version = 0
    feat_version = 0
    fix_version = 0
    start_including = False

    cur_line = ''
    if from_commit is None:
        start_including = True

    prev_version = (maj_version, feat_version, fix_version)

    for commit_sha, children in reversed(
        get_children_per_first_parent(repo_path).items()
    ):
        commit = get_repo_object(repo, commit_sha)
        maj_version, feat_version, fix_version = get_version(
            commit=commit,
            tags=tags,
            maj_version=maj_version,
            feat_version=feat_version,
            fix_version=fix_version,
            children=children,
        )
        version = (maj_version, feat_version, fix_version)
        version_str = '%s.%s.%s' % version

        if (
            start_including or commit_sha.startswith(from_commit) or
            fuzzy_matches_refs(from_commit, refs.get(commit_sha, []))
        ):
            commit_type = get_commit_type(
                commit=commit,
                children=children,
                tags=tags,
                prev_version=prev_version,
            )
            cur_line = pretty_commit(commit, version_str, commit_type)
            for child in children:
                commit_type = get_commit_type(
                    commit=commit,
                    tags=tags,
                    prev_version=prev_version,
                )
                cur_line += pretty_commit(
                    commit=child,
                    version=None,
                    commit_type=commit_type
                )
            start_including = True
            changelog.append(cur_line)

        prev_version = version

    return '\n'.join(reversed(changelog))


def get_current_version(repo_path):
    """
    Given a repo will return the version string, according to semantic
    versioning, counting as non-backwards compatible commit any one with a
    message header that matches (case insensitive)::

        sem-ver: .*break.*

    And as features any commit with a header matching::

        sem-ver: feature

    And counting any other as a bugfix
    """
    repo = dulwich.repo.Repo(repo_path)
    tags = get_tags(repo)
    maj_version = 0
    feat_version = 0
    fix_version = 0

    for commit_sha, children in reversed(
            get_children_per_first_parent(repo_path).items()
    ):
        commit = get_repo_object(repo, commit_sha)
        maj_version, feat_version, fix_version = get_version(
            commit=commit,
            tags=tags,
            maj_version=maj_version,
            feat_version=feat_version,
            fix_version=fix_version,
            children=children,
        )

    return '%s.%s.%s' % (maj_version, feat_version, fix_version)


def get_authors(repo_path, from_commit):
    """
    Given a repo and optionally a base revision to start from, will return
    the list of authors.
    """
    repo = dulwich.repo.Repo(repo_path)
    refs = get_refs(repo)
    start_including = False
    authors = set()

    if from_commit is None:
        start_including = True

    for commit_sha, children in reversed(
        get_children_per_first_parent(repo_path).items()
    ):
        commit = get_repo_object(repo, commit_sha)
        if (
            start_including or commit_sha.startswith(from_commit) or
            fuzzy_matches_refs(from_commit, refs.get(commit_sha, []))
        ):
            authors.add(commit.author.decode())
            for child in children:
                authors.add(child.author.decode())

            start_including = True

    return '\n'.join(sorted(authors))


def get_releasenotes(repo_path, from_commit):
    """
    Given a repo and optionally a base revision to start from, will return
    a text suitable for the relase notes announcement, grouping the bugs, the
    features and the api-breaking changes.
    """
    repo = dulwich.repo.Repo(repo_path)
    tags = get_tags(repo)
    refs = get_refs(repo)
    maj_version = 0
    feat_version = 0
    fix_version = 0
    start_including = False
    bugs = []
    features = []
    api_break_changes = []

    cur_line = ''
    if from_commit is None:
        start_including = True

    prev_version = (maj_version, feat_version, fix_version)

    for commit_sha, children in reversed(
        get_children_per_first_parent(repo_path).items()
    ):
        commit = get_repo_object(repo, commit_sha)
        maj_version, feat_version, fix_version = get_version(
            commit=commit,
            tags=tags,
            maj_version=maj_version,
            feat_version=feat_version,
            fix_version=fix_version,
            children=children,
        )
        version = (maj_version, feat_version, fix_version)
        version_str = '%s.%s.%s' % version

        if (
            start_including or commit_sha.startswith(from_commit) or
            fuzzy_matches_refs(from_commit, refs.get(commit_sha, []))
        ):
            parent_commit_type = get_commit_type(
                commit=commit,
                children=children,
                tags=tags,
                prev_version=prev_version,
            )
            cur_line = pretty_commit(commit, version_str, parent_commit_type)
            for child in children:
                commit_type = get_commit_type(
                    commit=commit,
                    tags=tags,
                    prev_version=prev_version,
                )
                cur_line += pretty_commit(
                    commit=child,
                    version=None,
                    commit_type=commit_type
                )
            start_including = True

            if parent_commit_type == 'api_break':
                api_break_changes.append(cur_line)
            elif parent_commit_type == 'feature':
                features.append(cur_line)
            else:
                bugs.append(cur_line)

        prev_version = version

    return '''
New changes for version %s
=================================

API Breaking changes
--------------------
%s

New features
------------
%s

Bugfixes and minor changes
--------------------------
%s
''' % (
        version_str,
        '\n'.join(reversed(api_break_changes)),
        '\n'.join(reversed(features)),
        '\n'.join(reversed(bugs)),
    )


def main(args):

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'repo_path', help='Git repo to generate the changelog for'
    )
    subparsers = parser.add_subparsers()
    changelog_parser = subparsers.add_parser('changelog')
    changelog_parser.add_argument(
        '--from-commit',
        default=None,
        help='Commit to start the changelog from'
    )
    changelog_parser.set_defaults(func=get_changelog)
    version_parser = subparsers.add_parser('version')
    version_parser.set_defaults(func=get_current_version)
    releasenotes_parser = subparsers.add_parser('releasenotes')
    releasenotes_parser.add_argument(
        '--from-commit',
        default=None,
        help='Commit to start the release notes from'
    )
    releasenotes_parser.set_defaults(func=get_releasenotes)
    authors_parser = subparsers.add_parser('authors')
    authors_parser.add_argument(
        '--from-commit',
        default=None,
        help='Commit to start the authors from'
    )
    authors_parser.set_defaults(func=get_authors)
    args = parser.parse_args(args)

    params = copy.deepcopy(vars(args))
    params.pop('func')
    return args.func(**params)


if __name__ == '__main__':
    print(main(sys.argv[1:]))

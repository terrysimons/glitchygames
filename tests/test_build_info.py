"""Tests for the engine source revision (glitchygames/build_info.py, scripts/write_build_stamp.py).

Each kind of answer is made for real: throwaway git repositories (a checkout, one with
uncommitted changes, a package installed untracked inside another repository), a real ``git
archive`` of a repository whose archive file is marked ``export-subst``, and a build stamp
written from a checkout and read from a copy of the package with no git.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
from typing import TYPE_CHECKING

import pytest
from scripts import write_build_stamp as write_build_stamp_script

from glitchygames import build_info
from glitchygames.build_info import (
    ARCHIVE_FILE_NAME,
    BUILD_STAMP_FILE_NAME,
    UNKNOWN_REVISION,
    RevisionSource,
    SourceRevision,
    archive_revision,
    engine_source_revision,
    environment_without_git_variables,
    git_checkout_revision,
    source_revision,
    stamped_revision,
    write_build_stamp,
)
from glitchygames.process import OutputCapture, TimeoutExpired, run_command
from glitchygames.recording_history import MeasurementRun, latest_measurement_run
from tests.harness import CHECKOUT_ENGINE_DIRECTORY

if TYPE_CHECKING:
    from pathlib import Path

# The variables that point git at another repository than the one its directory is in, written
# out by hand (build_info.REPOSITORY_LOCATION_VARIABLES must name each)
REPOSITORY_LOCATION_VARIABLES = (
    'GIT_DIR',
    'GIT_WORK_TREE',
    'GIT_INDEX_FILE',
    'GIT_COMMON_DIR',
    'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_NAMESPACE',
    'GIT_CEILING_DIRECTORIES',
)
ARCHIVAL_TEMPLATE = 'commit: $Format:%H$\ncommitted: $Format:%cI$\n'
BUILT_AT = '2026-10-23T12:00:00+00:00'
MODULE_FILE_NAME = 'module.py'


def _git(*arguments: str, directory: Path) -> str:
    """Run git in a directory with a fixed identity and no user configuration.

    Returns:
        Its standard output, stripped.

    """
    environment = {
        **os.environ,
        'GIT_CONFIG_GLOBAL': os.devnull,
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_AUTHOR_NAME': 'Test',
        'GIT_AUTHOR_EMAIL': 'test@example.com',
        'GIT_COMMITTER_NAME': 'Test',
        'GIT_COMMITTER_EMAIL': 'test@example.com',
    }
    git_program = shutil.which('git')
    assert git_program is not None, 'these tests need git'
    completed = run_command(
        command=[git_program, '-C', str(directory), *arguments],
        environment=environment,
        timeout_seconds=30.0,
        capture_output=OutputCapture.TOGETHER,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout.strip()


def _repository_with_package(root: Path) -> Path:
    """Make a git repository holding a committed package directory like the engine's.

    Returns:
        The package directory.

    """
    package_directory = root / 'package'
    package_directory.mkdir(parents=True)
    (package_directory / MODULE_FILE_NAME).write_text('# marker\n', encoding='utf-8')
    (package_directory / ARCHIVE_FILE_NAME).write_text(ARCHIVAL_TEMPLATE, encoding='utf-8')
    (root / '.gitattributes').write_text(
        f'package/{ARCHIVE_FILE_NAME} export-subst\n', encoding='utf-8'
    )
    _git('init', '--quiet', '--initial-branch=main', directory=root)
    _git('add', '.', directory=root)
    _git('commit', '--quiet', '--message', 'first', directory=root)
    return package_directory


class TestGitCheckout:
    """A package whose files git tracks: git answers, always current."""

    def test_this_engine_running_from_its_checkout_names_head(self):
        revision = source_revision(package_directory=CHECKOUT_ENGINE_DIRECTORY)

        assert revision.source is RevisionSource.GIT_CHECKOUT
        repository = CHECKOUT_ENGINE_DIRECTORY
        assert revision.commit == _git('rev-parse', 'HEAD', directory=repository)
        assert revision.committed_at == _git('log', '-1', '--format=%cI', directory=repository)
        status = _git('status', '--porcelain', '--untracked-files=no', directory=repository)
        assert revision.uncommitted_changes is bool(status)

    def test_a_clean_checkout_has_no_uncommitted_changes(self, tmp_path):
        package_directory = _repository_with_package(tmp_path)

        revision = git_checkout_revision(package_directory=package_directory)

        assert revision == SourceRevision(
            source=RevisionSource.GIT_CHECKOUT,
            commit=_git('rev-parse', 'HEAD', directory=tmp_path),
            committed_at=_git('log', '-1', '--format=%cI', directory=tmp_path),
            uncommitted_changes=False,
        )

    def test_an_edited_tracked_file_is_an_uncommitted_change(self, tmp_path):
        package_directory = _repository_with_package(tmp_path)
        (package_directory / MODULE_FILE_NAME).write_text('# edited\n', encoding='utf-8')

        revision = git_checkout_revision(package_directory=package_directory)

        assert revision is not None
        assert revision.uncommitted_changes is True

    def test_git_variables_in_the_environment_never_point_it_at_another_repository(
        self, tmp_path, monkeypatch
    ):
        """The commit is the package's own checkout's, whatever repository GIT_* names.

        GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE and GIT_COMMON_DIR set (a hook's, an alias's)
        name another repository, at another commit and with uncommitted changes.
        """
        package_directory = _repository_with_package(tmp_path / 'game')
        other = tmp_path / 'other'
        other_package = _repository_with_package(other)
        (other_package / MODULE_FILE_NAME).write_text('# edited\n', encoding='utf-8')
        _git('commit', '--quiet', '--all', '--message', 'second', directory=other)
        (other_package / MODULE_FILE_NAME).write_text('# dirty\n', encoding='utf-8')
        own_commit = _git('rev-parse', 'HEAD', directory=package_directory)
        monkeypatch.setenv('GIT_DIR', str(other / '.git'))
        monkeypatch.setenv('GIT_WORK_TREE', str(other))
        monkeypatch.setenv('GIT_INDEX_FILE', str(other / '.git' / 'index'))
        monkeypatch.setenv('GIT_COMMON_DIR', str(other / '.git'))

        revision = git_checkout_revision(package_directory=package_directory)

        assert revision is not None
        assert revision.commit == own_commit
        assert revision.uncommitted_changes is False

    def test_git_configuration_variables_reach_the_lookup(self, monkeypatch):
        """Only the variables that move git to another repository are left out of its lookup.

        ``GIT_CONFIG_*`` (``safe.directory`` given through the environment, say) and the rest
        reach git as they are, so a checkout git would trust still names its commit.
        """
        for name in REPOSITORY_LOCATION_VARIABLES:
            monkeypatch.setenv(name, 'another-repository')
        monkeypatch.setenv('GIT_CONFIG_COUNT', '1')
        monkeypatch.setenv('GIT_CONFIG_KEY_0', 'safe.directory')
        monkeypatch.setenv('GIT_CONFIG_VALUE_0', '*')

        environment = environment_without_git_variables()

        assert set(REPOSITORY_LOCATION_VARIABLES) == build_info.REPOSITORY_LOCATION_VARIABLES
        assert not set(REPOSITORY_LOCATION_VARIABLES) & set(environment)
        assert environment['GIT_CONFIG_COUNT'] == '1'
        assert environment['GIT_CONFIG_KEY_0'] == 'safe.directory'
        assert environment['GIT_CONFIG_VALUE_0'] == '*'

    def test_an_untracked_new_file_is_not_an_uncommitted_change(self, tmp_path):
        package_directory = _repository_with_package(tmp_path)
        (tmp_path / 'scratch.txt').write_text('notes\n', encoding='utf-8')

        revision = git_checkout_revision(package_directory=package_directory)

        assert revision is not None
        assert revision.uncommitted_changes is False

    def test_a_package_installed_untracked_inside_another_repository_is_not_a_checkout(
        self, tmp_path
    ):
        """A game's .venv (or .nox) sits in the game's work tree, but git does not track it."""
        _repository_with_package(tmp_path)
        installed = tmp_path / '.venv' / 'site-packages' / 'glitchygames'
        installed.mkdir(parents=True)
        (installed / MODULE_FILE_NAME).write_text('# installed copy\n', encoding='utf-8')

        assert git_checkout_revision(package_directory=installed) is None
        assert source_revision(package_directory=installed) == UNKNOWN_REVISION

    def test_a_directory_outside_any_repository_is_not_a_checkout(self, tmp_path):
        assert git_checkout_revision(package_directory=tmp_path) is None

    def test_without_git_there_is_no_checkout_answer(self, tmp_path, mocker):
        package_directory = _repository_with_package(tmp_path)
        mocker.patch.object(build_info.shutil, 'which', return_value=None)

        assert git_checkout_revision(package_directory=package_directory) is None

    @pytest.mark.parametrize(
        'failure', [TimeoutExpired(cmd='git', timeout=5.0), OSError('git vanished')]
    )
    def test_a_git_that_hangs_or_cannot_start_is_no_answer(self, tmp_path, mocker, failure):
        package_directory = _repository_with_package(tmp_path)
        mocker.patch.object(build_info, 'run_command', side_effect=failure)

        assert git_checkout_revision(package_directory=package_directory) is None

    def test_a_repository_without_commits_is_no_answer(self, tmp_path):
        package_directory = tmp_path / 'package'
        package_directory.mkdir()
        (package_directory / MODULE_FILE_NAME).write_text('# marker\n', encoding='utf-8')
        _git('init', '--quiet', directory=tmp_path)
        _git('add', '.', directory=tmp_path)

        assert git_checkout_revision(package_directory=package_directory) is None

    def test_a_status_that_fails_leaves_uncommitted_changes_unknown(self, tmp_path, mocker):
        package_directory = _repository_with_package(tmp_path)
        real_git_output = build_info._git_output

        def git_output_without_status(*, arguments, directory):
            if arguments[0] == 'status':
                return None
            return real_git_output(arguments=arguments, directory=directory)

        mocker.patch.object(build_info, '_git_output', side_effect=git_output_without_status)

        revision = git_checkout_revision(package_directory=package_directory)

        assert revision is not None
        assert revision.commit is not None
        assert revision.uncommitted_changes is None


class TestGitArchive:
    """``git archive`` writes the archived commit into the export-subst file."""

    def test_a_real_git_archive_names_its_commit(self, tmp_path):
        repository = tmp_path / 'repository'
        _repository_with_package(repository)
        commit = _git('rev-parse', 'HEAD', directory=repository)
        archive_path = tmp_path / 'source.tar'
        _git('archive', '--format=tar', f'--output={archive_path}', 'HEAD', directory=repository)
        extracted = tmp_path / 'extracted'
        with tarfile.open(archive_path) as archive:
            archive.extractall(extracted, filter='data')

        revision = source_revision(package_directory=extracted / 'package')

        assert revision == SourceRevision(
            source=RevisionSource.GIT_ARCHIVE,
            commit=commit,
            committed_at=_git('log', '-1', '--format=%cI', directory=repository),
        )

    def test_the_checkouts_unexpanded_file_says_nothing(self, tmp_path):
        (tmp_path / ARCHIVE_FILE_NAME).write_text(ARCHIVAL_TEMPLATE, encoding='utf-8')

        assert archive_revision(package_directory=tmp_path) is None

    def test_the_engines_own_archive_file_is_the_unexpanded_template(self):
        archive_file = build_info.PACKAGE_DIRECTORY / ARCHIVE_FILE_NAME

        assert archive_file.read_text(encoding='utf-8') == ARCHIVAL_TEMPLATE
        assert archive_revision(package_directory=build_info.PACKAGE_DIRECTORY) is None

    def test_an_unexpanded_date_alone_is_dropped(self, tmp_path):
        (tmp_path / ARCHIVE_FILE_NAME).write_text(
            'commit: abc123\ncommitted: $Format:%cI$\nnot a field\n', encoding='utf-8'
        )

        assert archive_revision(package_directory=tmp_path) == SourceRevision(
            source=RevisionSource.GIT_ARCHIVE, commit='abc123'
        )

    @pytest.mark.parametrize('contents', [b'committed: 2026\n', b'\xff\xfe not text'])
    def test_a_file_without_a_commit_or_not_text_says_nothing(self, tmp_path, contents):
        (tmp_path / ARCHIVE_FILE_NAME).write_bytes(contents)

        assert archive_revision(package_directory=tmp_path) is None


class TestBuildStamp:
    """A build from a checkout stamps the package; the packaged copy reads it without git."""

    def test_a_stamp_written_in_a_checkout_is_read_by_the_packaged_copy(self, tmp_path):
        package_directory = _repository_with_package(tmp_path / 'repository')
        (package_directory / MODULE_FILE_NAME).write_text('# edited\n', encoding='utf-8')

        written = write_build_stamp(package_directory=package_directory, built_at=BUILT_AT)
        packaged = tmp_path / 'site-packages' / 'package'
        shutil.copytree(package_directory, packaged)

        expected = SourceRevision(
            source=RevisionSource.BUILD_STAMP,
            commit=_git('rev-parse', 'HEAD', directory=package_directory),
            committed_at=_git('log', '-1', '--format=%cI', directory=package_directory),
            uncommitted_changes=True,
            built_at=BUILT_AT,
        )
        assert written == expected
        assert source_revision(package_directory=packaged) == expected
        stamp_fields = json.loads((packaged / BUILD_STAMP_FILE_NAME).read_text(encoding='utf-8'))
        assert 'source' not in stamp_fields

    def test_a_build_from_an_archive_stamps_the_archived_commit(self, tmp_path):
        (tmp_path / ARCHIVE_FILE_NAME).write_text('commit: abc123\n', encoding='utf-8')

        stamp = write_build_stamp(package_directory=tmp_path, built_at=BUILT_AT)

        assert stamp == SourceRevision(
            source=RevisionSource.BUILD_STAMP, commit='abc123', built_at=BUILT_AT
        )

    def test_a_build_from_neither_stamps_an_unknown_commit(self, tmp_path):
        stamp = write_build_stamp(package_directory=tmp_path, built_at=BUILT_AT)

        assert stamp == SourceRevision(source=RevisionSource.BUILD_STAMP, built_at=BUILT_AT)

    def test_a_checkout_answers_before_a_stale_stamp_left_in_it(self, tmp_path):
        package_directory = _repository_with_package(tmp_path)
        (package_directory / BUILD_STAMP_FILE_NAME).write_text(
            json.dumps({'commit': 'stale'}), encoding='utf-8'
        )

        revision = source_revision(package_directory=package_directory)

        assert revision.source is RevisionSource.GIT_CHECKOUT
        assert revision.commit != 'stale'

    @pytest.mark.parametrize(
        'contents', [b'not json', b'["a list"]', b'{"commit": 5}', b'{"extra": 1}', b'\xff']
    )
    def test_an_unreadable_stamp_says_nothing(self, tmp_path, contents):
        (tmp_path / BUILD_STAMP_FILE_NAME).write_bytes(contents)

        assert stamped_revision(package_directory=tmp_path) is None
        assert source_revision(package_directory=tmp_path) == UNKNOWN_REVISION


class TestWriteBuildStampScript:
    """scripts/write_build_stamp.py: what nox -s build-wheel / build-binary run around a build."""

    def test_it_writes_then_removes_the_stamp(self, tmp_path, mocker):
        package_directory = _repository_with_package(tmp_path)
        mocker.patch.object(write_build_stamp_script, 'PACKAGE_DIRECTORY', package_directory)
        output = mocker.patch.object(write_build_stamp_script.sys, 'stdout', new=io.StringIO())
        stamp_path = package_directory / BUILD_STAMP_FILE_NAME

        assert write_build_stamp_script.main([]) == 0
        stamped = stamped_revision(package_directory=package_directory)
        assert stamped is not None
        assert stamped.commit == _git('rev-parse', 'HEAD', directory=tmp_path)
        assert stamped.built_at is not None

        assert write_build_stamp_script.main(['--remove']) == 0
        assert not stamp_path.exists()
        assert write_build_stamp_script.main(['--remove']) == 0
        assert f'Wrote {stamp_path}: commit {stamped.commit}' in output.getvalue()
        assert f'Removed {stamp_path}' in output.getvalue()


class TestEngineSourceRevision:
    """The engine looks its revision up once per process and records it in every run."""

    def test_it_is_looked_up_once(self, mocker):
        engine_source_revision.cache_clear()
        lookup = mocker.patch.object(build_info, 'source_revision', return_value=UNKNOWN_REVISION)
        try:
            assert engine_source_revision() is UNKNOWN_REVISION
            assert engine_source_revision() is UNKNOWN_REVISION
            assert lookup.call_count == 1
        finally:
            engine_source_revision.cache_clear()

    def test_a_run_from_before_the_field_reads_as_none_and_a_new_run_round_trips(self):
        old_run = {
            'machine': 'macOS',
            'processing_paced': False,
            'engine_version': None,
            'pygame_version': '2.5.8',
            'python_version': '3.14.0',
            'measured_at': BUILT_AT,
            'rebaselined_from': None,
            'hash_scheme': 1,
        }
        old = latest_measurement_run(header={'measurement_runs': [old_run]})
        assert old is not None
        assert old.source_revision is None

        revision = SourceRevision(
            source=RevisionSource.GIT_CHECKOUT, commit='abc', uncommitted_changes=False
        )
        new_run = MeasurementRun.model_validate({**old_run, 'source_revision': revision})
        read_back = latest_measurement_run(header={'measurement_runs': [new_run.to_json()]})
        assert read_back == new_run
        assert new_run.to_json()['source_revision']['source'] == 'git-checkout'

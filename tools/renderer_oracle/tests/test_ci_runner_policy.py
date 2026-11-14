#!/usr/bin/env python3
"""Hosted runner, bounded execution DAG and fail-closed CI acceptance policy."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github' / 'workflows' / 'continuous_integration.yml'
WORKERS = ['corpus', 'publication', 'controls', 'witness-1', 'witness-2']
PROBE_WORKERS = WORKERS[2:]
CAPTURE_WORKERS = WORKERS[1:]


def job_blocks(text):
    """Read the workflow's deliberately simple top-level job map without PyYAML."""
    body = text.split('\njobs:\n', 1)[1]
    jobs = list(re.finditer(r'(?m)^  ([A-Za-z_][\w-]*):\s*$', body))
    return {match.group(1): body[match.end():jobs[index + 1].start()
            if index + 1 < len(jobs) else len(body)]
            for index, match in enumerate(jobs)}


def step_blocks(job):
    steps = list(re.finditer(r'(?m)^    - name: (.+)$', job))
    return {match.group(1): job[match.end():steps[index + 1].start()
            if index + 1 < len(steps) else len(job)]
            for index, match in enumerate(steps)}


def dependencies(block):
    match = re.search(r'(?m)^    needs: (.+)$', block)
    if not match:
        return []
    return [value.strip() for value in match.group(1).strip('[]').split(',')]


class GithubHostedRunnerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()
        self.jobs = job_blocks(self.text)

    def test_active_workflows_do_not_request_avrea_or_self_hosted(self):
        workflows = sorted((ROOT / '.github' / 'workflows').glob('*.yml'))
        self.assertTrue(workflows)
        for path in workflows:
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertNotIn('avrea', text.lower())
                self.assertNotIn('self-hosted', text.lower())

    def test_exact_windows_linux_matrix_and_check_names_remain(self):
        config = self.jobs['build'].split('        config:\n', 1)[1].split('\n    steps:', 1)[0]
        matches = list(re.finditer(r'(?m)^        - name: (.+)$', config))
        rows = []
        for index, match in enumerate(matches):
            block = config[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(config)]
            os_name = re.search(r'(?m)^          os: (.+)$', block).group(1)
            build_type = re.search(r'(?m)^          build_type: (.+)$', block).group(1)
            rows.append((match.group(1), build_type, os_name))
        self.assertEqual(rows, [
            ('Visual Studio 2022', 'RelWithDebInfo', 'windows-2022'),
            ('Visual Studio 2022', 'Debug', 'windows-2022'),
            ('Linux GCC 12', 'RelWithDebInfo', 'ubuntu-22.04'),
            ('Linux Clang 11', 'Debug', 'ubuntu-22.04'),
            ('Linux Clang 15', 'Release', 'ubuntu-22.04'),
        ])
        self.assertIn('name: ${{ matrix.config.name }} | ${{ matrix.config.build_type }}', self.jobs['build'])
        self.assertIn('name: Linux software Vulkan | RelWithDebInfo', self.jobs['vulkan_evidence'])
        self.assertNotIn('macos', self.text.lower())
        self.assertNotIn('DYLD_LIBRARY_PATH', self.text)
        self.assertIn('unittest discover -s tools/physical_supervisor -t . -v', self.jobs['build'])
        self.assertIn('sdvk009_probe_cpu_tests.exe', self.jobs['build'])

    def test_source_bundle_exports_the_same_exact_head_as_the_runtime(self):
        source_workflow = (ROOT / '.github/workflows/renderer_source_evidence.yml').read_text()
        self.assertIn('ref: ${{ github.event.pull_request.head.sha || github.sha }}', source_workflow)
        self.assertIn('fetch-depth: 0', source_workflow)
        self.assertIn('name: Exact renderer source bundle', source_workflow)

    def test_bounded_matrix_expansion_has_three_four_or_five_unique_workers(self):
        registration = step_blocks(self.jobs['vulkan_build'])[
            'Authenticate historical content and preregister the complete capture plan']
        arrays = [json.loads(value) for value in re.findall(r"suites='([^']+)'", registration)]
        self.assertEqual(arrays, [WORKERS, CAPTURE_WORKERS, PROBE_WORKERS, PROBE_WORKERS])
        for workers in arrays:
            self.assertEqual(len(workers), len(set(workers)))
        self.assertIn('suite: ${{ fromJSON(needs.vulkan_build.outputs.suites) }}', self.jobs['vulkan_qualification'])
        self.assertIn('fail-fast: false', self.jobs['vulkan_qualification'])
        self.assertNotIn('max-parallel:', self.jobs['vulkan_qualification'])
        self.assertNotIn('continue-on-error:', self.text)

    def test_dependencies_are_acyclic_and_capture_workers_have_no_serial_gate(self):
        graph = {name: dependencies(block) for name, block in self.jobs.items()}
        self.assertEqual(graph['vulkan_qualification'], ['vulkan_build'])
        self.assertEqual(set(graph['vulkan_evidence']), {'pf_oracle', 'build', 'vulkan_build', 'vulkan_qualification'})
        self.assertEqual(graph['build'], [])
        self.assertEqual(graph['vulkan_build'], [])
        self.assertEqual(graph['pf_oracle'], [])
        visiting, visited = set(), set()

        def visit(name):
            self.assertIn(name, graph, 'Workflow dependency names a nonexistent job')
            self.assertNotIn(name, visiting, 'Workflow dependency cycle')
            if name in visited:
                return
            visiting.add(name)
            for dependency in graph[name]:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for name in graph:
            visit(name)
        self.assertEqual(visited, set(graph))

    def test_diagnostic_modes_are_bounded_and_never_qualify(self):
        names = {'vulkan_probe_gated_controls', 'vulkan_probe_gated_witnesses', 'vulkan_probe_gated_evidence'}
        mode = re.search(r'(?m)^  SDVK_PUBLICATION_CAMPAIGN: (.+)$', self.text).group(1)
        self.assertIn(mode, ('preflight', 'shadow-startup-probe', 'cohort-probe', 'full'))
        self.assertFalse(names.intersection(self.jobs), 'The completed one-time gated experiment must not recur')
        self.assertNotIn('TEMPORARY POC', self.text)
        registration = step_blocks(self.jobs['vulkan_build'])[
            'Authenticate historical content and preregister the complete capture plan']
        self.assertEqual(registration.count('sdvk009_distributed register'), 1)
        case = registration.split('        case "$SDVK_PUBLICATION_CAMPAIGN" in', 1)[1].split('        esac', 1)[0]
        script = ('SDVK_PUBLICATION_CAMPAIGN="$1"\nflags=()\n'
                  'case "$SDVK_PUBLICATION_CAMPAIGN" in' + case + '\nesac\n'
                  'printf "%s\\n" "$suites" "${flags[*]}"\n')
        expected = {'full': (WORKERS, '--cohort'), 'cohort-probe': (CAPTURE_WORKERS, '--cohort-probe'),
                    'preflight': (PROBE_WORKERS, '--compatibility-probe'),
                    'shadow-startup-probe': (PROBE_WORKERS, '--shadow-startup-probe')}
        for campaign, (workers, flag) in expected.items():
            with self.subTest(campaign=campaign):
                result = subprocess.run(['bash', '-c', script, 'mode-check', campaign],
                                        check=True, capture_output=True, text=True)
                values = result.stdout.splitlines()
                self.assertEqual(json.loads(values[0]), workers)
                self.assertEqual(values[1], flag)
        invalid = subprocess.run(['bash', '-c', script, 'mode-check', 'unbounded'],
                                 capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)
        aggregate = step_blocks(self.jobs['vulkan_evidence'])
        restore = aggregate['Authenticate and restore worker evidence without accepting captures']
        self.assertIn('cohort-probe) flags+=(--suites publication,controls,witness-1,witness-2)', restore)
        self.assertIn('preflight|shadow-startup-probe) flags+=(--suites controls,witness-1,witness-2)', restore)
        gate = aggregate['Require every native, platform, CPU and authenticated assembly gate']
        self.assertIn('"$SDVK_PUBLICATION_CAMPAIGN" != full', gate)
        self.assertIn('PRECHECK_ONLY', gate)

    def test_shared_build_is_exact_source_and_never_recompiled_by_consumers(self):
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                self.assertIn('ref: ${{ github.event.pull_request.head.sha || github.sha }}', job)
        for name in ('vulkan_build', 'vulkan_qualification', 'vulkan_evidence'):
            self.assertIn('runs-on: ubuntu-24.04', self.jobs[name])
        consumer = self.jobs['vulkan_qualification']
        self.assertNotIn('cmake --build', consumer)
        self.assertNotIn('fetch_build_deps.py', consumer)
        self.assertNotIn('fetch-content', consumer)
        self.assertIn('software-vulkan-runtime.tar.gz.sha256', consumer)
        self.assertIn('needs.vulkan_build.outputs.runtime_sha256', consumer)
        self.assertIn('needs.vulkan_build.outputs.inputs_sha256', consumer)
        self.assertIn('needs.vulkan_build.outputs.plan_sha256', consumer)
        self.assertIn('--expected-state clean', consumer)
        steps = step_blocks(consumer)
        for name in ('Download exactly one shared renderer build', 'Verify archive and source-matched runtime'):
            self.assertNotIn('if:', steps[name], 'Every worker must authenticate the shared source/runtime')
        for name in ('Download preregistered publication inputs', 'Verify preregistered publication inputs'):
            self.assertIn("if: matrix.suite != 'corpus'", steps[name])
        self.assertNotIn('software-vulkan-publication-inputs', steps['Verify archive and source-matched runtime'])
        self.assertIn('SDVK_PUBLICATION_CAMPAIGN', self.text)
        self.assertNotIn('--expected-commit "$GITHUB_SHA"', self.text)

    def test_original_native_corpus_and_six_short_modules_preserved(self):
        steps = step_blocks(self.jobs['vulkan_qualification'])
        corpus = steps['Qualify software Vulkan corpus and timing collection']
        self.assertIn("if: matrix.suite == 'corpus'", corpus)
        self.assertIn('sdvk008_physical.py', corpus)
        self.assertIn('--correctness-only --software-fixture-control', corpus)
        self.assertIn('native_ci.py --exe build/vkdoom --iwad /usr/share/games/doom/freedoom2.wad --out build/renderer-native --full', corpus)
        self.assertIn('--classification reconstructed-hosted-production --replay', corpus)
        expected = ['sdvk010_acceptance', 'sdvk150_probe_owner', 'sdvk153_probe_reset',
                    'sdvk158_lightmap_transition', 'sdvk161_special_surfaces', 'sdvk014_controlled_planes']
        actual = []
        for step in steps.values():
            for module in expected:
                if '-m tools.renderer_oracle.' + module in step:
                    actual.append(module)
                    self.assertIn("if: matrix.suite == 'publication'", step)
                    self.assertIn('--iwad build/renderer-sdvk009-content/freedoom2.wad', step)
                    self.assertIn('--iwad-license build/renderer-sdvk009-content/COPYING.txt', step)
                    self.assertIn('--expected-commit "$(git rev-parse HEAD)"', step)
        self.assertEqual(actual, expected)
        worker = steps['Execute exactly the preregistered SDVK-009 worker captures']
        self.assertIn("if: " + ' || '.join("matrix.suite == '" + name + "'" for name in CAPTURE_WORKERS), worker)
        self.assertEqual(worker.count('sdvk009_distributed worker'), 1)
        self.assertIn("--worker '${{ matrix.suite }}'", worker)
        self.assertLess(self.jobs['vulkan_qualification'].index('Qualify SDVK-014 controlled planes'),
                        self.jobs['vulkan_qualification'].index('Execute exactly the preregistered SDVK-009 worker captures'))
        self.assertNotIn('sdvk009_publication qualify', self.text)
        self.assertNotIn('retry', worker.lower())

    def test_cohort_barrier_is_fixed_authenticated_and_cannot_launch_native_retries(self):
        job = self.jobs['vulkan_qualification']
        steps = step_blocks(job)
        probe = steps['Collect one preregistered bounded compatibility probe per shadow host']
        upload = steps['Retain immutable compatibility probe including failures']
        barrier = steps['Authenticate all three immutable peer probes within a bounded barrier']
        execution = steps['Execute exactly the preregistered SDVK-009 worker captures']
        modes = "(env.SDVK_PUBLICATION_CAMPAIGN == 'full' || env.SDVK_PUBLICATION_CAMPAIGN == 'cohort-probe')"
        probe_hosts = '(' + ' || '.join("matrix.suite == '" + name + "'" for name in PROBE_WORKERS) + ')'
        self.assertIn('if: ' + modes + ' && ' + probe_hosts, probe)
        self.assertIn('if: always() && ' + modes + ' && ' + probe_hosts, upload)
        self.assertIn('if: ' + modes + " && matrix.suite != 'corpus'", barrier)
        self.assertEqual(probe.count('sdvk009_distributed probe'), 1)
        self.assertIn("--out 'build/renderer-sdvk009-probe-${{ matrix.suite }}'", probe)
        self.assertIn('sdvk-cohort-probe-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.suite }}', upload)
        self.assertIn('include-hidden-files: true', upload)
        self.assertIn('if-no-files-found: error', upload)
        self.assertIn('uses: actions/upload-artifact@v4', upload)
        self.assertIn('--run-id', barrier)
        self.assertIn('--run-attempt', barrier)
        self.assertIn('--expected-commit "$(git rev-parse HEAD)"', barrier)
        self.assertIn('needs.vulkan_build.outputs.plan_sha256', barrier)
        self.assertIn('--out build/cohort-peers --artifact-set build/cohort-artifacts.json', barrier)
        self.assertIn('renderer-ci-${{ matrix.suite }}/cohort-barrier.json', barrier)
        self.assertIn('id: cohort_barrier', barrier)
        self.assertIn('--peers build/cohort-peers --artifact-set build/cohort-artifacts.json', execution)
        self.assertIn('permissions:\n      contents: read\n      actions: read', job)
        self.assertIn('timeout-minutes: 230', job)
        self.assertNotIn('actions: write', job)
        self.assertEqual(job.count('GITHUB_TOKEN:'), 1, 'API credential must be scoped to the transfer step')
        self.assertNotIn('GITHUB_TOKEN', probe)
        failure = steps['Retain failed cohort transfers without repeating probes']
        self.assertIn("if: always() && (steps.cohort_barrier.outcome == 'failure' || steps.cohort_barrier.outcome == 'cancelled')", failure)
        self.assertIn('name: renderer-cohort-transfer-failure-${{ matrix.suite }}', failure)
        self.assertIn('build/cohort-peers-archives/', failure)
        self.assertIn('build/renderer-ci-${{ matrix.suite }}/cohort-barrier.json', failure)
        self.assertIn('include-hidden-files: true', failure)
        self.assertNotIn('renderer-software-vulkan-', failure)
        for before, after in (
                ('Select explicit hosted llvmpipe', 'Collect one preregistered bounded'),
                ('Collect one preregistered bounded', 'Retain immutable compatibility probe'),
                ('Retain immutable compatibility probe', 'Authenticate all three immutable peer probes'),
                ('Qualify SDVK-014 controlled planes', 'Authenticate all three immutable peer probes'),
                ('Authenticate all three immutable peer probes', 'Execute exactly the preregistered')):
            self.assertLess(job.index(before), job.index(after))

    def test_failure_retention_and_complete_gate_are_explicit(self):
        workers = step_blocks(self.jobs['vulkan_qualification'])
        for name in ('Record worker completion including failures',
                     'Package lossless suite evidence (including failures)', 'Retain suite evidence'):
            self.assertIn('if: always()', workers[name])
        self.assertIn("--job-status '${{ job.status }}'", workers['Package lossless suite evidence (including failures)'])
        self.assertIn('if-no-files-found: error', workers['Retain suite evidence'])
        steps = step_blocks(self.jobs['vulkan_evidence'])
        download = steps['Download available qualification evidence']
        self.assertIn('merge-multiple: false', download)
        self.assertNotIn('merge-multiple: true', self.text)
        restore = steps['Authenticate and restore worker evidence without accepting captures']
        self.assertIn('flags+=(--complete)', restore)
        self.assertIn('--suites controls,witness-1,witness-2', restore)
        self.assertIn('--expected-commit', restore)
        self.assertIn('--runtime-sha256', restore)
        self.assertIn('--plan-sha256', restore)
        assemble = steps['Reconstruct and validate all original SDVK-009 comparisons and controls']
        self.assertIn("steps.restore.outcome == 'success'", assemble)
        self.assertIn("needs.vulkan_qualification.result == 'success'", assemble)
        self.assertIn('sdvk009_distributed assemble', assemble)
        timings = steps['Report individual capture timings after evidence assembly']
        self.assertIn("if: always() && steps.restore.outcome == 'success'", timings)
        self.assertNotIn("steps.assemble.outcome == 'success'", timings)
        self.assertIn("env.SDVK_PUBLICATION_CAMPAIGN == 'full'", timings)
        finalize = steps['Package and verify the complete legacy archive including failed comparisons']
        self.assertIn("if: always() && steps.restore.outcome == 'success'", finalize)
        self.assertIn('renderer_evidence.py finalize', finalize)
        self.assertIn('renderer-software-vulkan.tar.xz', finalize)
        gate = steps['Require every native, platform, CPU and authenticated assembly gate']
        for job in ('pf_oracle', 'build', 'vulkan_build', 'vulkan_qualification'):
            self.assertIn('test "${{ needs.' + job + '.result }}" = success', gate)
        for step in ('restore', 'assemble', 'finalize'):
            self.assertIn('test "${{ steps.' + step + '.outcome }}" = success', gate)
        self.assertIn('"$SDVK_PUBLICATION_CAMPAIGN" != full', gate)
        self.assertIn('PRECHECK_ONLY', gate)
        self.assertIn("qualification['status'] == 'PASS'", gate)
        self.assertIn('exit 1', gate)
        self.assertIn('if: always()', steps['Upload complete software Vulkan evidence'])
        self.assertIn('retention-days: 30', steps['Upload complete software Vulkan evidence'])
        self.assertIn('test_*.py', self.jobs['pf_oracle'])

    def test_shared_native_guard_requires_github_hosted(self):
        text = (ROOT / 'tools' / 'renderer_oracle' / 'sdvk010_sun_native.py').read_text()
        self.assertIn('os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"', text)
        self.assertNotIn('avrea', text.lower())
        self.assertNotIn('self-hosted', text.lower())
        self.assertNotIn('== 16', text)
        self.assertIn('llvmpipe', text)
        self.assertNotIn('SDVK_REQUESTED_RUNNER', self.text)
        self.assertNotIn('sdvk009-avrea-ci.py', self.text)


if __name__ == '__main__':
    unittest.main()

# SDVK-009 CI cancellation review

The macOS jobs in runs 41212815823 (#168) and 41215224554 (#169) were
cancelled before receiving a runner. Their check annotations identify the
scheduled macOS 14 runner-image brownout, rather than a source-test failure.
The other seven jobs completed successfully on each head. Cancelled jobs are
not passes and those historical results remain unchanged.

[The runner-image retirement notice](https://github.com/actions/runner-images/issues/13518)
includes 31 October 2026, 14:00 UTC through 1 November, 00:00 UTC, and removal
on 2 November. Both existing macOS matrix jobs now use the recommended pinned
`macos-15` image. Job count, workloads, checks and acceptance thresholds are
unchanged; normal PR CI must qualify the new heads. This is not permission for
additional benchmark runners or physical qualification. Issue #9 stays open,
Physical STOP active and SDVK-009-PHYSICAL held.

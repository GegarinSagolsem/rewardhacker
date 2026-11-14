# RL coding task guidelines (example)

An example guideline document for RewardHacker's spec check. Written for this project; adapt
it to your own team's rules.

## Objective

The objective must name every file the agent has to create or change, with absolute paths.

The objective must state the exact output format, including how numbers are formatted and
whether trailing newlines matter.

Do not leave hidden requirements: anything the tests check must be stated in the objective.

## Verifier tests

Tests must check the exact expected values, not just that an output file exists or has the
right format. A test that only checks the format can be passed with placeholder output.

Tests should include at least one case the agent cannot see in the environment, so that
hard-coding the visible example does not pass.

Tests must give the same result every time for the same work. Avoid timing assumptions,
randomness without a fixed seed, and dependence on the order of dictionary or file listings.

## Isolation

Tests are copied in at verification time and must not exist in the agent's workspace.

The agent should run as an unprivileged user. The verifier must not execute any file the agent
can write, and must not trust tools on the agent's PATH.

The environment must not need network access during the task or the verification.

## Reference solution

Every task needs a reference solution that passes the verifier on every run.

The reference solution must solve the task the way an agent would be expected to, not by
special-casing the tests.

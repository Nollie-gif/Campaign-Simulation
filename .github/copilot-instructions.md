# Repository Instructions

Before modifying this repository, read and follow the root-level `INSTALLATION_GUIDE.md` and `docs/ENGINEERING_DOCUMENTATION_POLICY.md`.

The protected-main workflow is mandatory: do not write directly to `main`; use a focused branch, pull request, required tests/CI, review, and only then merge.

Meaningful implementation changes must update the relevant repository documentation in the same branch/PR, or use the explicit behavior-neutral documentation exemption defined by the policy. The user must not be relied on to request documentation coverage manually.

Before creating or updating any external Workflow Decision Record, audit the live branch for duplication. Keep live mechanics in GitHub; keep rationale, boundaries, status, and verification evidence in the decision record.

If the user explicitly requests review-only work or no repository mutation, do not modify the repository until later authorization.

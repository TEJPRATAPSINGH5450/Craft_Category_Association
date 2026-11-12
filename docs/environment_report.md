# Phase 1 environment inspection

Initialization date: 2026-11-11 (Asia/Calcutta).

## System

- Workspace: `C:\Users\aftab\Desktop\SuperwiseProject`.
- OS runtime identification: Microsoft Windows 10.0.26300 (kernel version; not a marketing edition).
- PowerShell: 7.6.9.
- Git: 2.46.1.windows.1.
- Registered Python: 3.14.4 at `C:\Python314\python.exe`.
- Original pip: 26.2.1 (user-level installation; unchanged).
- Project environment: `C:\Users\aftab\Desktop\SuperwiseProject\.venv`.
- Project interpreter: `.venv\Scripts\python.exe`.
- System site packages are disabled in the virtual environment.
- Activation via `.venv\Scripts\Activate.ps1` succeeded in the setup shell; other terminals need their own activation.

Python 3.11/3.12 were preferred but not registered. Dependency resolution confirmed Windows wheels for the existing Python 3.14 interpreter, avoiding a system-level installation. Installed versions and verification results are recorded alongside this report in `environment_verification.txt`. Full dependency pins are in the root `requirements.txt`.

## Dataset preservation

Found at `C:\Users\aftab\Desktop\SuperwiseProject\online+retail+ii\online_retail_II.xlsx`.

Moved with explicit user approval to `C:\Users\aftab\Desktop\SuperwiseProject\data\raw\online_retail_II.xlsx`.

Size: 45,622,278 bytes (approximately 43.51 MiB).

SHA-256 before and after move: `BCBE73B35F5B7BABF197FB0CB983A11F5D9FF929078D4AA53D171B1F2DF2E980`.

The file was not opened for workbook analysis or changed. The source directory was retained. Worksheet names and columns remain unverified until Phase 2.

## Setup limitations and recoveries

- Windows CIM inspection was access-restricted; OS information was obtained from the .NET runtime instead.
- Initial PyPI access failed because sandbox DNS/network access was restricted. Approved network access allowed dependency retrieval.
- This workspace is not initialized as a Git repository. `.gitignore` has been created, but `git check-ignore` cannot validate it until a repository exists. No Git commit, remote, or upload was performed.
- Dependency imports and resolver checks validate environment readiness, not scientific or runtime correctness of future ML experiments.
- The first import check could not persist Matplotlib's font cache to the user profile. The verification script now uses a project-local ignored `.cache/matplotlib/` directory, without changing system settings.

## Final verification

All ten required library imports passed, as did imports of the planned K-Means and Apriori entry points (no algorithm execution). `pip check` reported no broken requirements. Jupyter's CLI version check succeeded. Project pip is 26.3. All dependencies were installed in `.venv`; Streamlit was not installed. No installation failures remain.

No preprocessing, EDA, model fitting, rule mining, or dashboard work is authorized or performed in Phase 1. Phase 2 requires explicit user approval.

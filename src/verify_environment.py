"""Verify Phase 1 dependencies without reading data or executing ML algorithms."""

import importlib
import json
import os
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys


PACKAGES = {
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "scikit-learn": "sklearn",
    "mlxtend": "mlxtend",
    "openpyxl": "openpyxl",
    "jupyter": "jupyter",
    "ipykernel": "ipykernel",
    "scipy": "scipy",
}


def main():
    expected = Path(__file__).resolve().parents[1] / ".venv"
    if Path(sys.prefix).resolve() != expected.resolve() or sys.prefix == sys.base_prefix:
        raise RuntimeError("Run this script with the project's .venv interpreter.")
    # Keep verification's font cache inside the writable project workspace.
    cache = expected.parent / ".cache" / "matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache)
    results = {}
    for distribution, module in PACKAGES.items():
        importlib.import_module(module)
        results[distribution] = {"version": version(distribution), "import": "PASS"}
    # Check planned entry-point imports only; do not fit models or mine rules.
    from sklearn.cluster import KMeans  # noqa: F401
    from mlxtend.frequent_patterns import apriori, association_rules  # noqa: F401

    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    print(json.dumps({
        "python": sys.version,
        "executable": sys.executable,
        "environment": sys.prefix,
        "pip": version("pip"),
        "packages": results,
        "algorithm_entrypoint_imports": "PASS (no algorithms executed)",
    }, indent=2))


if __name__ == "__main__":
    main()

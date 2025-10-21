# MKUltraSkelly

Enhanced control program for the Grave & Bones Ultra Skele.

## Quick start

Prepare a fresh workstation with the bootstrap script before working on the
project. The helper installs system dependencies, enables Bluetooth support, and
creates a Python virtual environment so the application can be developed or run
immediately:

```bash
./scripts/bootstrap.sh
```

> **Tip:** Run the script from the repository root. Administrative privileges
> (either as `root` or via `sudo`) are required so that apt operations and
> service configuration succeed.

The script performs the following actions:

1. Updates the apt package index and upgrades installed packages.
2. Installs Bluetooth and Python build dependencies (`bluez`, `bluez-tools`,
   `bluetooth`, `python3-venv`, and related packages).
3. Enables and starts the `bluetooth` service when `systemd` is available on the
   host.
4. Clones the repository (when `REPO_URL` is provided) or updates the existing
   checkout.
5. Provisions a `.venv` virtual environment and, when `requirements.txt` is
   present, installs the listed Python dependencies.

### Customisation

Tweak the workflow by exporting any of the following environment variables
before running the script:

| Variable     | Purpose |
|--------------|---------|
| `REPO_URL`   | Source URL used when cloning into an empty directory. |
| `REPO_DIR`   | Target directory for the checkout (defaults to the repository root). |
| `PYTHON_BIN` | Python interpreter used for the virtual environment (`python3` by default). |
| `VENV_PATH`  | Location where the virtual environment should be created (defaults to `<repo>/.venv`). |

### After bootstrapping

Activate the environment whenever you work on the project:

```bash
source .venv/bin/activate
```

You can then run project-specific tooling, install additional dependencies, or
execute scripts in an isolated context. When finished, deactivate the
environment with `deactivate`.

## Repository layout

```
scripts/
└── bootstrap.sh   # System setup and virtual environment provisioning helper
```

Additional source code and documentation will appear as the project evolves.

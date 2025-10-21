# MKUltraSkelly

Enhanced control program for the Grave & Bones Ultra Skele.

## Quick start

Use the provided bootstrap script to prepare a fresh environment with the system
packages, Bluetooth services, and Python virtual environment required by the
project:

```bash
./scripts/bootstrap.sh
```

The script performs the following steps:

1. Updates the apt package index and upgrades installed packages.
2. Installs the Bluetooth and Python build dependencies (`bluez`,
   `python3-venv`, and related packages).
3. Enables and starts the `bluetooth` service when `systemd` is available.
4. Clones or updates this repository, depending on whether an existing checkout
   is present.
5. Creates a `.venv` virtual environment and installs dependencies listed in
   `requirements.txt` when the file is present.

You can customise the behaviour with the following environment variables:

- `REPO_URL` – clone source when the target directory is empty.
- `REPO_DIR` – location for the checkout (defaults to the repository root).
- `PYTHON_BIN` – Python interpreter to use for the virtual environment.
- `VENV_PATH` – destination for the virtual environment (defaults to
  `<repo>/.venv`).

Run the script with administrative privileges (either as root or via `sudo`) so
that apt operations and service configuration can succeed.

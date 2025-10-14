# How to contribute
First you need to download and install [VS Code](https://code.visualstudio.com/download) and [Git](https://git-scm.com/downloads).  When installing Git, remember to opt-in to install the Unix utilities.  THis is a requirement.  You also need either [docker](https://www.docker.com/get-started/) or [podman](https://podman-desktop.io/downloads) to be installed for stress testing.

The following instructions should be executed in a terminal.  If Windows is your development environment, you should launch the terminal as an **administrator**.

Then you need to clone this project down to your local drive with the following command:
```bash
  git    clone  https://github.com/McCache/McCache-for-Python.git
```
If you are developing under Unix, once you have cloned the project down, run the following command to convert the Window's `CRLF` to `LF` end of line format:
```bash
  dos2unix  McCache-for-Python/tests/*.sh
  dos2unix  McCache-for-Python/tests/run_test
```

Next, make a copy of `pyproject.toml.sample` to `pyproject.toml`.  You may add additional configuration into s`pyproject.toml` to suite your needs.

Install the package and virtual environment manager of your choice.  We recommend `uv` but we have kept `pipenv` for backward compatibility.

<details open><summary><font size="3" color="cyan">uv</font></summary>

### Virtual Environment and Package Manager
We use [`uv`](https://docs.astral.sh/uv/), a very fast package manager, to manage the dependencies.

If you don't have `uv` installed, you should install it with the following command outside of your virtual environment:
```bash
  pip install -U  pip
  pip install     wheel
  pip install     uv
```

Once you have installed `uv`, the next step is to create a virtual environment with the following command:

```bash
  uv  venv
```

`uv` does **not** autoload your local `.env` file to set your custom environment variables.  You need to use the `--env-file` CLI parameter to point to your `.env` file or via the environment variable `UV_ENV_FILE`.  We are going to permanently set the `UV_ENV_FILE` environment variable to point to any `.env` file the current directory.

The follow command is only needed to be executed once.
```bash
  ::  Windows
  setx  UV_ENV_FILE .env

  #   Unix
  echo "UV_ENV_FILE=.env" >> ~/.bashrc
```

> [!IMPORTANT]
> Restart your terminal or source in the update `.env` file.

To activate your `virtualenv` with environment variable set from the `.env` file, run the following command:

<details open><summary><font size="3" color="cyan">uv</font></summary>

```bash
  ::  Windows
  uv  run cmd

  #   Unix
  uv  run bash
```
</details>

<details><summary><font size="3" color="cyan">pipenv</font></summary>

```bash
  pipenv  shell
```
</details>

> [!IMPORTANT]
> You should work from within the virtual environment at the root directory of the project.

Install all the project dependencies in the `pyproject.toml` using `uv`.  Use the following command to install all Python project dependencies:
```bash
  uv  sync
  uv  tree
```

<details><summary><font size="3" color="cyan">pipenv</font></summary>

We used to use [`pipenv`](https://realpython.com/pipenv-guide/) to manage the dependencies.  It is a slow resolving dependencies but we hope it is a one time activity that you as a developer have to perform.  `pipenv` can load your local `.env` file to set your custom environment variables.  We are left this documentation here for some backward compatibility.

If you don't have `pipenv` installed, you should install it with the following command outside of your virtual environment:
```bash
  pip    install -U  pip
  pip    install     wheel
  pip    install     pipenv
```

Once you have installed `pipenv`, the next step is to install all the project dependencies in the `Pipfile` using `pipenv`.  Use the following command to install all Python project dependencies:
```bash
  pipenv sync
  pipenv sync --dev
  pipenv graph
```
It may take a few minutes to rebuild the `Pipenv.lock` file, so be a little patient.
</details>

Install `pre-commit` into you github local repo with the following command:
```bash
  pre-commit install
```
`pre-commit` hook into `git` to auto check for your code for project requirements before it is committed into your local `git` repo.

Get the PyPi API key from the primary maintainer.  You can add it into the your local `.env` file.

## Formatting Philosophy
We are polyglot developers and we bring non-pythonic best practice to this project.
We like [PEP8](https://peps.python.org/pep-0008/#a-foolish-consistency-is-the-hobgoblin-of-little-minds) as a starting guideline but will **not** adhere to it if it makes the code harder to read.  Explicitly called out in PEP8 is "**do not break backwards compatibility just to comply with this PEP!**".  The area where we will deviate the most are:
* Max Line Length:
  * We are defaulting it to 160 but we trust that you exercise good judgement to keep it as short as possible around at 100.
  * For string messages, you don't need to game this limit by concatenating a bunch of individual lines to keep the string length at a reasonable length.
* Whitespaces:
  * We love it for we believe it makes the code more readable and we do not live in the 90s with small monitors.  Characters that are butted together is harder to read.
* Commas:
  * This is **not** English literature writing.  A comma is use to introduce the next term.  Therefore we have a space before the comma but no space after the comma.  If there is no next term, you will not need a comma to separate the terms as depicted by the following railroad diagram:
    * WIP: Waiting for [`mermaid`](https://github.com/mermaid-js/mermaid/issues/4252) railroad diagram support.
* Vertical alignment:
  * We believe that vertical align make it easier on the eyes to pick out deltas.  A multi jagged lines require the eyes and brain to perform a lot of scans and processing creating mental fatigue.

For this project, do follow the project precedence.  We expect you to run your changes through the `ruff` linter before you commit your changes.  The `ruff` configurations are in the `pyproject.toml` file under the `[tool.ruff]` section.

## Entrypoint
We recommend that you read the script [`start_mccache.py`](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py) to see how this library is used.  This script is used in the test harness to generate random cache activities in all the member in the test cluster.

The following sub-sections are tasks you need to perform manually before you commit your code.  At this point in time, it is **not** part of `pre-commit` so that there is some flexibility.

## Codestyle
You can run the following command to check the code for PEP8 formatting compliance.
```bash
  ::  Windows
  ruff  check  .\src\mccache\*.py

  #   Unix
  ruff  check  ./src/mccache/*.py
```
`ruff` documentation mentioned that it be used to replace `Flake8`, `isort`, `pydocstyle`, `yesqa`, `eradicate`, `pyupgrade`, and `autoflake`.
Execute the following command to display all the `ruff` supported linters:
```bash
  ruff  linter
```

### Checks
You can run the following command to further check the code.  `bandit` and `vulture` are automatic when you commit your code.
```bash
  ::  Windows
  mypy  --disable-error-code "arg-type"  .\src\mccache\   # Static type checker.
  bandit -r .\src\mccache\    # Security issues scanner.
  vulture   .\src\mccache\    # Dead code scanner.
  
  #   Unix
  mypy  --disable-error-code "arg-type"  ./src/mccache/   # Static type checker.
  bandit -r ./src/mccache/    # Security issues scanner.
  vulture   ./src/mccache/    # Dead code scanner.
```

### Tests
You can run the following command to **unit** test `PyCache` and `McCache`.
```bash
  ::  Windows
  pytest  .\tests\unit\test_pycache.py
  pytest  .\tests\unit\test_mccache.py

  #   Unix
  pytest  ./tests/unit/test_pycache.py
  pytest  ./tests/unit/test_mccache.py
```

### Coverage
You can run the following command to the coverage of `PyCache`.
```
  coverage  erase
  coverage  run -m  pytest  ./tests/unit/test_pycache.py
  coverage  report  --skip-empty --include                __init__.py
  coverage  report  --skip-empty --include --show-missing __init__.py
 ```

You may need to set your `PYTHONPATH` to pick up the packages to test.  `.env` is loaded by `pipenv` on invocation but not by `uv`.  If not try setting it as follows:
```bash
  ::  Windows
  SET PYTHONPATH="Path\to\your\source\root\directory"

  #   Unix
  PYTHONPATH="Path/to/your/source/root/directory"
```

You can run the following script to **stress** test `McCache`.
```bash
  ::  Windows
  .\tests\run_test

  #   Unix
  ./tests/run_test
```

### Before submitting
Before submitting your code please do the following steps:

1. Add any changes you want.
1. Add tests for the new changes.
1. Edit documentation if you have changed something significant.
1. Run the steps outline above from the **[Codestyle](#Codestyle)** section to format your changes.
1. Run the steps outline above from the **[Checks](#Checks)** section to ensure that types, security and docstrings are okay.
1. Run the steps outline above from the **[Tests](#Tests)** section to ensure that we did not break functionality.

## Deployment
Once the code is tested, you can install `McCache` into your local environment with the following command:
```bash
  pip uninstall  mccache
  pip   install -e  .
```

Check the local installation with the following command:
```bash
  pip list | grep -iE "McCache|Version"
```
You should get an output similar to the following:
```
Package           Version     Editable project location
McCache           0.0.0       C:\Work\Dev\McCache-for-Python
```

We use `hatch` to build and publish this package to [PyPi](https://pypi.org).  For each publish to the repository, you **must** increment the version number in the `src/mccache/__about__.py` file. Run the following command from the root directory of the `McCache` project:

<details open><summary><font size="3">uv</font></summary>

```bash
  ::  Windows
  del   dist/*

  #   Unix
  rm    dist/*

  uv    build
```
</details>
<details><summary><font size="3">hatch</font></summary>

```bash
  hatch env       show    # Show your environment(s) to build for.
  hatch clean             # Clean out the content  in the ./dist folder.
  hatch build  -t wheel   # Build the wheel file into the ./dist folder.
```
</details>

The above will create a sub-directory named `dist` under the project root directory.  Check the build with the following commands:
```bash
  #   Test the wheel file using Twine.
  twine   check   dist/mccache*.whl

  dir     dist          # Show the build artifacts in the ./dist folder.
```
You should get an output similar to the following:
```
  total 48K
  48K mccache-0.0.0-py3-none-any.whl
```

Once everything is checked out, you can manually deploy this `McCache` package to the `PyPi` repository.  First you should test the deploy to `TestPyPi` before you deploy it to the main `PyPi`.  Run the following command to publish the package.
```bash
  uv    publish
```

Make sure you do **ONLY** publish the `wheel` file up to the repository.


## TODOs
* We need to automate the unit test using the `pre-commit` hook.
* We need to automate the build using GitHub Actions.

## Other help
You can contribute by spreading a word about this library.
It would also be a huge contribution to write a short article on how you are using this project.
You can also share your best practices with us.

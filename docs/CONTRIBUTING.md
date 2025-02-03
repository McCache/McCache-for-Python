# How to contribute

First you need to clone this project down to your local drive with the following command:
```bash
git    clone  https://github.com/McCache/McCache-for-Python.git
```
Next, make a copy of `pyproject.toml.sample` to `pyproject.toml`.  You may add additional configuration into  `pyproject.toml` to suite your needs.

You need either `podman` or `docker` to be installed for stress testing.

We use `pipenv` to manage the [dependencies](https://realpython.com/pipenv-guide/).  It is a slow resolving dependencies but we hope it is a one time activity that you as a developer have to perform.  `pipenv` can load your local `.env` file to set your custom environment variables.  We are considering other tools like `hatch` or `uv` in the future.
If you don't have `pipenv` installed, you should install it with the following command outside of your virtual environment:
```bash
pip    install -U  pip
pip    install     wheel
pip    install     pipenv
```

Once you have installed `pipenv`, the next step is to install all the project dependencies in the `Pipfile` using `pipenv`.  Use the following command to install all Python project dependencies:
```bash
pipenv sync
pipenv graph
```
It may take a few minutes to rebuild the `Pipenv.lock` file, so be a little patient.

Install `pre-commit` to with the following command:
```bash
pre-commit install
```
`pre-commit` hook into `git` to auto check for your code for project requirements before it is committed into your local `git` repo.

To activate your `virtualenv` run the following command:
```bash
pipenv  shell
```
You should work from within the virtual environment at the root directory of the project.

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
    * WIP: Waiting for [`mermaid`](https://mermaid.js.org/intro/) railroad diagram support.
* Vertical alignment:
  * We believe that vertical align make it easier on the eyes to pick out deltas.  A multi jagged lines require the eyes and brain to perform a lot of scans and processing creating mental fatigue.

For this project, do use follow the project precedence.  We expect you to run your changes through the `ruff` linter before you commit your changes.  The `ruff` configurations are in the `pyproject.toml` file under the `[tool.ruff]` section.

## Entrypoint
We recommend that you read the script [`start_mccache.py`](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py) to see how this library is used.  This script is used in the test harness to generate random cache activities in all the member in the test cluster.

The following sub-sections are tasks you need to perform manually before you commit your code.  At this point in time, it is **not** part of `pre-commit` so that there is some flexibility.

## Codestyle
You can run the following command to check the code for PEP8 formatting compliance.
```bash
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
mypy  --disable-error-code "arg-type"  ./src/mccache/*.py  # Static type checker for Python.
bandit  ./src/mccache/*.py  # Security issues scanner.
vulture ./src/mccache/*.py  # Dead code scanner.
```

### Tests
You can run the following command to **unit** test `PyCache`.
```bash
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

You may need to set your `PYTHONPATH` to pick up the packages to test.  `.env` should be loaded by `pipenv` on invocation.  If not try setting it as follows:
```bash
PYTHONPATH="Path/to/your/source/root/directory"
```

You can run the following script to **stress** test `McCache`.
```bash
./tests/run_test
```

### Before submitting
Before submitting your code please do the following steps:

1. Add any changes you want.
1. Add tests for the new changes.
1. Edit documentation if you have changed something significant.
1. Run the steps outline above from the **`Codestyle`** section to format your changes.
1. Run the steps outline above from the **`Checks`** section to ensure that types, security and docstrings are okay.
1. Run the steps outline above from the **`Tests`** section to ensure that we did not break functionality.

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
```bash
hatch   env   show      # Show your environment(s) to build for.
hatch   clean           # Clean out the content  in the ./dist folder.
hatch   build -t wheel  # Build the wheel file into the ./dist folder.
```
The above will create a sub-directory named `dist` under the project root directory.  Check the build with the following commands:
```bash
# Test the wheel file using Twine.
twine   check   dist/mccache*.whl
ls -sh  dist            # Show the build artifacts in the ./dist folder.
```
You should get an output similar to the following:
```
total 48K
48K mccache-0.0.0-py3-none-any.whl
```

Once everything is checked out, you can manually deploy this `McCache` package to the `PyPi` repository.  First you should test the deploy to `TestPyPi` before you deploy it to the main `PyPi`.  Run the following command to publish the package.

Using **Twine** to publish `McCache` to the repository.
```bash
# Publish ONLY the wheel file to TestPypi using Twine.
twine  upload  -r testpypi  dist/mccache*.whl

# Publish ONLY the wheel file to Pypi using Twine.
twine  upload  -r pypi      dist/mccache*.whl
```
Using **Hatch** to publish `McCache` to the repository.
```bash
# Publish ONLY the wheel file to TestPypi using Hatch.
hatch  publish -r test   dist/

# Publish ONLY the wheel file to Pypi using Hatch.
hatch  publish -r main   dist/
```
Make sure you do **ONLY** publish the `wheel` file up to the repository.

SEE: https://hatch.pypa.io/1.9/publish/

## TODOs
* We need to automate the unit test using the `pre-commit` hook.
* We need to automate the build using GitHub Actions.

## Other help
You can contribute by spreading a word about this library.
It would also be a huge contribution to write a short article on how you are using this project.
You can also share your best practices with us.

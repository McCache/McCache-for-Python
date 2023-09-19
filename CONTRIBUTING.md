# How to contribute

## Dependencies

You need either `podman` or `docker` to be installed for testing.

We use `pipenv` to manage the [dependencies](https://realpython.com/pipenv-guide/).  It is a slow resolving dependencies but we hope it is a one time activity that you as a developer have to perform.  We are considering other tools like in the future.
If you dont have `pipenv` installed, you should install it with the following command outside of your virtual environment:
```bash
pip    install -U  pip
pip    install     wheel
pip    install     pipenv
```

Once you have installed `pipenv`, the next step is to install all the project dependencies in the `Pipfile` using `pipenv`.  Use the following command to install all Python project dependencies:
```
pipenv sync
```
It may take a few minutes to rebuild the `Pipenv.lock` file, so be a little patient.

To activate your `virtualenv` run the following command:
```bash
pipenv  shell
```

We use `hatch` to build and publish this package to [PyPi](https://pypi.org).
```bash
pipenv  run hatch  build
```

## Formatting Philosophy
We are polygot developers and we bring non-pythonic best practice to this project.
We like [PEP8](https://peps.python.org/pep-0008/#a-foolish-consistency-is-the-hobgoblin-of-little-minds) as a starting guideline but will **not** adhere to it if it makes the code harder to read.  Explicitely called out in PEP8 is "**do not break backwards compatibility just to comply with this PEP!**".  The area where we will deviate the most are:
* Max Line Length:
  * We are defaulting it to 160 but we trust that you excercise good jugdement to keep it as short as possible around at 100.
* Whitespaces:
  * We love it for we believe it makes the code more readable and we do not live in the 90s with small monitors.  Characters that are butted together is harder to read.
* Commas:
  * This is **not** English literature writing.  A comma is use to introduce the next term.  Therefore we have a space before the comma but no space after the comma.  If there is no next term, you will not need a comma to seperate the terms as dipicted by the following reailroad diagram:
    * WIP: Waiting for [`mermaid`](https://mermaid.js.org/intro/) railroad diagram support.
* Vertical aligment:
  * We believe that vertical align make it easier on the eyes to pick out deltas.  A multi jagged lines require the eyes and brain to perform a lot of scans and processing creating mental fatigue.

For this project, do use follow the project precedence.  We expect you to run your changes through the `ruff` linter before you commit your changes.

## Entrypoint
We recommend that you read the script [`start_mccache.py`](https://github.com/McCache/McCache-for-Python/blob/main/tests/unit/start_mccache.py) to see how this library is used.  This script is used in the test harness to generate random cache activities in all the member in the test cluster.

The following sub-sections are taks you  need to perform manually before you commit your code.  At this point in time, it is **not** part of `pre-commit` so that there is some flexibity.

## Codestyle
You can run the following command to check the code for PEP8 formatting compliance.
```bash
ruff check   ./src/mccache/*.py
```
`ruff` documentation mentioned that it be used to replace `Flake8`, `isort`, `pydocstyle`, `yesqa`, `eradicate`, `pyupgrade`, and `autoflake`.
Execute the following command to display all the `ruff` supported linters:
```
pipenv run ruff linter
```

### Checks

You can run the following command to further check the code.
```bash
mypy         ./src/mccache/*.py  # Static type checker for Python.
bandit       ./src/mccache/*.py  # Security issues scanner.
vulture      ./src/mccache/*.py  # Dead code scanner.
```

### Tests

You can run the following command to unit test the code.
```bash
./tests/run_unit_test
```

### Before submitting

Before submitting your code please do the following steps:

1. Add any changes you want.
1. Add tests for the new changes.
1. Edit documentation if you have changed something significant.
1. Run the steps outline above from the **`Codestyle`** section to format your changes.
1. Run the steps outline above from the **`Checks`** section to ensure that types, security and docstrings are okay.
1. Run the steps outline above from the **`Tests`** section to ensure that we did not break functionality.

## Other help

You can contribute by spreading a word about this library.
It would also be a huge contribution to write a short article on how you are using this project.
You can also share your best practices with us.

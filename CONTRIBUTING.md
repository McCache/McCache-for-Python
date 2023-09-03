# How to contribute

## Dependencies

We need either `podman` or `docker` to be installed for testing.

We use `pipenv` to manage the [dependencies](https://realpython.com/pipenv-guide/).  It is a slow resolving dependencies but we hope it is a one time activity that you as a developer have to perform.  We are considering `poetry` in the future.
If you dont have `pipenv`, you should install with the following command outside of your virtual environment:
```bash
pip    install -U  pip
pip    install     wheel
pip    install     pipenv
```

We use `build` to build and publish this package to [PyPi](https://pypi.org).
```bash
```

To install dependencies and prepare [`pre-commit`](https://pre-commit.com/) hooks you would need to run the following command:

```bash
pipenv run  pre-commit  install
```

To activate your `virtualenv` run the following command:
```bash
pipenv shell
```

## Codestyle

After installation you may execute code formatting with the following commands:
```bash
pipenv run pyupgrade    --exit-zero-even-if-changed --py39-plus **/*.py
pipenv run isort        --settings-path pyproject.toml  ./src
pipenv run blue         --config        pyproject.toml  ./src
pipenv run ruff
pipenv run darglint     --verbosity  2  mccache tests
```

### Checks

You can run the following command to further check the code.
```bash
pipenv run mypy         --config-file   pyproject.toml  ./src
pipenv check
pipenv run safety check --full-report
pipenv run bandit -ll   --recursive     mccache tests
pipenv run vulture
```

### Tests

You can run the following command to unit test the code.
```bash
tests/run_unit_test
```

### Before submitting

Before submitting your code please do the following steps:

1. Add any changes you want.
1. Add tests for the new changes.
1. Edit documentation if you have changed something significant.
1. Run the steps outline above from the `Codestyle` section to format your changes.
1. Run the steps outline above from the `Checks` section to ensure that types, security and docstrings are okay.
1. Run the steps outline above from the `Tests` section to ensure that we did not break functionality.

## Other help

You can contribute by spreading a word about this library.
It would also be a huge contribution to write a short article on how you are using this project.
You can also share your best practices with us.

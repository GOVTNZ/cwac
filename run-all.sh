black -l 120 .
mypy .
flake8 --max-line-length 120 .
bandit -r .
isort --diff --profile black .
pydocstyle --convention=google
pylint -rn -sn $(git ls-files '*.py')
npx prettier --write web/

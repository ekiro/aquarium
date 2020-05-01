FROM python:3.8

WORKDIR /aquarium

RUN pip install poetry
COPY pyproject.toml /aquarium/pyproject.toml
COPY poetry.lock /aquarium/poetry.lock
RUN poetry install

ENTRYPOINT [ "poetry", "run", "python", "-m", "aquarium.app" ]
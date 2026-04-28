FROM python:3.12-slim

WORKDIR /app

RUN apt-get update

COPY ./docker/frontend-requirements.txt /app

RUN pip install --no-cache-dir -r frontend-requirements.txt

VOLUME ["/app/logs"]

EXPOSE 8501

COPY ./.streamlit /app/.streamlit

RUN mkdir "src" && touch src/__init__.py
COPY ./src/frontend /app/src/frontend

ENTRYPOINT ["streamlit","run","src/frontend/web.py"]
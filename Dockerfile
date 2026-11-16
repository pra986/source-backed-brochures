FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY brochure ./brochure
RUN pip install --no-cache-dir . && useradd -m app && mkdir /app/.data && chown app:app /app/.data
USER app
EXPOSE 8000
CMD ["uvicorn", "brochure.app:app", "--host", "0.0.0.0", "--port", "8000"]

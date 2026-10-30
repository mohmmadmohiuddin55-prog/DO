FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DO_HOSTED_MODE=1 DO_HOST=0.0.0.0
WORKDIR /app
COPY requirements-web.txt ./
RUN python -m pip install --no-cache-dir -r requirements-web.txt
COPY web_server.py language_filter.py ./
COPY frontend ./frontend
EXPOSE 8000
CMD ["python", "web_server.py"]

FROM python:3.12-slim

# Without this, Python buffers stdout when it isn't attached to a
# terminal (which is always true inside a container), so every print()
# call sits invisible until the buffer fills. `docker logs` would show
# nothing at all, even while the script is running fine.
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY producer.py .

CMD ["python", "producer.py"]
